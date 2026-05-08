"""Seed real UZ Mt Pleasant parking zones and spots.

Idempotent: zones are looked up by name, spots by (zone, spot_number).
Re-running will not create duplicates and will not touch the existing
"Parklee Test Lot" / spot A12 used by the Arduino sensor demo.
"""

from database import SessionLocal, engine, Base
from models import ParkingZone, ParkingSpot

# Real coordinates around the University of Zimbabwe, Mt Pleasant campus.
ZONES = [
    {
        "name": "UZ Great Hall Lot",
        "zone_type": "staff",
        "latitude": -17.78369,
        "logitude": 31.05076,
        "spot_count": 10,
        "spot_prefix": "GH",
    },
    {
        "name": "UZ Faculty of Engineering Lot",
        "zone_type": "staff",
        "latitude": -17.78469,
        "logitude": 31.04885,
        "spot_count": 10,
        "spot_prefix": "EN",
    },
    {
        "name": "UZ Faculty of Medicine Parking",
        "zone_type": "staff",
        "latitude": -17.78700,
        "logitude": 31.05050,
        "spot_count": 10,
        "spot_prefix": "MD",
    },
    {
        "name": "UZ Student Union Lot",
        "zone_type": "student",
        "latitude": -17.78584,
        "logitude": 31.05213,
        "spot_count": 10,
        "spot_prefix": "SU",
    },
    {
        "name": "UZ Main Library Parking",
        "zone_type": "student",
        "latitude": -17.78445,
        "logitude": 31.05148,
        "spot_count": 10,
        "spot_prefix": "LB",
    },
    {
        "name": "UZ Sports Complex Lot",
        "zone_type": "general",
        "latitude": -17.78801,
        "logitude": 31.04880,
        "spot_count": 10,
        "spot_prefix": "SP",
    },
    {
        "name": "UZ Visitor Parking",
        "zone_type": "visitor",
        "latitude": -17.78366,
        "logitude": 31.05204,
        "spot_count": 10,
        "spot_prefix": "VP",
    },
]


def realistic_spot_attrs(zone_type: str, idx: int):
    """Return (spot_type, is_vip, status) for a given zone + index, mixing variety."""
    # First spot in staff/visitor zones reserved for disabled access.
    if idx == 1:
        spot_type = "disabled"
    elif zone_type in ("staff", "visitor") and idx == 2:
        spot_type = "reserved"
    else:
        spot_type = "regular"

    # A couple of VIP spots in staff zones.
    is_vip = zone_type == "staff" and idx in (3, 4)

    # Sprinkle realistic statuses so the dashboard isn't all empty.
    if idx % 5 == 0:
        status = "occupied"
    elif idx % 7 == 0:
        status = "under_maintenance"
    elif idx % 4 == 0:
        status = "reserved"
    else:
        status = "empty"

    return spot_type, is_vip, status


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    created_zones = 0
    updated_zones = 0
    created_spots = 0

    try:
        for z in ZONES:
            zone = db.query(ParkingZone).filter(ParkingZone.name == z["name"]).first()
            if zone is None:
                zone = ParkingZone(
                    name=z["name"],
                    zone_type=z["zone_type"],
                    latitude=z["latitude"],
                    logitude=z["logitude"],
                )
                db.add(zone)
                db.flush()
                created_zones += 1
            else:
                # Refresh coords/type if missing or different.
                changed = False
                if zone.latitude != z["latitude"]:
                    zone.latitude = z["latitude"]
                    changed = True
                if zone.logitude != z["logitude"]:
                    zone.logitude = z["logitude"]
                    changed = True
                if zone.zone_type != z["zone_type"]:
                    zone.zone_type = z["zone_type"]
                    changed = True
                if changed:
                    updated_zones += 1

            for i in range(1, z["spot_count"] + 1):
                spot_number = f"{z['spot_prefix']}{i:02d}"
                exists = (
                    db.query(ParkingSpot)
                    .filter(
                        ParkingSpot.parking_zone_id == zone.id,
                        ParkingSpot.spot_number == spot_number,
                    )
                    .first()
                )
                if exists:
                    continue
                spot_type, is_vip, status = realistic_spot_attrs(z["zone_type"], i)
                db.add(
                    ParkingSpot(
                        spot_number=spot_number,
                        lot_name=zone.name,
                        is_vip=is_vip,
                        spot_type=spot_type,
                        status=status,
                        parking_zone_id=zone.id,
                    )
                )
                created_spots += 1

        db.commit()
        print(
            f"Seed complete: {created_zones} zones created, {updated_zones} updated, "
            f"{created_spots} spots created."
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed()
