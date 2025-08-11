import pytz
from sqlalchemy import and_, or_
from models import Events
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
from schemas.auth_schema import SuccessMessage
from schemas.events_schema import EventCreate, EventRead
from database import get_db
from datetime import datetime, time, timedelta, timezone

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

@router.get("/counts")
def get_event_count(db: Session = Depends(get_db)):
    utc = pytz.UTC
    today = datetime.utcnow().date()
    start_of_day = utc.localize(datetime.combine(today, time.min))          # Today 00:00:00 UTC (aware)
    start_of_next_day = utc.localize(datetime.combine(today + timedelta(days=1), time.min))  # Tomorrow 00:00:00 UTC (aware)

    count = db.query(Events).filter(
        and_(
            Events.start_time < start_of_next_day,
            or_(
                Events.end_time == None,        # If end_time is null, consider event just at start_time
                Events.end_time >= start_of_day
            )
        )
    ).count()

    return {"events_count": count}

