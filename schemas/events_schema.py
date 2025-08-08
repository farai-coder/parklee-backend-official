from typing import List, Optional
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class EventCreate(BaseModel):
    name: str
    description: Optional[str] = None
    # Make date, start_time, and end_time optional
    date: Optional[datetime] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    event_location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    allowed_parking_lots: Optional[List[str]] = []
   
class EventRead(EventCreate):
    id: UUID
    
    class config:
        orm_mode = True

class MessageResponse(BaseModel):
    message: str
