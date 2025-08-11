from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List

class ParkingZoneCreate(BaseModel):
    name: str
    zone_type: str # staff, student, visitor, general
    latitude: Optional[float] = None
    logitude: Optional[float] = None

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

class ParkingZoneOccupancyRead(BaseModel):
    id: UUID
    name: str
    total_spots: int
    reserved_spots: int
    occupied_spots: int
    occupancy_rate: float  # as a decimal between 0 and 1
    latitude: Optional[float] = None
    longitude: Optional[float] = None

# --- Success Message Schema ---
class SuccessMessage(BaseModel):
    message: str