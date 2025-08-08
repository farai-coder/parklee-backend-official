from typing import List, Optional
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class ReservationCreate(BaseModel):
    user_id: UUID
    spot_id: UUID
    event_id: Optional[UUID] = None
    start_time: datetime
    end_time: datetime


class ReservationRead(ReservationCreate):
    id: UUID
    status: str # Added status to read schema

    class Config:
        orm_mode = True

class ReservationCancel(BaseModel): # New schema for cancellation
    reservation_id: UUID
    user_id: UUID # To verify ownership or admin privilege