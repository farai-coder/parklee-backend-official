from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List

class ParkingZoneCreate(BaseModel):
    name: str
    zone_type: str # staff, student, visitor, general

class ParkingZoneRead(ParkingZoneCreate):
    id: UUID
    class Config:
        from_attributes = True # This is the correct fix for Pydantic V2

class ParkingSpotCreate(BaseModel):
    spot_number: str
    lot_name: str
    is_vip: bool = False
    parking_zone_id: UUID

class ParkingSpotRead(ParkingSpotCreate):
    id: UUID
    status: str # occupied, empty, under_maintenance
    class Config:
        from_attributes = True # This is the correct fix for Pydantic V2

class ParkingSpotUpdate(BaseModel):
    spot_number: Optional[str] = None
    lot_name: Optional[str] = None
    is_vip: Optional[bool] = None
    spot_type: Optional[str] = None
    status: Optional[str] = None
    parking_zone_id: Optional[UUID] = None

# --- Success Message Schema ---
class SuccessMessage(BaseModel):
    message: str