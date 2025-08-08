from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional, List
from datetime import date, datetime
from uuid import UUID

# --- Base Schema for User Information ---
# This will include all fields that are commonly shared across read/update operations.
class UserBase(BaseModel):
    email: EmailStr
    date_of_birth: Optional[date] = None
    name: str
    gender: Optional[str] = None
    surname: str
    phone_number: Optional[str] = None
    # Add business-related fields here as they are part of the user's full info
# -
class UserResponse(BaseModel):
    id: UUID
    name: Optional[str] = None
    surname: Optional[str] = None
    email: EmailStr
    gender: Optional[str] = None
    phone_number: Optional[str] = None
    license_plate: Optional[str] = None  # Added license_plate
    role: str
    status: str

    class Config:
        orm_mode = True
# --- Schema for User Creation (Input) ---
# This should only include fields necessary for initial creation.
class UserCreate(BaseModel):
    email: EmailStr
    name: str
    surname: str
    gender: Optional[str] = None
    phone_number: Optional[str] = None
    license_plate: str # Added license_plate
    role: Optional[str] = "staff"

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    date_of_birth: Optional[date] = None
    name: Optional[str] = None
    gender: Optional[str] = None
    surname: Optional[str] = None
    phone_number: Optional[str] = None
    license_plate: Optional[str] = None # Added license_plate
    status: Optional[str] = None
    role: Optional[str] = None

class AuthResponse(BaseModel):
    user_id: UUID
    status: str
    role: str

class ImagePathResponse(BaseModel):
    image_path: str

# --- Success Message Schema ---
class SuccessMessage(BaseModel):
    message: str
