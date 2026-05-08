from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import ParkingSpot

router = APIRouter(prefix="/sensors", tags=["sensors"])

DEFAULT_OCCUPIED_THRESHOLD_CM = 50.0


class SensorReading(BaseModel):
    spot_number: str = Field(..., description="ParkingSpot.spot_number identifier")
    distance_cm: float = Field(..., ge=0, description="Distance reported by ultrasonic sensor")
    threshold_cm: Optional[float] = Field(
        None, description="Override occupancy threshold in cm; defaults to 50"
    )


class SensorReadingResponse(BaseModel):
    spot_number: str
    distance_cm: float
    threshold_cm: float
    status: str
    changed: bool


@router.post("/reading", response_model=SensorReadingResponse)
def ingest_sensor_reading(reading: SensorReading, db: Session = Depends(get_db)):
    spot = (
        db.query(ParkingSpot)
        .filter(ParkingSpot.spot_number == reading.spot_number)
        .first()
    )
    if not spot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No parking spot with spot_number={reading.spot_number}",
        )

    threshold = reading.threshold_cm or DEFAULT_OCCUPIED_THRESHOLD_CM
    desired_status = "occupied" if reading.distance_cm < threshold else "empty"

    # Don't override admin-managed states.
    if spot.status in ("reserved", "under_maintenance"):
        return SensorReadingResponse(
            spot_number=spot.spot_number,
            distance_cm=reading.distance_cm,
            threshold_cm=threshold,
            status=spot.status,
            changed=False,
        )

    changed = spot.status != desired_status
    if changed:
        spot.status = desired_status
        db.commit()
        db.refresh(spot)

    return SensorReadingResponse(
        spot_number=spot.spot_number,
        distance_cm=reading.distance_cm,
        threshold_cm=threshold,
        status=spot.status,
        changed=changed,
    )
