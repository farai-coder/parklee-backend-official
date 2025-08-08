import datetime
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, not_
import csv
from uuid import UUID

from schemas.auth_schema import SuccessMessage
from schemas.parkingzone_schema import ParkingZoneCreate, ParkingZoneRead, ParkingSpotCreate, ParkingSpotRead, ParkingSpotUpdate
from database import SessionLocal
from models import ParkingSession, ParkingSpot, Reservation, ParkingZone, User
from database import get_db  # Assuming you have a get_db function to provide DB session    

router = APIRouter(prefix="/spots", tags=["spots"])

# --- Parking Zone Endpoints (Admin Only) ---
@router.post("/zones/", response_model=SuccessMessage, status_code=status.HTTP_201_CREATED)
def create_parking_zone(zone_in: ParkingZoneCreate, db: Session = Depends(get_db)):
    existing_zone = db.query(ParkingZone).filter(ParkingZone.name == zone_in.name).first()
    if existing_zone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parking zone with this name already exists")
    db_zone = ParkingZone(**zone_in.model_dump())
    db.add(db_zone)
    db.commit()
    db.refresh(db_zone)
    return SuccessMessage(message="Parking zone created successfully", data=db_zone)

@router.put("/zones/{zone_id}", response_model=ParkingZoneRead)
def update_parking_zone(zone_id: UUID, zone_update: ParkingZoneCreate, db: Session = Depends(get_db)):
    db_zone = db.query(ParkingZone).filter(ParkingZone.id == zone_id).first()
    if not db_zone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking zone not found")
    for key, value in zone_update.model_dump(exclude_unset=True).items():
        setattr(db_zone, key, value)
    db.commit()
    db.refresh(db_zone)
    return db_zone

@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_parking_zone(zone_id: UUID, db: Session = Depends(get_db)):
    db_zone = db.query(ParkingZone).filter(ParkingZone.id == zone_id).first()
    if not db_zone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking zone not found")
    db.delete(db_zone)
    db.commit()
    return {"message": "Parking zone deleted successfully"}

@router.get("/zones/{zone_id}/spots", response_model=list[ParkingSpotRead])
def get_spots_by_zone_id(zone_id: UUID, db: Session = Depends(get_db)):
    zone = db.query(ParkingZone).filter(ParkingZone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking zone not found")
    return db.query(ParkingSpot).filter(ParkingSpot.parking_zone_id == zone_id).all()

# --- Parking Spot Endpoints (Admin Only for Create/Edit/Delete) ---
@router.post("/bulk-upload", status_code=status.HTTP_201_CREATED)
def bulk_create_spots_from_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    content = file.file.read().decode()
    reader = csv.DictReader(content.splitlines())

    created_spots = []
    zone_cache = {}

    for row in reader:
        spot_number = row.get("spot_number")
        spot_type = row.get("spot_type")
        is_vip = row.get("is_vip", "false").lower() == "true"
        zone_name = row.get("parking_zone_name")
        zone_type = row.get("zone_type", "general")

        if not all([spot_number, spot_type, zone_name]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV must contain 'spot_number', 'spot_type', 'parking_zone_name' columns.")

        if zone_name not in zone_cache:
            zone = db.query(ParkingZone).filter(ParkingZone.name == zone_name).first()
            if not zone:
                zone = ParkingZone(name=zone_name, zone_type=zone_type)
                db.add(zone)
                db.flush()
            zone_cache[zone_name] = zone
        else:
            zone = zone_cache[zone_name]

        spot = ParkingSpot(
            spot_number=spot_number,
            lot_name=zone.name,
            is_vip=is_vip,
            spot_type=spot_type,
            parking_zone_id=zone.id,
            status="empty"
        )
        created_spots.append(spot)

    db.add_all(created_spots)
    db.commit()
    for spot in created_spots:
        db.refresh(spot)

    return {"message": f"{len(created_spots)} parking spots created, zones auto-created if needed."}

@router.post("/spots/", response_model=SuccessMessage, status_code=status.HTTP_201_CREATED)
def create_parking_spot(spot_in: ParkingSpotCreate, db: Session = Depends(get_db)):
    zone = db.query(ParkingZone).filter(ParkingZone.id == spot_in.parking_zone_id).first()
    if not zone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking zone not found")

    db_spot = ParkingSpot(**spot_in.model_dump(), status="empty")
    db.add(db_spot)
    db.commit()
    db.refresh(db_spot)
    return SuccessMessage(message="Parking spot created successfully", data=db_spot)

@router.put("/spots/{spot_id}", response_model=ParkingSpotRead)
def update_parking_spot(spot_id: UUID, spot_update: ParkingSpotUpdate, db: Session = Depends(get_db)):
    db_spot = db.query(ParkingSpot).filter(ParkingSpot.id == spot_id).first()
    if not db_spot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking spot not found")
    for key, value in spot_update.model_dump(exclude_unset=True).items():
        setattr(db_spot, key, value)
    db.commit()
    db.refresh(db_spot)
    return db_spot

@router.delete("/spots/{spot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_parking_spot(spot_id: UUID, db: Session = Depends(get_db)):
    db_spot = db.query(ParkingSpot).filter(ParkingSpot.id == spot_id).first()
    if not db_spot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking spot not found")
    db.delete(db_spot)
    db.commit()
    return {"message": "Parking spot deleted successfully"}

# New endpoint to get all parking zones
@router.get("/zones/", response_model=list[ParkingZoneRead])
def get_all_parking_zones(db: Session = Depends(get_db)):
    zones = db.query(ParkingZone).all()
    return zones


@router.get("/available-spots", response_model=list[ParkingSpotRead])
def get_available_spots(db: Session = Depends(get_db)):
    now = datetime.datetime.utcnow()
    # Occupied spots from active sessions
    occupied_by_sessions = (
        db.query(ParkingSession.spot_id)
          .filter(ParkingSession.check_out_time.is_(None))
    ).subquery()

    # Occupied spots from active reservations
    reserved_now = (
        db.query(Reservation.spot_id)
          .filter(and_(Reservation.start_time <= now,
                       Reservation.end_time > now,
                       Reservation.status == "active"))
    ).subquery()

    # Spots that are explicitly marked as occupied or under maintenance
    unavailable_by_status = db.query(ParkingSpot.id).filter(
        ParkingSpot.status.in_(["occupied", "under_maintenance"])
    ).subquery()


    # Filter out spots that are occupied by sessions, reserved, or explicitly unavailable by status
    available_spots = (
        db.query(ParkingSpot)
          .filter(not_(ParkingSpot.id.in_(occupied_by_sessions)))
          .filter(not_(ParkingSpot.id.in_(reserved_now)))
          .filter(not_(ParkingSpot.id.in_(unavailable_by_status)))
          .all()
    )
    return available_spots