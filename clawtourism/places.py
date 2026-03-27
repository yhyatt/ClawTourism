"""
places.py — Google Places API (New) integration for clawtourism.

Searches restaurants, attractions, and POIs near a location.

API key: stored at ~/.openclaw/google-places-key.txt or GOOGLE_PLACES_KEY env var.
Free tier (as of March 2025): 5,000 Nearby Search requests/month.

Usage:
    python -m clawtourism places restaurants --city Vienna --district Neubau --top 8
    python -m clawtourism places attractions --city Barcelona --radius 2000 --top 10
    python -m clawtourism places search --city "Tel Aviv" --type cafe --top 5

Place types: restaurant, tourist_attraction, museum, park, cafe, bar, bakery,
             amusement_park, zoo, aquarium, art_gallery, night_club, spa

When to use:
    - "Where should we eat in [city/neighborhood]?" → places restaurants
    - "What's there to do in [city] with kids?" → places attractions + type=amusement_park,zoo
    - "Best cafés near [hotel/address]?" → places search --type cafe
    - Building a day plan → combine attractions + restaurants for a neighborhood

Limitations:
    - Radius-based (lat/lon center required internally; city names resolved via geocoding)
    - Results are Google's popularity ranking, not curated
    - No availability/reservation data (use accommodation.py for that)
"""

from __future__ import annotations

import os
import json
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional

PLACES_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
KEY_FILE = Path.home() / ".openclaw" / "google-places-key.txt"

# Price level mapping
PRICE_MAP = {
    "PRICE_LEVEL_FREE": "Free",
    "PRICE_LEVEL_INEXPENSIVE": "€",
    "PRICE_LEVEL_MODERATE": "€€",
    "PRICE_LEVEL_EXPENSIVE": "€€€",
    "PRICE_LEVEL_VERY_EXPENSIVE": "€€€€",
}

# City/district → approximate lat/lon (common destinations)
# These avoid a geocoding API call for well-known locations
KNOWN_COORDS: dict[str, tuple[float, float]] = {
    "vienna": (48.2082, 16.3738),
    "neubau": (48.2000, 16.3500),
    "neubau vienna": (48.2000, 16.3500),
    "barcelona": (41.3851, 2.1734),
    "eixample": (41.3944, 2.1550),
    "eixample barcelona": (41.3944, 2.1550),
    "madrid": (40.4168, -3.7038),
    "valencia": (39.4699, -0.3763),
    "tel aviv": (32.0853, 34.7818),
    "bucharest": (44.4268, 26.1025),
    "rome": (41.9028, 12.4964),
    "naples": (40.8518, 14.2681),
    "catania": (37.5079, 15.0830),
    "athens": (37.9838, 23.7275),
    "paphos": (34.7757, 32.4282),
    "marrakech": (31.6295, -7.9811),
    "tenerife": (28.2916, -16.6291),
    "paris": (48.8566, 2.3522),
}


def _get_key() -> str:
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    key = os.environ.get("GOOGLE_PLACES_KEY", "")
    if not key:
        raise RuntimeError(
            f"No Google Places API key found. "
            f"Store at {KEY_FILE} or set GOOGLE_PLACES_KEY env var."
        )
    return key


def _geocode(location: str) -> tuple[float, float]:
    """Resolve a location string to lat/lon using Google Geocoding API."""
    # Try known coords first (no API call)
    key_lower = location.lower().strip()
    if key_lower in KNOWN_COORDS:
        return KNOWN_COORDS[key_lower]

    # Fall back to Geocoding API
    api_key = _get_key()
    params = urllib.parse.urlencode({"address": location, "key": api_key})
    url = f"{GEOCODE_URL}?{params}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read())

    results = data.get("results", [])
    if not results:
        raise ValueError(f"Could not geocode location: {location}")

    loc = results[0]["geometry"]["location"]
    return loc["lat"], loc["lng"]


def search_places(
    location: str,
    place_types: list[str],
    radius_m: int = 1500,
    min_rating: float = 4.0,
    min_reviews: int = 100,
    max_results: int = 10,
    language: str = "en",
) -> list[dict]:
    """
    Search for places near a location.

    Args:
        location: City name, neighborhood, or "lat,lon"
        place_types: List of Google place types (e.g. ["restaurant", "cafe"])
        radius_m: Search radius in meters
        min_rating: Minimum rating filter
        min_reviews: Minimum review count filter
        max_results: Max results to return
        language: Language code for results

    Returns:
        List of place dicts with: name, rating, reviews, address, type, price, summary, url
    """
    api_key = _get_key()

    # Resolve location to coordinates
    if "," in location and all(p.replace(".", "").replace("-", "").isdigit()
                               for p in location.split(",", 1)):
        lat, lng = map(float, location.split(",", 1))
    else:
        lat, lng = _geocode(location)

    payload = {
        "includedTypes": place_types,
        "maxResultCount": min(max_results * 2, 20),  # fetch more, filter down
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(radius_m),
            }
        },
        "rankPreference": "POPULARITY",
        "languageCode": language,
    }

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.displayName,"
            "places.rating,"
            "places.userRatingCount,"
            "places.formattedAddress,"
            "places.primaryTypeDisplayName,"
            "places.editorialSummary,"
            "places.priceLevel,"
            "places.websiteUri,"
            "places.googleMapsUri,"
            "places.regularOpeningHours"
        ),
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(PLACES_NEARBY_URL, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())

    places = []
    for p in result.get("places", []):
        rating = p.get("rating", 0)
        reviews = p.get("userRatingCount", 0)
        if rating < min_rating or reviews < min_reviews:
            continue
        places.append({
            "name": p.get("displayName", {}).get("text", "?"),
            "rating": rating,
            "reviews": reviews,
            "address": p.get("formattedAddress", ""),
            "type": p.get("primaryTypeDisplayName", {}).get("text", ""),
            "price": PRICE_MAP.get(p.get("priceLevel", ""), ""),
            "summary": p.get("editorialSummary", {}).get("text", ""),
            "maps_url": p.get("googleMapsUri", ""),
            "website": p.get("websiteUri", ""),
            "open_now": (
                p.get("regularOpeningHours", {}).get("openNow")
                if p.get("regularOpeningHours") else None
            ),
        })

    # Sort by rating desc, then reviews desc
    places.sort(key=lambda x: (-x["rating"], -x["reviews"]))
    return places[:max_results]


def search_restaurants(
    location: str,
    radius_m: int = 1200,
    min_rating: float = 4.3,
    top_n: int = 8,
) -> list[dict]:
    return search_places(
        location=location,
        place_types=["restaurant"],
        radius_m=radius_m,
        min_rating=min_rating,
        max_results=top_n,
    )


def search_attractions(
    location: str,
    radius_m: int = 2000,
    min_rating: float = 4.3,
    top_n: int = 10,
    family_types: bool = False,
) -> list[dict]:
    types = ["tourist_attraction", "museum", "art_gallery", "park"]
    if family_types:
        types += ["amusement_park", "zoo", "aquarium", "bowling_alley"]
    return search_places(
        location=location,
        place_types=types,
        radius_m=radius_m,
        min_rating=min_rating,
        max_results=top_n,
    )


def format_report(places: list[dict], title: str) -> str:
    """Format a list of places into a readable text report."""
    if not places:
        return f"{title}\n\nNo places found."

    lines = [f"{title}\n"]
    for p in places:
        price = f" {p['price']}" if p["price"] else ""
        ptype = f" [{p['type']}]" if p["type"] else ""
        summary = f"\n   {p['summary'][:120]}" if p["summary"] else ""
        maps = f"\n   📍 {p['maps_url']}" if p["maps_url"] else ""
        lines.append(
            f"⭐ {p['rating']} ({p['reviews']:,} reviews){price}{ptype}\n"
            f"   {p['name']}\n"
            f"   {p['address']}"
            f"{summary}"
            f"{maps}"
        )
    return "\n\n".join(lines)
