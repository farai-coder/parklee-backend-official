import datetime
from fastapi import Depends
from sqlalchemy.orm import Session
from models import ParkingSession,Reservation,ParkingSpot
from sqlalchemy import and_, not_

def get_available_spots(db: Session ):
    now = datetime.utcnow()
    # Subquery: spot IDs currently in use
    occupied = (
        db.query(ParkingSession.spot_id)
          .filter(ParkingSession.check_out_time.is_(None))
    )
    # Subquery: spot IDs reserved right now
    reserved = (
        db.query(Reservation.spot_id)
          .filter(and_(Reservation.start_time <= now,
                       Reservation.end_time > now))
    )
    # Spots that are neither in occupied nor reserved
    return (
        db.query(ParkingSpot)
          .filter(not_(ParkingSpot.id.in_(occupied.subquery())))
          .filter(not_(ParkingSpot.id.in_(reserved.subquery())))
          .all()
    )
