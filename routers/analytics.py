from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, not_, func, cast, Date, or_
from sqlalchemy.orm import Session, joinedload
from database import SessionLocal
from models import ParkingSession, ParkingSpot, Reservation, User, ParkingZone, Events # Import new models
from uuid import UUID
from typing import List, Dict, Any
from database import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Existing: Number of available spots (updated to consider new statuses)
@router.get("/spots_count", response_model=int)
def spots_count(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    # Spots currently checked in
    occupied_by_sessions = (
        db.query(ParkingSession.spot_id)
          .filter(ParkingSession.check_out_time.is_(None))
    ).subquery()

    # Spots currently reserved
    reserved_now = (
        db.query(Reservation.spot_id)
          .filter(and_(Reservation.start_time <= now,
                       Reservation.end_time > now,
                       Reservation.status.in_(["active", "pending"]))) # Only active/pending reservations
    ).subquery()

    # Spots explicitly marked as occupied or under maintenance
    unavailable_by_status = db.query(ParkingSpot.id).filter(
        ParkingSpot.status.in_(["occupied", "under_maintenance"])
    ).subquery()

    return (
        db.query(ParkingSpot)
          .filter(not_(ParkingSpot.id.in_(occupied_by_sessions)))
          .filter(not_(ParkingSpot.id.in_(reserved_now)))
          .filter(not_(ParkingSpot.id.in_(unavailable_by_status)))
          .count()
    )

# Existing: Get the number of parking zones
@router.get("/zones_count", response_model=int)
def zones_count(db: Session = Depends(get_db)):
    return db.query(ParkingZone).count() # Changed to count from ParkingZone table

# Existing: Get the number of users
@router.get("/users_count", response_model=int)
def users_count(db: Session = Depends(get_db)):
    return db.query(User).count()

# Existing: Total reservations count
@router.get("/reservations_count", response_model=int)
def reservations_count(db: Session = Depends(get_db)):
    return db.query(Reservation).count()


# --- New Analytics Endpoints ---

## Parking Zone Analytics
@router.get("/zones/occupancy_rate", response_model=Dict[str, float])
def get_zone_occupancy_rate(db: Session = Depends(get_db)):
    zones = db.query(ParkingZone).all()
    occupancy_rates = {}
    now = datetime.utcnow()

    for zone in zones:
        total_spots_in_zone = db.query(ParkingSpot).filter(ParkingSpot.parking_zone_id == zone.id).count()

        if total_spots_in_zone == 0:
            occupancy_rates[zone.name] = 0.0
            continue

        # Spots in this zone that are currently occupied by a session
        occupied_by_sessions = db.query(ParkingSession.spot_id).join(ParkingSpot).filter(
            ParkingSpot.parking_zone_id == zone.id,
            ParkingSession.check_out_time.is_(None)
        ).count()

        # Spots in this zone that are currently reserved (active/pending within time frame)
        reserved_now = db.query(Reservation.spot_id).join(ParkingSpot).filter(
            ParkingSpot.parking_zone_id == zone.id,
            Reservation.start_time <= now,
            Reservation.end_time > now,
            Reservation.status.in_(["active", "pending"])
        ).count()

        # Spots explicitly marked as occupied or under maintenance in this zone
        unavailable_by_status = db.query(ParkingSpot.id).filter(
            ParkingSpot.parking_zone_id == zone.id,
            ParkingSpot.status.in_(["occupied", "under_maintenance"])
        ).count()

        # Sum unique occupied spots
        occupied_spot_ids = set()
        occupied_spot_ids.update([s.spot_id for s in db.query(ParkingSession.spot_id).join(ParkingSpot).filter(
            ParkingSpot.parking_zone_id == zone.id,
            ParkingSession.check_out_time.is_(None)
        ).all()])
        occupied_spot_ids.update([r.spot_id for r in db.query(Reservation.spot_id).join(ParkingSpot).filter(
            ParkingSpot.parking_zone_id == zone.id,
            Reservation.start_time <= now,
            Reservation.end_time > now,
            Reservation.status.in_(["active", "pending"])
        ).all()])
        occupied_spot_ids.update([s.id for s in db.query(ParkingSpot).filter(
            ParkingSpot.parking_zone_id == zone.id,
            ParkingSpot.status.in_(["occupied", "under_maintenance"])
        ).all()])


        current_occupied_count = len(occupied_spot_ids)
        occupancy_rate = (current_occupied_count / total_spots_in_zone) * 100
        occupancy_rates[zone.name] = round(occupancy_rate, 2)

    return occupancy_rates


@router.get("/zones/spot_distribution", response_model=Dict[str, Dict[str, int]])
def get_zone_spot_distribution(db: Session = Depends(get_db)):
    # Counts spots by zone and then by spot_type (student, visitor, staff, disabled)
    result = db.query(
        ParkingZone.name,
        ParkingSpot.spot_type,
        func.count(ParkingSpot.id)
    ).join(ParkingSpot).group_by(
        ParkingZone.name, ParkingSpot.spot_type
    ).all()

    distribution = {}
    for zone_name, spot_type, count in result:
        if zone_name not in distribution:
            distribution[zone_name] = {}
        distribution[zone_name][spot_type] = count
    return distribution


@router.get("/zones/{zone_id}/spots/details", response_model=List[Dict[str, Any]])
def get_spots_with_details_by_zone(zone_id: UUID, db: Session = Depends(get_db)):
    spots = db.query(ParkingSpot).filter(ParkingSpot.parking_zone_id == zone_id).all()
    if not spots:
        []

    spot_details = []
    for spot in spots:
        current_session = db.query(ParkingSession).filter(
            ParkingSession.spot_id == spot.id,
            ParkingSession.check_out_time.is_(None)
        ).first()
        current_reservation = db.query(Reservation).filter(
            Reservation.spot_id == spot.id,
            Reservation.start_time <= datetime.utcnow(),
            Reservation.end_time > datetime.utcnow(),
            Reservation.status.in_(["active", "pending"])
        ).first()

        details = {
            "id": spot.id,
            "spot_number": spot.spot_number,
            "lot_name": spot.lot_name,
            "is_vip": spot.is_vip,
            "spot_type": spot.spot_type,
            "status": spot.status, # Current status from DB
            "occupied_by_session": bool(current_session),
            "reserved_now": bool(current_reservation),
            "current_user_email": current_session.user.email if current_session and current_session.user else None,
            "reservation_user_email": current_reservation.user.email if current_reservation and current_reservation.user else None,
        }
        spot_details.append(details)
    return spot_details

@router.get("/trend/daily", response_model=Dict[str, int])
def get_daily_reservation_count(db: Session = Depends(get_db), days: int = 7):
    """
    Counts reservations per day for the last 'days', handling timezone differences.
    """
    # Define the end of the period as the start of the next day in UTC
    end_of_day = datetime.utcnow().date() + timedelta(days=1)
    
    # Define the start of the period
    start_of_period = end_of_day - timedelta(days=days)

    result = db.query(
        func.date(Reservation.start_time),
        func.count(Reservation.id)
    ).filter(
        # Use a proper datetime range filter to include all times within the dates
        Reservation.start_time >= start_of_period,
        Reservation.start_time < end_of_day
    ).group_by(
        func.date(Reservation.start_time)
    ).order_by(
        func.date(Reservation.start_time)
    ).all()

    # Create a dictionary with a default count of 0 for each day in the range
    daily_counts = {(end_of_day - timedelta(days=i+1)).isoformat(): 0 for i in range(days)}

    # Fill in the actual counts from the query result
    for res_date, count in result:
        daily_counts[res_date] = count

    return daily_counts


@router.get("/reservations/status_counts", response_model=Dict[str, int])
def get_reservation_status_counts(db: Session = Depends(get_db)):
    result = db.query(
        Reservation.status,
        func.count(Reservation.id)
    ).group_by(
        Reservation.status
    ).all()
    return {status: count for status, count in result}

@router.get("/reservations/details", response_model=List[Dict[str, Any]])
def get_all_reservations_with_details(db: Session = Depends(get_db)):
    reservations = db.query(Reservation).options(
        joinedload(Reservation.user),
        joinedload(Reservation.parking_spot),
        joinedload(Reservation.event)
    ).all()

    detailed_reservations = []
    for res in reservations:
        detailed_reservations.append({
            "id": res.id,
            "start_time": res.start_time,
            "end_time": res.end_time,
            "status": res.status,
            "user": {
                "id": res.user.id,
                "email": res.user.email,
                "name": f"{res.user.name} {res.user.surname}",
                "role": res.user.role,
                "license_plate": res.user.license_plate
            } if res.user else None,
            "parking_spot": {
                "id": res.parking_spot.id,
                "spot_number": res.parking_spot.spot_number,
                "lot_name": res.parking_spot.lot_name,
                "spot_type": res.parking_spot.spot_type
            } if res.parking_spot else None,
            "event": {
                "id": res.event.id,
                "name": res.event.name,
                "date": res.event.date
            } if res.event else None,
        })
    return detailed_reservations


## Overall Parking System Analytics
@router.get("/total_spots", response_model=int)
def get_total_spots(db: Session = Depends(get_db)):
    return db.query(ParkingSpot).count()

@router.get("/peak_hours_occupancy", response_model=Dict[str, float])
def get_peak_hours_occupancy(db: Session = Depends(get_db), period_days: int = 30):
    # Analyze check-in and check-out times over a period to find peak hours
    start_date = datetime.utcnow() - timedelta(days=period_days)

    # Count active sessions per hour
    hourly_occupancy_counts = db.query(
        func.strftime("%H", ParkingSession.check_in_time), # Extract hour
        func.count(ParkingSession.id)
    ).filter(
        ParkingSession.check_in_time >= start_date,
        ParkingSession.check_out_time.is_(None) # Only active sessions
    ).group_by(
        func.strftime("%H", ParkingSession.check_in_time)
    ).order_by(
        func.strftime("%H", ParkingSession.check_in_time)
    ).all()

    # Also consider reservations that are active during certain hours
    # This is more complex as reservations span periods. For simplicity, we can count reservations
    # that are active at the start of each hour.
    hourly_reservation_counts = {}
    for hour in range(24):
        hourly_reservation_counts[f"{hour:02d}"] = db.query(Reservation).filter(
            Reservation.status.in_(["active", "pending"]),
            Reservation.start_time >= start_date,
            func.strftime("%H", Reservation.start_time) == f"{hour:02d}"
        ).count() # This is a simplification; a full solution would check overlap for *all* reservations

    # Combine and normalize
    combined_hourly_counts = {str(h).zfill(2): 0 for h in range(24)}
    for hour, count in hourly_occupancy_counts:
        combined_hourly_counts[hour] += count
    for hour, count in hourly_reservation_counts.items():
        combined_hourly_counts[hour] += count

    total_possible_spots = db.query(ParkingSpot).count()
    if total_possible_spots == 0:
        return {hour: 0.0 for hour in combined_hourly_counts}

    peak_occupancy = {}
    for hour, count in combined_hourly_counts.items():
        peak_occupancy[hour] = round((count / total_possible_spots) * 100, 2)

    return peak_occupancy

@router.get("/hourly_occupancy_trend", response_model=Dict[str, float])
def get_hourly_occupancy_trend(db: Session = Depends(get_db), hours_back: int = 24):
    now = datetime.utcnow()
    hourly_trend = {}

    for i in range(hours_back):
        current_time_slot_end = now - timedelta(hours=i)
        current_time_slot_start = current_time_slot_end - timedelta(hours=1)

        # Count active sessions in this hour slot
        sessions_in_slot = db.query(ParkingSession).filter(
            ParkingSession.check_in_time <= current_time_slot_end,
            or_(
                ParkingSession.check_out_time >= current_time_slot_start,
                ParkingSession.check_out_time.is_(None) # Still active
            )
        ).count()

        # Count active reservations in this hour slot
        reservations_in_slot = db.query(Reservation).filter(
            Reservation.status.in_(["active", "pending"]),
            Reservation.start_time <= current_time_slot_end,
            Reservation.end_time >= current_time_slot_start
        ).count()

        total_occupied = sessions_in_slot + reservations_in_slot
        total_spots = db.query(ParkingSpot).count()

        if total_spots == 0:
            occupancy_rate = 0.0
        else:
            occupancy_rate = (total_occupied / total_spots) * 100

        hourly_trend[current_time_slot_start.strftime("%Y-%m-%d %H:00")] = round(occupancy_rate, 2)

    return dict(sorted(hourly_trend.items())) # Sort by time


## User-specific Analytics (Staff, Student, Visitor)
@router.get("/users/spot_distribution_by_role", response_model=Dict[str, Dict[str, int]])
def get_spot_distribution_by_role(db: Session = Depends(get_db)):
    # Counts how many spots are associated with each user role (via active sessions)
    result = db.query(
        User.role,
        ParkingSpot.spot_type,
        func.count(ParkingSpot.id)
    ).join(ParkingSession, ParkingSession.user_id == User.id).join(ParkingSpot, ParkingSession.spot_id == ParkingSpot.id).filter(
        ParkingSession.check_out_time.is_(None)
    ).group_by(
        User.role, ParkingSpot.spot_type
    ).all()

    distribution = {}
    for role, spot_type, count in result:
        if role not in distribution:
            distribution[role] = {}
        distribution[role][spot_type] = count
    return distribution


@router.get("/events/distribution_trend_by_month", response_model=Dict[str, int])
def get_event_distribution_by_month(db: Session = Depends(get_db)):
    result = db.query(
        func.strftime("%Y-%m", Events.date),
        func.count(Events.id)
    ).group_by(
        func.strftime("%Y-%m", Events.date)
    ).order_by(
        func.strftime("%Y-%m", Events.date)
    ).all()
    return {month: count for month, count in result}

@router.get("/events/parking_demand_by_event", response_model=List[Dict[str, Any]])
def get_parking_demand_by_event(db: Session = Depends(get_db)):
    result = db.query(
        Events.name,
        func.count(Reservation.id)
    ).outerjoin(Reservation, Events.id == Reservation.event_id).group_by(
        Events.name
    ).order_by(
        Events.name
    ).all()

    demand = []
    for event_name, reservation_count in result:
        # Also include how many spots are *allowed* for this event to compare demand vs supply
        event_obj = db.query(Events).filter(Events.name == event_name).first()
        allowed_spots_count = 0
        if event_obj and event_obj.allowed_parking_lots:
            allowed_spots_count = db.query(ParkingSpot).filter(
                ParkingSpot.lot_name.in_(event_obj.allowed_parking_lots)
            ).count()

        demand.append({
            "event_name": event_name,
            "total_reservations": reservation_count,
            "allowed_parking_spots_count": allowed_spots_count
        })
    return demand

# Get events with details (e.g., associated reservations)
@router.get("/events/details", response_model=List[Dict[str, Any]])
def get_events_with_details(db: Session = Depends(get_db)):
    events = db.query(Events).options(joinedload(Events.reservations)).all()
    detailed_events = []
    for event in events:
        detailed_events.append({
            "id": event.id,
            "name": event.name,
            "description": event.description,
            "date": event.date,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "event_location": event.event_location,
            "total_reservations": len(event.reservations)
        })
    return detailed_events

@router.get("/occupied_spots_count", response_model=int)
def get_occupied_spots_count(db: Session = Depends(get_db)):
    """
    Returns the total number of parking spots currently occupied.
    An occupied spot is defined as a ParkingSession with a check_out_time of None.
    """
    count = (
        db.query(ParkingSession)
        .filter(ParkingSession.check_out_time.is_(None))
        .count()
    )
    return count


@router.get("/api/events")
def get_events(db: Session = Depends(get_db)):
    """
    Retrieves all events from the database.
    """
    events = db.query(Events).all()
    return events

@router.get("/api/analytics/events/distribution_by_type", response_model=Dict[str, int])
def get_event_distribution(db: Session = Depends(get_db)):
    """
    Counts the number of events for each event type, returning 0 for types with no events.
    """
    # A list of all possible event types
    all_event_types = ["academic", "sports", "cultural", "official"]

    # Initialize a dictionary with a count of 0 for each type
    result = {event_type: 0 for event_type in all_event_types}

    # Query the database to get the actual counts
    distribution = db.query(
        Events.event_type,
        func.count(Events.id)
    ).group_by(Events.event_type).all()

    # Update the result dictionary with the counts from the database
    for event_type, count in distribution:
        result[event_type] = count

    return result

@router.get("/api/analytics/events/trend_by_month")
def get_monthly_event_trend(db: Session = Depends(get_db)):
    """
    Counts events per month for each type over the last 6 months.
    """
    today = datetime.now()
    start_date = today - timedelta(days=180)
    
    events_in_range = db.query(Events).filter(Events.start_time >= start_date).all()
    
    monthly_data = {}
    for i in range(6):
        month_date = today - timedelta(days=(5-i)*30) # Approx. month calculation
        month_label = month_date.strftime("%b")
        monthly_data[month_label] = {
            "academic": 0, "sports": 0, "cultural": 0, "official": 0
        }

    for event in events_in_range:
        month_label = event.start_time.strftime("%b")
        if month_label in monthly_data and event.event_type in monthly_data[month_label]:
            monthly_data[month_label][event.event_type] += 1
            
    # Format for the frontend line chart
    academic_data = [monthly_data[month]["academic"] for month in monthly_data]
    sports_data = [monthly_data[month]["sports"] for month in monthly_data]
    cultural_data = [monthly_data[month]["cultural"] for month in monthly_data]
    official_data = [monthly_data[month]["official"] for month in monthly_data]

    return {
        "months": list(monthly_data.keys()),
        "academic": academic_data,
        "sports": sports_data,
        "cultural": cultural_data,
        "official": official_data,
    }

@router.get("/api/analytics/events/parking_demand")
def get_parking_demand(db: Session = Depends(get_db)):
    """
    Calculates average and max reservations per event type.
    """
    # Query to get the total reservations for each event
    total_reservations_per_event = db.query(
        Events.id,
        Events.event_type,
        func.count(Reservation.id).label('reservation_count')
    ).outerjoin(Reservation, Events.id == Reservation.event_id).group_by(
        Events.id, Events.event_type
    ).all()

    # Process the results to group by event type
    reservations_by_type = {
        'academic': [],
        'sports': [],
        'cultural': [],
        'official': []
    }
    for event_id, event_type, count in total_reservations_per_event:
        if event_type in reservations_by_type:
            reservations_by_type[event_type].append(count)

    # Calculate average and max for each event type
    avg_result = {}
    max_result = {}
    for event_type, counts in reservations_by_type.items():
        if counts:
            avg_result[event_type] = round(sum(counts) / len(counts), 2)
            max_result[event_type] = max(counts)
        else:
            avg_result[event_type] = 0.0
            max_result[event_type] = 0

    event_types = ['academic', 'sports', 'cultural', 'official']
    
    # Map results to the required frontend format
    formatted_avg = [avg_result.get(type, 0.0) for type in event_types]
    formatted_max = [max_result.get(type, 0) for type in event_types]

    return {
        "event_types": event_types,
        "average_reservations": formatted_avg,
        "max_reservations": formatted_max,
    }
    
@router.get("/api/analytics/events/count")
def get_event_count(db: Session = Depends(get_db)):
    """
    Returns the total number of events in the database.
    """
    count = db.query(func.count(Events.id)).scalar()
    
    return {"total_events": count}