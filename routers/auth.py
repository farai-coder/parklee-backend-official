from typing import Optional
from datetime import datetime, timedelta, timezone # Import timedelta and timezone
import string
import secrets

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status
import bcrypt

# Import models
from models import User,  VerificationCode# Make sure VerificationCode is imported
# Import schemas
from schemas.auth_schema import SuccessMessage
from schemas.userSchema import AuthBase, AuthResponse, AuthLogin, LoginResponse, PasswordResetRequest, VerifyResetCodeRequest, ResetPasswordConfirm, PasswordChange, MessageResponse
from database import get_db

# --- Utility Functions (no change needed here) ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies if a given password matches the stored hash."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def hash_password(password: str) -> str:
    """Hashes a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_password.decode('utf-8')

def create_verification_code(length: int = 6) -> str: # Changed name for clarity and default length
    """Generates a random numerical verification code (PIN)."""
    digits = string.digits
    return ''.join(secrets.choice(digits) for _ in range(length))

def authenticate_user(db: Session, email: str, password: str) -> User:
    """Authenticates a user by email and password."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, # Use status.HTTP for consistency
            detail="User with this email not found."
        )
    if not user.password_hash or not verify_password(password, user.password_hash): # Check if password_hash exists
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, # Use 401 for authentication failure
            detail="Incorrect email or password."
        )
    return user

# --- FastAPI Router ---
auth_router = APIRouter(prefix="/auth", tags=["Auth"])

# --- Endpoint to set initial password for a new user ---
@auth_router.post("/set-password", response_model=SuccessMessage, status_code=status.HTTP_200_OK)
def set_initial_password(auth: AuthBase, db: Session = Depends(get_db)):
    """
    Allows a newly registered user (or a user with no password set) to set their initial password.
    User's status is set to 'active' upon successful password creation.
    """
    user = db.query(User).filter(User.id == auth.user_id).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if user.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password already set for this user. Use /change-password instead.")

    user.password = hash_password(auth.password)
    user.status = "active" # Mark user as active after password is set
    user.updated_at = datetime.now(timezone.utc) # Update timestamp

    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to set password: {e}")

    return SuccessMessage(message="Successfully created an account!")


# --- Endpoint for User Login ---

# In auth.py (login endpoint)
@auth_router.post("/login", response_model=LoginResponse)
async def login(auth_data: AuthLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == auth_data.email).first()

    if not user or not user.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or password not set.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(auth_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check user status
    if user.status in ["disabled", "pending", "inactive"]: # Updated check
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User account is {user.status}. Please contact support.",
        )

    # For simplicity, returning basic user info. In a real app, generate a token.
    return LoginResponse(
        message="Login successful",
        user_id=user.id,
        user_email=user.email,
        user_role=user.role,
        user_status=user.status
    )

# 1. Request Password Reset (Generates and "sends" code)
@auth_router.post("/forgot-password", response_model=MessageResponse, status_code=status.HTTP_200_OK)
async def forgot_password_request(request: PasswordResetRequest, db: Session = Depends(get_db)):
    """
    Initiates the password reset process by generating a verification code
    and associating it with the user's email.
    """
    user = db.query(User).filter(User.email == request.email).first()
    
    if user: # Only generate/send if user exists to prevent email enumeration
        verification_code_value = create_verification_code()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15) # Code valid for 15 minutes

        # Invalidate any previous unused reset codes for this user
        db.query(VerificationCode).filter(
            VerificationCode.user_id == user.id,
            VerificationCode.type == "password_reset",
            VerificationCode.is_used == False,
            VerificationCode.expires_at > datetime.now(timezone.utc)
        ).update({"is_used": True}, synchronize_session=False) # Mark as used without loading objects

        new_code = VerificationCode(
            user_id=user.id,
            code=verification_code_value,
            type="password_reset",
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc)
        )
        
        try:
            db.add(new_code)
            db.commit()
            # TODO: Integrate with an email/SMS sending service here
            print(f"DEBUG: Password reset code for {user.email}: {verification_code_value}")
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate reset code: {e}")
            
    # Always return a generic success message to prevent user enumeration
    return MessageResponse(message="If an account with that email exists, a password reset code has been sent.")

# 2. Verify Password Reset Code
@auth_router.post("/verify-reset-code", response_model=MessageResponse, status_code=status.HTTP_200_OK)
async def verify_reset_code(request: VerifyResetCodeRequest, db: Session = Depends(get_db)):
    """
    Verifies if the provided reset code is valid for the given email.
    """
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    verification_code = db.query(VerificationCode).filter(
        VerificationCode.user_id == user.id,
        VerificationCode.code == request.code,
        VerificationCode.type == "password_reset",
        VerificationCode.is_used == False,
        VerificationCode.expires_at > datetime.now(timezone.utc)
    ).first()

    if not verification_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid, expired, or used verification code.")
    
    # Code is valid but not used yet. We don't mark it as used here, only on successful password change.
    return MessageResponse(message="Verification code is valid. You can now reset your password.")

# 3. Reset Password (After code verification)
@auth_router.post("/reset-password", response_model=MessageResponse, status_code=status.HTTP_200_OK)
async def reset_password_confirm(data: ResetPasswordConfirm, db: Session = Depends(get_db)):
    """
    Allows a user to reset their password using a valid verification code.
    """
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    verification_code = db.query(VerificationCode).filter(
        VerificationCode.user_id == user.id,
        VerificationCode.code == data.code,
        VerificationCode.type == "password_reset",
        VerificationCode.is_used == False,
        VerificationCode.expires_at > datetime.now(timezone.utc)
    ).first()

    if not verification_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid, expired, or used verification code.")

    # Update password and mark code as used
    user.password_hash = hash_password(data.new_password)
    user.updated_at = datetime.now(timezone.utc)
    verification_code.is_used = True
    verification_code.updated_at = datetime.now(timezone.utc) # Assuming updated_at on VerificationCode model

    try:
        db.add(user)
        db.add(verification_code)
        db.commit()
        db.refresh(user)
        db.refresh(verification_code)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to reset password: {e}")

    return MessageResponse(message="Password has been successfully reset.")

# --- Endpoint for Logged-in User to Change Password ---
@auth_router.post("/change-password", response_model=MessageResponse, status_code=status.HTTP_200_OK)
async def change_password(data: PasswordChange, db: Session = Depends(get_db)):
    """
    Allows a logged-in user to change their password, requiring their old password for verification.
    """
    user = db.query(User).filter(User.id == data.user_id).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if not user.password_hash or not verify_password(data.old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, # Changed to 401 for incorrect old password
            detail="Incorrect old password."
        )
    
    if verify_password(data.new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be the same as the old password."
        )

    user.password_hash = hash_password(data.new_password)
    user.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to change password: {e}")

    return MessageResponse(message="Password changed successfully.")