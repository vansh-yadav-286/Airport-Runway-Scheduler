"""Dependency-free Python implementation of the airport runway scheduler.

Run directly with ``python3 python/airport_scheduler.py`` for a small example,
or import :class:`RunwayScheduler` into another Python program.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import heapq
from typing import Literal

FlightType = Literal["arrival", "departure"]
RunwayMode = Literal["mixed", "arrival", "departure"]


@dataclass(order=True)
class Flight:
    """A request; fields used for queue ordering come first."""

    sort_key: tuple = field(init=False, repr=False)
    id: str = field(compare=False)
    type: FlightType = field(compare=False)
    requested_time: int = field(compare=False)
    priority: int = field(compare=False)
    emergency: bool = field(default=False, compare=False)
    status: str = field(default="pending", compare=False)
    slot: dict | None = field(default=None, compare=False)

    def refresh_sort_key(self) -> None:
        self.sort_key = (not self.emergency, self.priority, self.requested_time, self.id)

    def __post_init__(self) -> None:
        self.refresh_sort_key()


@dataclass
class Booking:
    flight_id: str
    start: int
    end: int


@dataclass
class Runway:
    name: str
    mode: RunwayMode
    windows: list[tuple[int, int]]
    bookings: list[Booking] = field(default_factory=list)

    def accepts(self, flight_type: FlightType) -> bool:
        return self.mode == "mixed" or self.mode == flight_type

    def find_earliest_slot(self, requested_time: int, duration: int) -> tuple[int, str | None] | None:
        """Return earliest fitting start and the flight that caused its last delay."""
        for window_start, window_end in self.windows:
            start = max(requested_time, window_start)
            blocked_by = None
            for booking in self.bookings:
                if booking.end <= start:
                    continue
                if booking.start >= start + duration:
                    break
                start = booking.end
                blocked_by = booking.flight_id
            if start + duration <= window_end:
                return start, blocked_by
        return None

    def book(self, booking: Booking) -> None:
        if any(not (booking.end <= b.start or booking.start >= b.end) for b in self.bookings):
            raise ValueError(f"Booking overlaps an existing booking on runway {self.name}.")
        self.bookings.append(booking)
        self.bookings.sort(key=lambda item: item.start)


class RunwayScheduler:
    """Schedules runway requests by emergency, priority, requested time, then ID."""

    MAX_FLIGHTS = 500
    MAX_RUNWAYS = 10

    def __init__(self) -> None:
        self.flights: dict[str, Flight] = {}
        self.runways: list[Runway] = []
        self.durations = {"arrival": 4, "departure": 3}
        self._queue: list[Flight] = []

    def set_runways(self, configs: list[dict]) -> None:
        if not 1 <= len(configs) <= self.MAX_RUNWAYS:
            raise ValueError(f"Provide 1 to {self.MAX_RUNWAYS} runways.")
        names = set()
        runways = []
        for config in configs:
            name = str(config["name"]).strip()
            mode = config.get("mode", "mixed")
            windows = sorted(tuple(window) for window in config["windows"])
            if not name or name in names:
                raise ValueError("Runway names must be non-empty and unique.")
            if mode not in ("mixed", "arrival", "departure"):
                raise ValueError("Runway mode must be mixed, arrival, or departure.")
            if not windows or any(not (0 <= start < end <= 1440) for start, end in windows):
                raise ValueError("Runway windows must be valid minute intervals within a day.")
            if any(windows[i][1] > windows[i + 1][0] for i in range(len(windows) - 1)):
                raise ValueError("Runway windows cannot overlap.")
            names.add(name)
            runways.append(Runway(name, mode, windows))
        self.runways = runways
        self._requeue_all()

    def add_flight(self, id: str, type: FlightType, requested_time: int, priority: int,
                   emergency: bool = False) -> Flight:
        flight_id = str(id).strip().upper()
        if not flight_id.isalnum() or not 2 <= len(flight_id) <= 8:
            raise ValueError("Flight ID must be 2–8 letters or digits.")
        if flight_id in self.flights or len(self.flights) >= self.MAX_FLIGHTS:
            raise ValueError("Flight ID already exists or flight limit reached.")
        if type not in self.durations or not isinstance(requested_time, int) or not 0 <= requested_time < 1440:
            raise ValueError("Invalid flight type or requested time.")
        if not isinstance(priority, int) or not 1 <= priority <= 5:
            raise ValueError("Priority must be an integer from 1 through 5.")
        flight = Flight(flight_id, type, requested_time, priority, bool(emergency))
        self.flights[flight_id] = flight
        heapq.heappush(self._queue, flight)
        return flight

    def update_flight(self, id: str, *, priority: int | None = None, emergency: bool | None = None) -> None:
        flight = self._pending(id)
        if priority is not None:
            if not isinstance(priority, int) or not 1 <= priority <= 5:
                raise ValueError("Priority must be an integer from 1 through 5.")
            flight.priority = priority
        if emergency is not None:
            flight.emergency = bool(emergency)
        self._requeue_all()

    def schedule_next(self) -> Flight | None:
        if not self._queue:
            return None
        flight = heapq.heappop(self._queue)
        duration = self.durations[flight.type]
        candidates = []
        for runway in self.runways:
            if runway.accepts(flight.type):
                slot = runway.find_earliest_slot(flight.requested_time, duration)
                if slot:
                    candidates.append((slot[0], runway.name, runway, slot[1]))
        if not candidates:
            flight.status = "unscheduled"
            return flight
        start, _, runway, blocked_by = min(candidates)
        end = start + duration
        runway.book(Booking(flight.id, start, end))
        flight.status = "scheduled"
        flight.slot = {"runway": runway.name, "start": start, "end": end,
                       "delay": start - flight.requested_time, "blocked_by": blocked_by}
        return flight

    def schedule_all(self) -> list[Flight]:
        scheduled = []
        while flight := self.schedule_next():
            scheduled.append(flight)
        return scheduled

    def _pending(self, id: str) -> Flight:
        flight = self.flights.get(str(id).upper())
        if not flight or flight.status != "pending":
            raise ValueError("Flight does not exist or is no longer pending.")
        return flight

    def _requeue_all(self) -> None:
        for runway in self.runways:
            runway.bookings.clear()
        self._queue = []
        for flight in self.flights.values():
            flight.status, flight.slot = "pending", None
            flight.refresh_sort_key()
            self._queue.append(flight)
        heapq.heapify(self._queue)


def to_minutes(value: str) -> int:
    """Convert a 24-hour HH:MM time into minutes since midnight."""
    hour, minute = map(int, value.split(":"))
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Time must be in HH:MM format.")
    return hour * 60 + minute


if __name__ == "__main__":
    scheduler = RunwayScheduler()
    scheduler.set_runways([{"name": "09L", "mode": "mixed", "windows": [(0, 1440)]}])
    scheduler.add_flight("UK811", "arrival", to_minutes("06:00"), 2)
    scheduler.add_flight("EMG1", "arrival", to_minutes("06:05"), 5, emergency=True)
    for flight in scheduler.schedule_all():
        print(f"{flight.id}: {flight.status} {flight.slot}")
