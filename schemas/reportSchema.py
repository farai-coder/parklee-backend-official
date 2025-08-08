from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class ReportCreate(BaseModel):
    user_id: Optional[UUID] = None # Can be null if reported by system or anonymous
    license_plate: Optional[str] = None
    spot_id: Optional[UUID] = None
    zone_id: Optional[UUID] = None
    report_type: str # wrong_zone_entry, overstay, unauthorized_parking, other
    description: Optional[str] = None

class ReportRead(ReportCreate):
    id: UUID
    timestamp: datetime
    status: str
    class Config:
        orm_mode = True

class ReportUpdate(BaseModel):
    status: str # pending, resolved, dismissed
    description: Optional[str] = None