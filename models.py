import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, DateTime,
    Enum, ForeignKey, Boolean
)
from sqlalchemy.dialects.postgresql import UUID
from database import Base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.sqlite import JSON

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    surname = Column(String, nullable=False)
    gender = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    license_plate = Column(String, unique=True, index=True, nullable=False)
    role = Column(Enum("student", "staff", "admin", "visitor", name="user_roles"), default="student", nullable=False)
    password = Column(String, nullable=True)
    status = Column(Enum("active", "inactive", "pending", "disabled", name="user_status"), default="active", nullable=False)

    reservations = relationship("Reservation", back_populates="user")
    parking_sessions = relationship("ParkingSession", back_populates="user")
    reports = relationship("Report", back_populates="user")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
    
    # This line was added to fix the error
    verification_codes = relationship("VerificationCode", back_populates="user")

class ParkingZone(Base):
    __tablename__ = "parking_zones"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    # spot_numbers will be inferred from relationship to ParkingSpot
    zone_type = Column(Enum("staff", "student", "visitor", "general", name="zone_types"), default="general", nullable=False)

    parking_spots = relationship("ParkingSpot", back_populates="parking_zone")


class ParkingSpot(Base):
    __tablename__ = "parking_spots"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    spot_number = Column(String, nullable=False)
    lot_name = Column(String, nullable=False) # Still relevant for general location
    is_vip = Column(Boolean, default=False) # New VIP field
    spot_type = Column(Enum("reserved", "regular", "disabled", name="spot_types"), default="regular", nullable=False) # Updated spot type
    status = Column(Enum("reserved","occupied", "empty", "under_maintenance", name="spot_status"), default="empty", nullable=False) # New status field
    parking_zone_id = Column(UUID(as_uuid=True), ForeignKey("parking_zones.id"), nullable=False)

    parking_zone = relationship("ParkingZone", back_populates="parking_spots")
    reservations = relationship("Reservation", back_populates="parking_spot")
    parking_sessions = relationship("ParkingSession", back_populates="parking_spot")


class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    spot_id = Column(UUID(as_uuid=True), ForeignKey("parking_spots.id"), nullable=False)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=True) # Reservation for an event or general
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(Enum("pending", "active", "completed", "cancelled", name="reservation_status"), default="pending", nullable=False) # New reservation status

    user = relationship("User", back_populates="reservations")
    parking_spot = relationship("ParkingSpot", back_populates="reservations")
    event = relationship("Events", back_populates="reservations")


class ParkingSession(Base):
    __tablename__ = "parking_sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    spot_id = Column(UUID(as_uuid=True), ForeignKey("parking_spots.id"), nullable=False)
    check_in_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    check_out_time = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="parking_sessions")
    parking_spot = relationship("ParkingSpot", back_populates="parking_sessions")


class Events(Base):
    __tablename__ = "events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    date = Column(DateTime, nullable=False)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    event_location = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    allowed_parking_lots = Column(JSON, nullable=True) # Assuming this is a list of allowed lot names

    reservations = relationship("Reservation", back_populates="event")


class Report(Base):
    __tablename__ = "reports"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True) # User who made the report, if any
    license_plate = Column(String, nullable=True) # License plate involved
    spot_id = Column(UUID(as_uuid=True), ForeignKey("parking_spots.id"), nullable=True) # Spot related to the report
    zone_id = Column(UUID(as_uuid=True), ForeignKey("parking_zones.id"), nullable=True) # Zone related to the report
    report_type = Column(Enum("wrong_zone_entry", "overstay", "unauthorized_parking", "other", name="report_types"), nullable=False)
    description = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(Enum("pending", "resolved", "dismissed", name="report_status"), default="pending", nullable=False)

    user = relationship("User", back_populates="reports")
    parking_spot = relationship("ParkingSpot") # No back_populates needed if not frequently accessed from spot
    parking_zone = relationship("ParkingZone") # No back_populates needed

class VerificationCode(Base):
    __tablename__ = "verification_codes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    code = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="verification_codes")