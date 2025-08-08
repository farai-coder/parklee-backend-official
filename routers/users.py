from datetime import datetime, timezone
from io import BytesIO
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse, StreamingResponse
from database import SessionLocal
from models import User # Ensure your SQLAlchemy User model is imported correctly
from schemas.auth_schema import AuthResponse
from schemas.auth_schema import ImagePathResponse, SuccessMessage, UserBase, UserCreate, UserResponse, UserUpdate # Import updated schemas
from uuid import UUID
from typing import List, Optional
import os
from dotenv import load_dotenv
import boto3
from botocore.exceptions import NoCredentialsError
from database import get_db
from schemas.userSchema import UserIdResponse

user_router = APIRouter(prefix="/users", tags=["Users"])

def create_username(name: str, surname: str) -> str:
    """Generates a username from first name and surname."""
    return f"{name.lower()}.{surname.lower()}"

# In auth.py or users.py (depending on where create_user is)
@user_router.post("/", response_model=UserIdResponse, status_code=status.HTTP_201_CREATED)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    if user_in.phone_number and db.query(User).filter(User.phone_number == user_in.phone_number).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone number already registered")

    if user_in.license_plate and db.query(User).filter(User.license_plate == user_in.license_plate).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="License plate already registered")

    new_user = User(
        name=user_in.name,
        surname=user_in.surname,
        email=user_in.email,
        gender=user_in.gender,
        license_plate=user_in.license_plate, # Added
        phone_number=user_in.phone_number, # Added
        status="pending", # Default to pending
        role=user_in.role,
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    if not new_user.id:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user in database")

    return {"user_id": new_user.id}

@user_router.get("/", response_model=List[UserResponse])
def get_all_users(db: Session = Depends(get_db)):
    """
    Retrieves all users from the database.
    Returns detailed user information, including optional fields like username, location, and timestamps.
    """
    users = db.query(User).all()
    return users
