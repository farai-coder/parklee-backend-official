# schemas/auth_schema.py
from datetime import date
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from uuid import UUID

# Existing schemas (ensure these match your current ones)
class AuthBase(BaseModel):
    user_id: UUID
    password: str = Field(..., min_length=8, max_length=128) # Added min/max length for password

class AuthLogin(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    user_id: UUID
    status: str
    role: str

class LoginResponse(BaseModel):
    user_id: UUID
    status: str
    role: str
    name: Optional[str] = None
    profile_image: Optional[str] = None
    email: str
    business_name: Optional[str] = None
    business_description: Optional[str] = None
    business_profile_image: Optional[str] = None

class PasswordChange(BaseModel):
    user_id: UUID # User ID for the logged-in user changing their password
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

class PasswordResetRequest(BaseModel):
    email: str

# --- NEW SCHEMAS FOR VERIFICATION CODE BASED RESET ---

class VerifyResetCodeRequest(BaseModel):
    email: str
    code: str = Field(..., min_length=6, max_length=6) # Assuming 6-digit code

class ResetPasswordConfirm(BaseModel):
    email: str
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)

class UploadImageResponse(BaseModel):
    image_path: str

class MessageResponse(BaseModel):
    message: str

class UserBase(BaseModel):
    email: EmailStr
    date_of_birth: Optional[date] = None
    name: str
    gender: Optional[str] = None
    surname: str
    phone_number: Optional[str] = None

class UserResponse(BaseModel):
    id: UUID
    username: Optional[str] = None
    role: str
    status: str

    class Config:
        orm_mode = True

# --- Schema for User Creation (Input) ---
class UserCreate(BaseModel):
    email: EmailStr
    name: str
    surname: str
    gender: Optional[str] = None
    phone_number: Optional[str] = None
    role: Optional[str] = "customer"

# --- Schema for User Updates (Input) ---
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    date_of_birth: Optional[date] = None
    name: Optional[str] = None
    gender: Optional[str] = None
    surname: Optional[str] = None
    phone_number: Optional[str] = None
    status: Optional[str] = None
    role: Optional[str] = None

class AuthResponse(BaseModel):
    user_id: UUID
    status: str
    message: Optional[str] = None

class ImagePathResponse(BaseModel):
    image_path: str

# --- Success Message Schema ---
class MessageResponse(BaseModel):
    message: str

# --- New schemas start here ---
class AuthLogin(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    message: str
    user_id: UUID
    user_email: EmailStr
    user_role: str
    user_status: str

class PasswordChange(BaseModel):
    user_id: UUID
    old_password: str
    new_password: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class VerifyResetCodeRequest(BaseModel):
    email: EmailStr
    reset_code: str

class ResetPasswordConfirm(BaseModel):
    email: EmailStr
    reset_code: str
    new_password: str

# New schema for the create user response
class UserIdResponse(BaseModel):
    user_id: UUID