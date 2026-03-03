"""
Pre-trip checklist — D-14, D-7, D-3, D-1 alerts per trip.
Family trips only (Mode B). Group trips handled by group agent.
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path
import os

TRIPS_DIR = Path(os.environ.get("KAITRAVEL_TRIPS_DIR",
    Path(__file__).parent.parent.parent.parent / "memory/trips"))

FAMILY_TRAVELLERS = {"Yonatan Hyatt", "Louise Hyatt", "Zoe Hyatt", "Lenny Hyatt"}


def is_family_trip(trip: dict) -> bool:
    travellers = set(trip.get("travellers", []))
    return bool(travellers & {"Louise Hyatt", "Zoe Hyatt", "Lenny Hyatt"})


def days_until(date_str: str) -> int:
    target = datetime.strptime(date_str, "%Y-%m-%d").date()
    return (target - date.today()).days


def get_checklist_cron_specs(trip: dict) -> list[dict]:
    """Generate D-14, D-7, D-3, D-1 cron specs for a family trip."""
    if not is_family_trip(trip):
        return []

    start = trip["start_date"]
    trip_id = trip["trip_id"]
    destination = trip.get("destination", "your trip")
    has_kids = any(t in trip.get("travellers", []) for t in ["Zoe Hyatt", "Lenny Hyatt"])
    kids_str = "Zoe (5.5) and Lenny (1.5)" if has_kids else ""

    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
    except ValueError:
        return []

    specs = []

    checkpoints = {
        14: (
            f"🧳 *{destination} in 2 weeks!*\n\n"
            f"Suggested to-do:\n"
            f"• Book any restaurants not yet reserved\n"
            f"• Check passport expiry (Zoe + Lenny)\n"
            f"• Start packing list?\n"
            f"• Travel insurance confirmed?\n"
            f"• Check excursion/activity bookings\n"
            f"\n_Say 'yes' if you want a packing list for {destination}"
        + (" (kid-friendly)" if has_kids else "") + "_"
        ),
        7: (
            f"✈️ *{destination} in 1 week*\n\n"
            f"• Prescriptions for the trip packed?\n"
            f"• Adapter/chargers ready?\n"
            f"• Download offline maps for each port city\n"
            f"• Notify credit cards of travel dates\n"
            f"• Check weather at destination\n"
            + (f"• Kids snacks + entertainment for flights packed?\n" if kids_str else "")
        ),
        3: (
            f"🗂️ *{destination} — 3 days to go*\n\n"
            f"• Travel docs printed/saved offline (boarding passes, hotel refs, booking confirmations)\n"
            f"• Luggage weight check\n"
            f"• Car/taxi to airport arranged?\n"
            + (f"• Stroller checked in? (Lenny)\n" if has_kids else "")
            + f"• Emergency contacts noted\n"
        ),
        1: (
            f"🚨 *Tomorrow: {destination}!*\n\n"
            f"I'll check in with flight status + terminal info shortly.\n"
            f"• Bags packed and weighed?\n"
            f"• Phone charged?\n"
            f"• Passport in bag (not drawer)?\n"
            + (f"• Kids' car seats / stroller at door?\n" if has_kids else "")
        ),
    }

    for days_before, message in checkpoints.items():
        alert_date = start_dt - timedelta(days=days_before)
        if alert_date.date() <= date.today():
            continue  # Past — skip
        specs.append({
            "name": f"pretripcheck-{trip_id}-d{days_before}",
            "schedule": {
                "kind": "cron",
                "expr": f"0 9 {alert_date.day} {alert_date.month} *",
                "tz": "Asia/Jerusalem",
            },
            "payload_text": message,
        })

    return specs


if __name__ == "__main__":
    for trip_file in TRIPS_DIR.glob("*.json"):
        trip = json.loads(trip_file.read_text())
        specs = get_checklist_cron_specs(trip)
        if specs:
            print(f"\n{trip['trip_id']} — {len(specs)} checklist crons:")
            for s in specs:
                print(f"  {s['name']} @ {s['schedule']['expr']}")
