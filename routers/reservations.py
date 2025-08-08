import datetime
from fastapi import APIRouter, Depends, HTTPException, status
import pytz
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from database import SessionLocal
from models import ParkingSession, ParkingSpot, Reservation, User, Events, ParkingZone
from schemas.reservationsSchema import ReservationCreate, ReservationRead, ReservationCancel # Import new schema
from uuid import UUID
from database import get_db  # Assuming you have a get_db function to provide DB 
from datetime import datetime, timedelta, timezone # Import timezone

router = APIRouter(prefix="/reservations", tags=["reservations"])
@router.post("/reserve-spot", response_model=ReservationRead, status_code=status.HTTP_201_CREATED)
def create_reservation(res: ReservationCreate, db: Session = Depends(get_db)):

    existing_reservation = (
        db.query(Reservation)
        .filter(
            Reservation.user_id == res.user_id,
            Reservation.status.in_(["active", "pending"])
        )
        .first()
    )
    if existing_reservation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has an active or pending reservation."
        )

    user = db.query(User).get(res.user_id)
    spot = db.query(ParkingSpot).get(res.spot_id)
    event = db.query(Events).get(res.event_id) if res.event_id else None

    if not user or not spot:
        raise HTTPException(status_code=404, detail="User or Spot not found")

    # Get the parking zone for the spot
    parking_zone = db.query(ParkingZone).filter(ParkingZone.id == spot.parking_zone_id).first()
    if not parking_zone:
        raise HTTPException(status_code=404, detail="Parking zone for spot not found")

    # Role-based parking zone restriction
    if user.role in ["staff", "student", "visitor"] and parking_zone.zone_type != user.role:
        # Allow 'general' zones for everyone
        if parking_zone.zone_type != "general":
            raise HTTPException(status_code=403, detail=f"User with role '{user.role}' is not allowed to park in '{parking_zone.zone_type}' zones.")

    now = pytz.utc.localize(datetime.utcnow())

    # Event-specific checks if an event is linked
    if event and event.start_time:
        # Localize event.start_time if naive
        if event.start_time.tzinfo is None:
            event_start_time_aware = pytz.utc.localize(event.start_time)
        else:
            event_start_time_aware = event.start_time.astimezone(pytz.utc)

        # Localize reservation start time if naive
        if res.start_time.tzinfo is None:
            res_start_time_aware = pytz.utc.localize(res.start_time)
        else:
            res_start_time_aware = res.start_time.astimezone(pytz.utc)

        # Check if the spot's lot is allowed for this event
        if event.allowed_parking_lots and spot.lot_name not in event.allowed_parking_lots:
            raise HTTPException(status_code=403, detail="This parking lot is not available for the selected event")

        # Reservation window for events (e.g., within 30 minutes before event start)
        if now < event_start_time_aware - timedelta(minutes=30) or res_start_time_aware > event_start_time_aware:
            raise HTTPException(status_code=400, detail="Reservation for an event can only be made within 30 minutes before the event starts.")
    else:
        # General reservation time validation (e.g., not too far in the future, not in the past)

        # Localize reservation start time if naive
        if res.start_time.tzinfo is None:
            res_start_time_aware = pytz.utc.localize(res.start_time)
        else:
            res_start_time_aware = res.start_time.astimezone(pytz.utc)

        if res_start_time_aware < now:
            raise HTTPException(status_code=400, detail="Reservation start time cannot be in the past.")
        if res.end_time <= res.start_time:
            raise HTTPException(status_code=400, detail="Reservation end time must be after start time.")

    # Enforce VIP-only spot logic (Only VIP role can reserve VIP spots)
    if spot.is_vip and user.role != "vip":
        raise HTTPException(status_code=403, detail="Not authorized for VIP spot")

    # Check for reservation time overlap
    overlap = (
        db.query(Reservation)
        .filter(Reservation.spot_id == res.spot_id)
        .filter(Reservation.status.in_(["active", "pending"]))
        .filter(res.start_time < Reservation.end_time)
        .filter(res.end_time > Reservation.start_time)
        .first()
    )
    if overlap:
        raise HTTPException(status_code=400, detail="Spot already reserved in that period")

    # Check if spot is currently occupied by an active session
    current_session = db.query(ParkingSession).filter(
        ParkingSession.spot_id == res.spot_id,
        ParkingSession.check_out_time.is_(None)
    ).first()
    if current_session:
        raise HTTPException(status_code=400, detail="Spot is currently occupied by an active parking session.")

    # Create the reservation
    obj = Reservation(**res.model_dump(), status="pending")
    db.add(obj)
    db.commit()
    db.refresh(obj)

    # Update spot status if reserved
    spot.status = "occupied"
    db.add(spot)
    db.commit()
    db.refresh(spot)

    return obj

@router.post("/cancel", status_code=status.HTTP_200_OK)
def cancel_reservation(cancel_data: ReservationCancel, db: Session = Depends(get_db)):
    reservation = db.query(Reservation).filter(Reservation.id == cancel_data.reservation_id).first()

    if not reservation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found.")

    # Authorization check: only the user who made the reservation or an admin can cancel
    user = db.query(User).filter(User.id == cancel_data.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if reservation.user_id != user.id and user.role != "admin": # Assuming 'admin' role has override
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to cancel this reservation.")

    if reservation.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reservation is already cancelled.")

    if reservation.status == "active" and reservation.start_time < datetime.utcnow():
        # You might want to prevent cancellation of active reservations that have already started
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot cancel an active reservation that has already started.")

    reservation.status = "cancelled"
    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    # Optionally, update the spot status back to empty if it was reserved by this reservation
    spot = db.query(ParkingSpot).get(reservation.spot_id)
    if spot and spot.status == "occupied": # Or "reserved"
         # Check if there are other active reservations or sessions for this spot
        other_active_occupancies = db.query(Reservation).filter(
            Reservation.spot_id == spot.id,
            Reservation.status.in_(["active", "pending"]),
            Reservation.id != reservation.id, # Exclude the current cancelled reservation
            Reservation.end_time > datetime.utcnow()
        ).first() or db.query(ParkingSession).filter(
            ParkingSession.spot_id == spot.id,
            ParkingSession.check_out_time.is_(None)
        ).first()

        if not other_active_occupancies:
            spot.status = "empty"
            db.add(spot)
            db.commit()
            db.refresh(spot)

    return {"message": "Reservation cancelled successfully."}


@router.get("/user/{user_id}", response_model=list[ReservationRead])
def get_user_reservations(user_id: UUID, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return db.query(Reservation).filter(Reservation.user_id == user_id).all()

# New endpoint to get reservations with details
@router.get("/details", response_model=list[ReservationRead]) # Consider a more detailed schema if needed
def get_reservations_with_details(db: Session = Depends(get_db)):
    # This example returns basic reservation details. You'd typically use join loading
    # to include user, spot, and event details.
    return db.query(Reservation).all()