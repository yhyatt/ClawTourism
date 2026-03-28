"""
foursquare.py — Foursquare Places API integration for clawtourism.

Uses the new Places API (places-api.foursquare.com) with Service API Key.
10,000 free calls/month. Better venue data than Google Places for nightlife,
bars, coffee, and local spots.

Key file: ~/.openclaw/foursquare-key.txt
Auth format: Bearer <key>
API version: 2025-06-17

Usage:
    python -m clawtourism foursquare restaurants --location Vienna --top 8
    python -m clawtourism foursquare bars --location Tel Aviv --top 8
    python -m clawtourism foursquare search --location Barcelona --query "tapas" --top 10
    python -m clawtourism foursquare details --fsq-id 5f88b1d2f7ff383699aaed16

When to use:
    - "Best bars/nightlife in [city]?" → foursquare bars
    - "Coffee shops in [neighborhood]?" → foursquare search --query coffee
    - "Local restaurants, not tourist traps" → foursquare restaurants --sort POPULARITY
    - Supplement Google Places when you want Foursquare's community ratings

Complements places.py (Google Places): use both for cross-referencing high-signal venues.

Category IDs (common):
    13000  Food (all)
    13065  Restaurant
    13003  Bar
    13032  Café / Coffee Shop
    13035  Cocktail Bar
    13040  Wine Bar
    13145  Sushi Restaurant
    13064  Pizza Place
    13049  Italian Restaurant
    13191  Burger Joint
    10000  Arts & Entertainment
    10024  Museum
    10027  Nightclub / Music Venue
    16000  Outdoors & Recreation
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional

BASE_URL = "https://places-api.foursquare.com/places"
KEY_FILE = Path.home() / ".openclaw" / "foursquare-key.txt"
TIMEOUT = 10
API_VERSION = "2025-06-17"

# Category IDs for common searches
CATEGORY_FOOD = "13000"
CATEGORY_RESTAURANT = "13065"
CATEGORY_BAR = "13003"
CATEGORY_CAFE = "13032"
CATEGORY_COCKTAIL_BAR = "13035"
CATEGORY_WINE_BAR = "13040"
CATEGORY_NIGHTCLUB = "10027"
CATEGORY_MUSEUM = "10024"

# Default fields to request (avoids fetching everything)
DEFAULT_FIELDS = "fsq_place_id,name,rating,price,location,categories,popularity,hours,tel,website,tastes"


def _get_key() -> str:
    key = os.environ.get("FOURSQUARE_API_KEY", "")
    if not key and KEY_FILE.exists():
        key = KEY_FILE.read_text().strip()
    if not key:
        raise ValueError(
            f"Foursquare API key not found. Store at {KEY_FILE} or set FOURSQUARE_API_KEY env var."
        )
    return key


def _request(path: str, params: dict) -> dict:
    key = _get_key()
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{BASE_URL}{path}?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {key}",
            "X-Places-Api-Version": API_VERSION,
            "Accept": "application/json",
            "User-Agent": "clawtourism/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def search_places(
    location: str,
    query: Optional[str] = None,
    radius_m: int = 2000,
    min_rating: float = 7.0,
    sort: str = "POPULARITY",
    top_n: int = 10,
    open_now: bool = False,
    fields: str = DEFAULT_FIELDS,
) -> list[dict]:
    """
    Search Foursquare places by location and optional query.

    Args:
        location: City name, neighborhood, or "lat,lon"
        query: Free-text search (e.g. "tapas", "ramen", "rooftop bar", "bar", "coffee")
        radius_m: Search radius in meters (default 2000)
        min_rating: Minimum rating (0-10 scale). Default 7.0
        sort: RELEVANCE | RATING | DISTANCE | POPULARITY
        top_n: Max results to return
        open_now: Only return places open now
        fields: Comma-separated list of fields to return

    Returns:
        List of place dicts with name, rating, price, location, categories, etc.
    """
    params: dict = {
        "limit": min(top_n * 2, 50),  # fetch extra to allow rating filter
        "sort": sort,
        "fields": fields,
    }

    # Location: lat,lon or geocodable string
    if "," in location and all(c in "0123456789.,-" for c in location):
        params["ll"] = location
        params["radius"] = radius_m
    else:
        params["near"] = location

    if query:
        params["query"] = query
    if open_now:
        params["open_now"] = "true"

    data = _request("/search", params)
    if "error" in data:
        return []

    results = data.get("results", [])

    # Filter by minimum rating (Foursquare uses 0-10 scale)
    if min_rating > 0:
        results = [r for r in results if r.get("rating", 0) >= min_rating]

    return results[:top_n]


def search_restaurants(
    location: str,
    radius_m: int = 2000,
    min_rating: float = 7.5,
    top_n: int = 10,
    sort: str = "POPULARITY",
) -> list[dict]:
    """Search for restaurants near a location."""
    return search_places(
        location=location,
        query="restaurant",
        radius_m=radius_m,
        min_rating=min_rating,
        top_n=top_n,
        sort=sort,
    )


def search_bars(
    location: str,
    radius_m: int = 2000,
    min_rating: float = 7.0,
    top_n: int = 10,
    bar_type: str = "bar",
) -> list[dict]:
    """
    Search for bars near a location.

    Args:
        bar_type: "bar" | "wine bar" | "cocktail bar" | "nightclub"
    """
    return search_places(
        location=location,
        query=bar_type,
        radius_m=radius_m,
        min_rating=min_rating,
        top_n=top_n,
        sort="POPULARITY",
    )


def search_cafes(
    location: str,
    radius_m: int = 1500,
    min_rating: float = 7.0,
    top_n: int = 8,
) -> list[dict]:
    """Search for cafés and coffee shops near a location."""
    return search_places(
        location=location,
        query="coffee",
        radius_m=radius_m,
        min_rating=min_rating,
        top_n=top_n,
        sort="POPULARITY",
    )


def get_place_details(fsq_place_id: str) -> dict:
    """Fetch full details for a specific place by its FSQ ID."""
    fields = DEFAULT_FIELDS + ",description,tips,photos,social_media,stats"
    data = _request(f"/{fsq_place_id}", {"fields": fields})
    if "error" in data:
        return data
    return data


def format_place(place: dict, idx: Optional[int] = None) -> str:
    """Format a single place as a readable string."""
    prefix = f"{idx}. " if idx is not None else ""
    name = place.get("name", "Unknown")
    rating = place.get("rating")
    price = place.get("price")
    price_str = "€" * price if price else ""
    rating_str = f"⭐ {rating:.1f}" if rating else ""

    cats = place.get("categories", [])
    cat_str = cats[0].get("name", "") if cats else ""

    loc = place.get("location", {})
    address = loc.get("formatted_address") or loc.get("address", "")

    hours = place.get("hours", {})
    open_str = ""
    if hours:
        open_str = " · Open now ✅" if hours.get("open_now") else ""

    tastes = place.get("tastes", [])[:3]
    tastes_str = f"  Tags: {', '.join(tastes)}" if tastes else ""

    line1 = f"{prefix}**{name}**"
    if cat_str:
        line1 += f" ({cat_str})"
    if rating_str or price_str:
        line1 += f"  {rating_str} {price_str}"
    line1 += open_str

    lines = [line1]
    if address:
        lines.append(f"  📍 {address}")
    if tastes_str:
        lines.append(tastes_str)

    return "\n".join(lines)


def format_report(places: list[dict], title: str) -> str:
    """Format a list of places as a report."""
    if not places:
        return f"{title}\n\nNo results found."
    lines = [title, ""]
    for i, place in enumerate(places, 1):
        lines.append(format_place(place, idx=i))
        lines.append("")
    return "\n".join(lines).strip()


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    import sys
    args = argv if argv is not None else sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return

    cmd = args[0]

    def _get_arg(flag: str, default=None):
        if flag in args:
            idx = args.index(flag)
            return args[idx + 1] if idx + 1 < len(args) else default
        return default

    def _get_int(flag: str, default: int) -> int:
        v = _get_arg(flag)
        return int(v) if v else default

    def _get_float(flag: str, default: float) -> float:
        v = _get_arg(flag)
        return float(v) if v else default

    location = _get_arg("--location") or _get_arg("--near") or (_get_arg("--ll"))
    if not location and len(args) > 1 and not args[1].startswith("--"):
        location = args[1]

    top_n = _get_int("--top", 8)
    radius = _get_int("--radius", 2000)
    min_rating = _get_float("--min-rating", 7.0)
    sort = _get_arg("--sort", "POPULARITY")

    if not location and cmd not in ("details",):
        print("Error: --location required")
        return

    if cmd == "restaurants":
        places = search_restaurants(location, radius_m=radius, min_rating=min_rating, top_n=top_n, sort=sort)
        print(format_report(places, f"🍽️ Restaurants near {location} (Foursquare)"))

    elif cmd == "bars":
        places = search_bars(location, radius_m=radius, min_rating=min_rating, top_n=top_n)
        print(format_report(places, f"🍸 Bars near {location} (Foursquare)"))

    elif cmd == "cafes":
        places = search_cafes(location, radius_m=radius, min_rating=min_rating, top_n=top_n)
        print(format_report(places, f"☕ Cafés near {location} (Foursquare)"))

    elif cmd == "search":
        query = _get_arg("--query")
        places = search_places(location, query=query, radius_m=radius, min_rating=min_rating, top_n=top_n, sort=sort)
        title = f"📍 {query or 'Places'} near {location} (Foursquare)"
        print(format_report(places, title))

    elif cmd == "details":
        fsq_id = _get_arg("--fsq-id") or (args[1] if len(args) > 1 else None)
        if not fsq_id:
            print("Error: --fsq-id required")
            return
        details = get_place_details(fsq_id)
        if "error" in details:
            print(f"Error: {details['error']}")
        else:
            print(json.dumps(details, indent=2))

    else:
        print(f"Unknown command: {cmd}. Try: restaurants, bars, cafes, search, details")
