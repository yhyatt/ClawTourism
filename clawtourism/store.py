"""TripStore — saves and loads trips from memory/travel/ directory."""

import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from clawtourism.models import (
    CruiseBooking,
    Flight,
    GapItem,
    GapSeverity,
    Hotel,
    Restaurant,
    SourceEmail,
    Trip,
    TripStatus,
)
from clawtourism.renderer import TripRenderer


class TripStore:
    """Stores and retrieves trips from the filesystem."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.renderer = TripRenderer()

    def save_trip_markdown(self, trip: Trip) -> Path:
        """Save trip as markdown file."""
        filename = self.renderer.get_filename(trip)
        filepath = self.base_dir / filename
        content = self.renderer.render(trip)
        filepath.write_text(content, encoding="utf-8")
        return filepath

    def save_trip_json(self, trip: Trip) -> Path:
        """Save trip as JSON for machine consumption."""
        filename = f"{trip.trip_id}.json"
        filepath = self.base_dir / filename
        data = self._trip_to_dict(trip)
        filepath.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return filepath

    def load_trip_json(self, trip_id: str) -> Trip | None:
        """Load trip from JSON file."""
        filepath = self.base_dir / f"{trip_id}.json"
        if not filepath.exists():
            return None
        data = json.loads(filepath.read_text(encoding="utf-8"))
        return self._dict_to_trip(data)

    def list_trips(self) -> list[str]:
        """List all trip IDs in the store."""
        return [
            p.stem for p in self.base_dir.glob("*.json")
        ]

    def save_all(self, trips: list[Trip]) -> list[Path]:
        """Save all trips as both markdown and JSON."""
        paths = []
        for trip in trips:
            paths.append(self.save_trip_markdown(trip))
            paths.append(self.save_trip_json(trip))
        return paths

    def _trip_to_dict(self, trip: Trip) -> dict[str, Any]:
        """Convert trip to dictionary for JSON serialization."""

        def convert_value(obj: Any) -> Any:
            if isinstance(obj, date):
                return obj.isoformat()
            elif isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, (TripStatus, GapSeverity)):
                return obj.value
            elif hasattr(obj, "__dataclass_fields__"):
                return {k: convert_value(v) for k, v in asdict(obj).items()}
            elif isinstance(obj, list):
                return [convert_value(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: convert_value(v) for k, v in obj.items()}
            return obj

        result: dict[str, Any] = convert_value(asdict(trip))
        return result

    def _dict_to_trip(self, data: dict[str, Any]) -> Trip:
        """Convert dictionary back to Trip object."""

        def parse_date(value: str | None) -> date | None:
            if value is None:
                return None
            return date.fromisoformat(value)

        def parse_datetime(value: str | None) -> datetime | None:
            if value is None:
                return None
            return datetime.fromisoformat(value)

        # Parse flights
        flights = [
            Flight(
                flight_number=f["flight_number"],
                departure_airport=f["departure_airport"],
                arrival_airport=f["arrival_airport"],
                departure_date=parse_date(f["departure_date"]) or date.today(),
                departure_time=f.get("departure_time"),
                arrival_time=f.get("arrival_time"),
                passengers=f.get("passengers", []),
                booking_ref=f.get("booking_ref"),
                airline=f.get("airline"),
                seat=f.get("seat"),
                is_return=f.get("is_return", False),
            )
            for f in data.get("flights", [])
        ]

        # Parse hotels
        hotels = [
            Hotel(
                name=h["name"],
                check_in=parse_date(h["check_in"]) or date.today(),
                check_out=parse_date(h["check_out"]) or date.today(),
                booking_ref=h.get("booking_ref"),
                address=h.get("address"),
                guests=h.get("guests", 2),
                room_type=h.get("room_type"),
                price=h.get("price"),
                cancelled=h.get("cancelled", False),
            )
            for h in data.get("hotels", [])
        ]

        # Parse restaurants
        restaurants = [
            Restaurant(
                name=r["name"],
                date=parse_date(r["date"]) or date.today(),
                time=r["time"],
                party_size=r.get("party_size", 2),
                booking_ref=r.get("booking_ref"),
                phone=r.get("phone"),
                address=r.get("address"),
                special_occasion=r.get("special_occasion"),
            )
            for r in data.get("restaurants", [])
        ]

        # Parse cruise
        cruise_data = data.get("cruise")
        cruise = None
        if cruise_data:
            cruise = CruiseBooking(
                ship_name=cruise_data["ship_name"],
                cruise_line=cruise_data["cruise_line"],
                start_date=parse_date(cruise_data["start_date"]) or date.today(),
                end_date=parse_date(cruise_data["end_date"]) or date.today(),
                nights=cruise_data["nights"],
                booking_refs=cruise_data.get("booking_refs", []),
                cabin_type=cruise_data.get("cabin_type"),
                passengers=cruise_data.get("passengers", []),
                itinerary=cruise_data.get("itinerary", []),
                embark_port=cruise_data.get("embark_port"),
                disembark_port=cruise_data.get("disembark_port"),
                package=cruise_data.get("package"),
                agent_name=cruise_data.get("agent_name"),
                agent_email=cruise_data.get("agent_email"),
            )

        # Parse gaps
        gaps = [
            GapItem(
                description=g["description"],
                severity=GapSeverity(g.get("severity", "WARNING")),
                category=g.get("category", "general"),
            )
            for g in data.get("gaps", [])
        ]

        # Parse source emails
        source_emails = [
            SourceEmail(
                message_id=e["message_id"],
                thread_id=e["thread_id"],
                subject=e["subject"],
                sender=e["sender"],
                date=parse_datetime(e["date"]) or datetime.now(),
                snippet=e.get("snippet", ""),
            )
            for e in data.get("source_emails", [])
        ]

        return Trip(
            trip_id=data["trip_id"],
            destination=data["destination"],
            start_date=parse_date(data["start_date"]) or date.today(),
            end_date=parse_date(data["end_date"]) or date.today(),
            status=TripStatus(data.get("status", "UPCOMING")),
            travellers=data.get("travellers", []),
            flights=flights,
            hotels=hotels,
            restaurants=restaurants,
            cruise=cruise,
            gaps=gaps,
            source_emails=source_emails,
            booking_refs=data.get("booking_refs", []),
            notes=data.get("notes", []),
        )
