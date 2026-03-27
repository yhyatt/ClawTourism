"""
accommodation.py — Hotel/apartment search and availability via Booking.com RapidAPI.

Uses the booking-com15 API on RapidAPI to search real availability with live pricing.

Usage:
    python -m clawtourism accommodation search \
        --city "Vienna" --district "Neubau" \
        --checkin 2026-04-03 --checkout 2026-04-10 \
        --adults 2 --children-ages 5 1 \
        --min-rating 8.0 --type apartment

    python -m clawtourism accommodation details --hotel-id 14726732 \
        --checkin 2026-04-03 --checkout 2026-04-10

API key: stored at ~/.openclaw/rapidapi-booking-key.txt
"""

from __future__ import annotations

import os
import json
import urllib.request
from pathlib import Path
from typing import Optional


RAPIDAPI_HOST = "booking-com15.p.rapidapi.com"
KEY_FILE = Path.home() / ".openclaw" / "rapidapi-booking-key.txt"


def _get_key() -> str:
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    key = os.environ.get("RAPIDAPI_BOOKING_KEY", "")
    if not key:
        raise RuntimeError(
            f"No RapidAPI Booking key found. "
            f"Store key at {KEY_FILE} or set RAPIDAPI_BOOKING_KEY env var."
        )
    return key


def _get(path: str, params: dict) -> dict:
    """Make a GET request to the Booking.com RapidAPI."""
    key = _get_key()
    query = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"https://{RAPIDAPI_HOST}/{path}?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "x-rapidapi-host": RAPIDAPI_HOST,
            "x-rapidapi-key": key,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


import urllib.parse


def search_destination(query: str) -> list[dict]:
    """Find dest_id and search_type for a location string."""
    data = _get("api/v1/hotels/searchDestination", {"query": query})
    return data.get("data", [])


def search_hotels(
    dest_id: str,
    search_type: str,
    checkin: str,
    checkout: str,
    adults: int = 2,
    children_ages: list[int] | None = None,
    currency: str = "EUR",
    sort_by: str = "popularity",
    apartment_only: bool = True,
    min_rating: float = 8.0,
) -> list[dict]:
    """
    Search available hotels/apartments.

    Returns list of dicts with: hotel_id, name, price_total, rating, reviews, address.
    """
    params = {
        "dest_id": dest_id,
        "search_type": search_type,
        "arrival_date": checkin,
        "departure_date": checkout,
        "adults": adults,
        "room_qty": 1,
        "currency_code": currency,
        "languagecode": "en-us",
        "sort_by": sort_by,
    }
    if children_ages:
        params["children_age"] = "%2C".join(str(a) for a in children_ages)
    if apartment_only:
        params["categories_filter"] = 201  # apartments filter

    data = _get("api/v1/hotels/searchHotels", params)
    results = []
    for h in data.get("data", {}).get("hotels", []):
        prop = h.get("property", {})
        rating = float(prop.get("reviewScore") or 0)
        if rating < min_rating:
            continue
        price = prop.get("priceBreakdown", {}).get("grossPrice", {}).get("value")
        results.append({
            "hotel_id": h.get("hotel_id"),
            "name": prop.get("name", "?"),
            "price_total_eur": round(float(price), 0) if price else None,
            "rating": rating,
            "review_count": prop.get("reviewCount", 0),
            "address": prop.get("address", ""),
        })
    return results


def get_hotel_details(hotel_id: int, checkin: str, checkout: str,
                      adults: int = 2, children_ages: list[int] | None = None) -> dict:
    """Get full details for a specific hotel."""
    params = {
        "hotel_id": hotel_id,
        "arrival_date": checkin,
        "departure_date": checkout,
        "adults": adults,
        "currency_code": "EUR",
        "languagecode": "en-us",
    }
    if children_ages:
        params["children_age"] = ",".join(str(a) for a in children_ages)
    data = _get("api/v1/hotels/getHotelDetails", params)
    return data.get("data", {})


def get_hotel_reviews(hotel_id: int, limit: int = 5) -> list[dict]:
    """Get top reviews for a hotel."""
    data = _get("api/v1/hotels/getHotelReviews", {
        "hotel_id": hotel_id,
        "sort_type": "SORT_MOST_RELEVANT",
        "page_number": 1,
        "languagecode": "en-us",
    })
    reviews = data.get("data", {}).get("result", [])[:limit]
    return [
        {
            "score": r.get("average_score_out_of_10"),
            "title": r.get("title", ""),
            "pros": r.get("pros", "")[:200],
            "cons": r.get("cons", "")[:100],
        }
        for r in reviews
    ]


def search_and_report(
    city: str,
    checkin: str,
    checkout: str,
    adults: int = 2,
    children_ages: list[int] | None = None,
    district: str | None = None,
    min_rating: float = 8.5,
    top_n: int = 5,
    with_reviews: bool = True,
) -> str:
    """
    High-level: search city/district, return formatted text report.

    This is the main entry point for agents.
    """
    query = f"{district}, {city}" if district else city
    destinations = search_destination(query)
    if not destinations:
        return f"No destination found for: {query}"

    # Prefer district matches
    dest = next(
        (d for d in destinations if d.get("dest_type") == "district"),
        destinations[0]
    )
    dest_id = dest["dest_id"]
    search_type = dest.get("dest_type", "city")

    hotels = search_hotels(
        dest_id=dest_id,
        search_type=search_type,
        checkin=checkin,
        checkout=checkout,
        adults=adults,
        children_ages=children_ages,
        min_rating=min_rating,
    )

    if not hotels:
        return f"No apartments found in {query} for {checkin}–{checkout} with rating ≥{min_rating}"

    # Sort by rating
    hotels.sort(key=lambda h: h["rating"], reverse=True)

    nights = (
        __import__("datetime").date.fromisoformat(checkout)
        - __import__("datetime").date.fromisoformat(checkin)
    ).days

    lines = [f"🏨 {query} — {checkin} to {checkout} ({nights} nights)\n"]
    for h in hotels[:top_n]:
        nightly = round(h["price_total_eur"] / nights) if h["price_total_eur"] and nights else "?"
        lines.append(
            f"⭐ {h['rating']} ({h['review_count']} reviews) — {h['name']}\n"
            f"   💶 €{nightly}/night (€{h['price_total_eur']} total) | {h['address']}"
        )
        if with_reviews:
            try:
                reviews = get_hotel_reviews(h["hotel_id"], limit=3)
                for r in reviews:
                    if r["pros"]:
                        lines.append(f"   ✍️  \"{r['pros'][:120]}\"")
            except Exception:
                pass
        lines.append("")

    return "\n".join(lines)
