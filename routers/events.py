from models import Events
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
from schemas.auth_schema import SuccessMessage
from schemas.events_schema import EventCreate, EventRead
from database import get_db
from datetime import datetime, timezone

router = APIRouter(prefix="/events", tags=["events"])

@router.post("/", response_model=SuccessMessage)
def create_event(event: EventCreate, db: Session = Depends(get_db)):
    db_event = Events(**event.model_dump())
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return SuccessMessage(message="Event created successfully")

@router.get("/{event_id}", response_model=EventRead)
def get_event(event_id: str, db: Session = Depends(get_db)):
    event = db.query(Events).filter(Events.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

@router.get("/", response_model=list[EventRead])
def get_all_events(db: Session = Depends(get_db)):
    return db.query(Events).all()

@router.delete("/{event_id}")
def delete_event(event_id: str, db: Session = Depends(get_db)):
    event = db.query(Events).filter(Events.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(event)
    db.commit()
    return {"detail": "Event deleted successfully"}


#events with todays date
@router.get("/today", response_model=list[EventRead])
def get_today_events(db: Session = Depends(get_db)):
    from datetime import datetime
    today = datetime.utcnow().date()
    return db.query(Events).filter(Events.date == today).all()

#how many events are happening today
@router.get("/counts")
def get_event_count(db:Session = Depends(get_db)):
    from datetime import datetime
    today = datetime.utcnow().date()
    return db.query(Events).filter(Events.date == today).count() 