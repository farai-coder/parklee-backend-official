from datetime import datetime, timedelta
import pytz

class ReservationValidationError(Exception):
    pass

class ReservationValidator:
    def __init__(
        self,
        user_role: str,
        spot_is_vip: bool,
        parking_zone_type: str,
        existing_reservations_statuses: list,
        spot_currently_occupied: bool,
        res_start_time: datetime,
        res_end_time: datetime,
        now: datetime = None,
        event_start_time: datetime = None,
        event_allowed_parking_lots: list = None,
        spot_lot_name: str = None
    ):
        self.user_role = user_role
        self.spot_is_vip = spot_is_vip
        self.parking_zone_type = parking_zone_type
        self.existing_reservations_statuses = existing_reservations_statuses
        self.spot_currently_occupied = spot_currently_occupied
        self.res_start_time = self._make_aware(res_start_time)
        self.res_end_time = self._make_aware(res_end_time)
        self.now = self._make_aware(now or datetime.utcnow())
        self.event_start_time = self._make_aware(event_start_time) if event_start_time else None
        self.event_allowed_parking_lots = event_allowed_parking_lots or []
        self.spot_lot_name = spot_lot_name

    def _make_aware(self, dt):
        if dt.tzinfo is None:
            return pytz.utc.localize(dt)
        else:
            return dt.astimezone(pytz.utc)

    def print_times(self):
        print(f"Current UTC now: {self.now}")
        if self.event_start_time:
            print(f"Event start time (UTC): {self.event_start_time}")
            print(f"Event start time minus 30 minutes: {self.event_start_time - timedelta(minutes=30)}")
        print(f"Requested reservation start time (UTC): {self.res_start_time}")
        print(f"Requested reservation end time (UTC): {self.res_end_time}")

    def validate(self):
        self.print_times()

        # Check existing active or pending reservations
        if any(status in ["active", "pending"] for status in self.existing_reservations_statuses):
            raise ReservationValidationError("User already has an active or pending reservation.")

        # Role-based parking zone restriction
        if self.user_role in ["staff", "student", "visitor"] and self.parking_zone_type != self.user_role:
            if self.parking_zone_type != "general":
                raise ReservationValidationError(f"User with role '{self.user_role}' is not allowed to park in '{self.parking_zone_type}' zones.")

        # Event-specific checks
        if self.event_start_time:
            if self.event_allowed_parking_lots and self.spot_lot_name not in self.event_allowed_parking_lots:
                raise ReservationValidationError("This parking lot is not available for the selected event.")

            # Reservation time window: must be within 30 min before event start (relative to current time now)
            if self.now < self.event_start_time - timedelta(minutes=30) or self.res_start_time > self.event_start_time:
                raise ReservationValidationError("Reservation for an event can only be made within 30 minutes before the event starts.")

        else:
            # General reservation time checks
            if self.res_start_time < self.now:
                raise ReservationValidationError("Reservation start time cannot be in the past.")
            if self.res_end_time <= self.res_start_time:
                raise ReservationValidationError("Reservation end time must be after start time.")

        # VIP spot check
        if self.spot_is_vip and self.user_role != "vip":
            raise ReservationValidationError("Not authorized for VIP spot.")

        # Spot occupancy check
        if self.spot_currently_occupied:
            raise ReservationValidationError("Spot is currently occupied by an active parking session.")

        print("Validation passed successfully.")
        return True


try:
    # Define test inputs:
    now = pytz.utc.localize(datetime.utcnow())
    event_start = now + timedelta(minutes=25)  # event in 25 minutes

    validator = ReservationValidator(
        user_role="staff",
        spot_is_vip=False,
        parking_zone_type="staff",
        existing_reservations_statuses=[],  # no active or pending
        spot_currently_occupied=False,
        res_start_time=now + timedelta(minutes=10),
        res_end_time=now + timedelta(minutes=60),
        now=now,
        event_start_time=event_start,
        event_allowed_parking_lots=["Lot A", "Lot B"],
        spot_lot_name="Lot A"
    )
    result = validator.validate()  # This will print all the times and validations

except ReservationValidationError as e:
    print("Validation failed:", str(e))
