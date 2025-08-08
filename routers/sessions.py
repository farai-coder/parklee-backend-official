
from fastapi import APIRouter, Depends, HTTPException, status, APIRouter
from sqlalchemy.orm import Session
from database import SessionLocal
from models import ParkingSession, User, Reservation, ParkingSpot, ParkingZone, Report # Import Report
from schemas.sessionSchema import SessionCreate
from schemas.reportSchema import ReportCreate # Assuming you have a ReportCreate schema
from uuid import UUID
import datetime
from crud import get_available_spots # Assuming crud.py has this or similar logic
from database import get_db  # Assuming you have a get_db function to provide DB session 

  
router = APIRouter(prefix="/sessions", tags=["sessions"])    

def check_user_and_zone_rules(license_plate: str, spot_id: UUID, db: Session):
    user = db.query(User).filter(User.license_plate == license_plate).first()
    spot = db.query(ParkingSpot).filter(ParkingSpot.id == spot_id).first()

    if not user:
        # Report: Unauthorized license plate trying to park
        report = Report(
            license_plate=license_plate,
            report_type="unauthorized_parking",
            description=f"Unregistered license plate '{license_plate}' attempted to park at spot {spot_id}.",
            spot_id=spot_id
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        raise HTTPException(status_code=403, detail="License plate not recognized. Report generated.")

    if not spot:
        raise HTTPException(status_code=404, detail="Parking spot not found.")

    parking_zone = db.query(ParkingZone).filter(ParkingZone.id == spot.parking_zone_id).first()
    if not parking_zone:
        raise HTTPException(status_code=404, detail="Parking zone not found for this spot.")

    # Role-based parking zone restriction
    if user.role in ["staff", "student", "visitor"] and parking_zone.zone_type != user.role:
        if parking_zone.zone_type != "general": # Allow 'general' zones for everyone
            # Report: Wrong zone entry
            report = Report(
                user_id=user.id,
                license_plate=license_plate,
                spot_id=spot_id,
                zone_id=parking_zone.id,
                report_type="wrong_zone_entry",
                description=f"User '{user.email}' (Role: {user.role}) attempted to park in restricted zone '{parking_zone.name}' (Type: {parking_zone.zone_type})."
            )
            db.add(report)
            db.commit()
            db.refresh(report)
            raise HTTPException(status_code=403, detail=f"You are not authorized to park in this zone. Report generated.")

    # Check for active reservation for this user and spot
    active_reservation = db.query(Reservation).filter(
        Reservation.user_id == user.id,
        Reservation.spot_id == spot_id,
        Reservation.start_time <= datetime.utcnow(),
        Reservation.end_time >= datetime.utcnow(),
        Reservation.status == "active"
    ).first()

    if not active_reservation:
        # If no active reservation, check if the spot is 'reserved' type for a general park
        if spot.spot_type == "reserved" and not user.role == "admin": # Admins might override
             raise HTTPException(status_code=403, detail="This is a reserved spot and you do not have an active reservation.")

    return user, spot, parking_zone, active_reservation


@router.post("/check-in", response_model=SessionCreate)
def check_in(s: SessionCreate, db: Session = Depends(get_db)):
    user, spot, zone, active_reservation = check_user_and_zone_rules(s.license_plate, s.spot_id, db)

    # Check for active session for this user or spot
    existing_session_for_user = db.query(ParkingSession).filter(
        ParkingSession.user_id == user.id,
        ParkingSession.check_out_time.is_(None)
    ).first()
    if existing_session_for_user:
        raise HTTPException(status_code=400, detail="User already has an active parking session.")

    existing_session_for_spot = db.query(ParkingSession).filter(
        ParkingSession.spot_id == s.spot_id,
        ParkingSession.check_out_time.is_(None)
    ).first()
    if existing_session_for_spot:
        raise HTTPException(status_code=400, detail="Spot is already occupied by another session.")

    # Ensure spot is available (not occupied by reservation or other means)
    # This logic might be slightly redundant with check_user_and_zone_rules and available-spots,
    # but good to re-confirm before creating session.
    # It's better to update spot status to "occupied" immediately on check-in.
    if spot.status != "empty":
        raise HTTPException(status_code=400, detail=f"Spot is not available for check-in. Current status: {spot.status}")

    # Create the parking session
    db_session = ParkingSession(
        user_id=user.id,
        spot_id=s.spot_id,
        check_in_time=datetime.utcnow()
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    # Update spot status to 'occupied'
    spot.status = "occupied"
    db.add(spot)
    db.commit()
    db.refresh(spot)

    return db_session


@router.post("/check-out", status_code=status.HTTP_200_OK)
def check_out(session_id: UUID, db: Session = Depends(get_db)):
    ses = db.query(ParkingSession).get(session_id)
    if not ses or ses.check_out_time is not None:
        raise HTTPException(status_code=404, detail="Active session not found or already checked out.")

    ses.check_out_time = datetime.utcnow()
    db.add(ses)
    db.commit()
    db.refresh(ses)

    # Update the spot status to 'empty'
    spot = db.query(ParkingSpot).get(ses.spot_id)
    if spot:
        # Before setting to empty, check if there's an overlapping reservation that needs to occupy it
        now = datetime.utcnow()
        overlapping_reservation = db.query(Reservation).filter(
            Reservation.spot_id == spot.id,
            Reservation.status == "active",
            Reservation.start_time <= now,
            Reservation.end_time > now
        ).first()

        if overlapping_reservation:
            spot.status = "reserved" # Or 'occupied' by reservation
        else:
            spot.status = "empty"
        db.add(spot)
        db.commit()
        db.refresh(spot)

    return {"message": "Checked out successfully."}