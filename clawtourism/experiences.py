"""
experiences.py — Bookable experience & tour links for a destination.

Zero cost. Zero API. No key needed.
Generates direct deep links to the major tour/experience booking platforms.

Platforms:
    GetYourGuide  — largest global catalog, strongest for Europe
    Viator        — TripAdvisor-owned, strong US/EU, family-friendly filters
    Klook         — strong Asia, growing globally
    Airbnb Exp.   — unique local-hosted experiences
    Musement      — Europe-focused, good for museum tickets + city tours

Usage:
    python -m clawtourism experiences Vienna
    python -m clawtourism experiences "Tel Aviv" --category food
    python -m clawtourism experiences Barcelona --kids
    python -m clawtourism experiences Vienna --category outdoor --kids

When to use:
    - Pre-trip briefing "what to book in [city]?"
    - User asks "things to do in X" and wants booking links
    - After clawevents results — "here's where to book experiences"
    - Day planning when activities need advance booking

Category mapping:
    food / cooking / culinary  → food & drink filter
    outdoor / hiking / nature  → outdoor & nature filter
    museum / art / culture     → arts & culture filter
    nightlife / bar / drinks   → nightlife filter (disabled if kids=True)
    family / kids / children   → family filter (sets kids=True)
    adventure / sports         → sports & adventure filter
"""

from __future__ import annotations

import urllib.parse
from typing import Optional

# Platform emoji
PLATFORM_ICONS = {
    "getyourguide": "🌍",
    "viator": "🗺️",
    "klook": "🎪",
    "airbnb": "🏠",
    "musement": "🎭",
}

# Category → per-platform filter params
CATEGORY_PARAMS = {
    "food": {
        "getyourguide": "&categories=food-drink",
        "viator": "&taxonomyRef=FOOD_DRINK",
        "klook": "&category=food-beverage",
        "airbnb": "&category_tag=Tag:5366",  # cooking/food
        "musement": "/food-and-drink/",
    },
    "outdoor": {
        "getyourguide": "&categories=outdoor-activities",
        "viator": "&taxonomyRef=OUTDOOR",
        "klook": "&category=outdoor-activities",
        "airbnb": "&category_tag=Tag:5376",  # outdoor adventures
        "musement": "/outdoor-activities/",
    },
    "museum": {
        "getyourguide": "&categories=museum-exhibitions",
        "viator": "&taxonomyRef=MUSEUMS",
        "klook": "&category=museum-attractions",
        "airbnb": "&category_tag=Tag:5365",  # art & culture
        "musement": "/museums/",
    },
    "nightlife": {
        "getyourguide": "&categories=nightlife",
        "viator": "&taxonomyRef=NIGHTLIFE",
        "klook": "&category=nightlife",
        "airbnb": "&category_tag=Tag:5367",  # nightlife
        "musement": "/nightlife/",
    },
    "adventure": {
        "getyourguide": "&categories=sports-adventure",
        "viator": "&taxonomyRef=ADVENTURE",
        "klook": "&category=outdoor-activities",
        "airbnb": "&category_tag=Tag:5376",
        "musement": "/sports-and-adventure/",
    },
}

# Normalize category aliases
CATEGORY_ALIASES = {
    "cooking": "food",
    "culinary": "food",
    "drink": "food",
    "bar": "nightlife",
    "drinks": "nightlife",
    "hiking": "outdoor",
    "nature": "outdoor",
    "art": "museum",
    "culture": "museum",
    "history": "museum",
    "sports": "adventure",
    "kids": "family",
    "children": "family",
    "family": "family",
}

# Kids-friendly extra params per platform
KIDS_PARAMS = {
    "getyourguide": "&suitable_for=families",
    "viator": "&pid=P00012",       # family-friendly filter
    "klook": "&tag=family-friendly",
    "airbnb": "&amenities[]=children",
    "musement": "",                 # Musement has no URL-level family filter
}

# Known European city slugs for Musement
MUSEMENT_CITIES = {
    "vienna": "vienna",
    "wien": "vienna",
    "barcelona": "barcelona",
    "madrid": "madrid",
    "paris": "paris",
    "rome": "rome",
    "milan": "milan",
    "amsterdam": "amsterdam",
    "berlin": "berlin",
    "prague": "prague",
    "budapest": "budapest",
    "athens": "athens",
    "lisbon": "lisbon",
    "florence": "florence",
    "venice": "venice",
    "tel aviv": "tel-aviv",
    "bucharest": "bucharest",
    "istanbul": "istanbul",
    "valletta": "valletta",
    "marseille": "marseille",
    "genova": "genoa",
    "messina": "messina",
    "new york": "new-york",
    "nyc": "new-york",
}


def _normalize_category(category: str) -> Optional[str]:
    """Normalize category aliases to canonical form."""
    cat = category.lower().strip()
    return CATEGORY_ALIASES.get(cat, cat if cat in CATEGORY_PARAMS else None)


def get_experience_links(
    city: str,
    country_code: str = "",
    category: str = "",
    kids: bool = False,
) -> dict[str, str]:
    """
    Generate deep-link URLs for booking experiences in a city.

    Args:
        city: City name (e.g. "Vienna", "Tel Aviv")
        country_code: ISO 2-letter country code (optional, improves some links)
        category: Filter category — food, outdoor, museum, nightlife, adventure, family
        kids: If True, apply family/kids-friendly filters

    Returns:
        Dict of platform name → URL
    """
    # Normalize category
    if category.lower() in ("family", "kids", "children"):
        kids = True
        category = ""
    norm_cat = _normalize_category(category) if category else None
    cat_params = CATEGORY_PARAMS.get(norm_cat, {}) if norm_cat else {}

    city_encoded = urllib.parse.quote_plus(city)
    city_lower = city.lower()

    links = {}

    # ── GetYourGuide ──────────────────────────────────────────────────────────
    gyg_url = f"https://www.getyourguide.com/s/?q={city_encoded}&et=2"
    gyg_url += cat_params.get("getyourguide", "")
    if kids:
        gyg_url += KIDS_PARAMS["getyourguide"]
    links["getyourguide"] = gyg_url

    # ── Viator ────────────────────────────────────────────────────────────────
    viator_url = f"https://www.viator.com/searchResults/all?text={city_encoded}"
    viator_url += cat_params.get("viator", "")
    if kids:
        viator_url += KIDS_PARAMS["viator"]
    links["viator"] = viator_url

    # ── Klook ─────────────────────────────────────────────────────────────────
    klook_url = f"https://www.klook.com/en-US/search/?query={city_encoded}"
    klook_url += cat_params.get("klook", "")
    if kids:
        klook_url += KIDS_PARAMS["klook"]
    links["klook"] = klook_url

    # ── Airbnb Experiences ────────────────────────────────────────────────────
    airbnb_url = f"https://www.airbnb.com/experiences?location={city_encoded}"
    airbnb_url += cat_params.get("airbnb", "")
    if kids:
        airbnb_url += KIDS_PARAMS["airbnb"]
    links["airbnb"] = airbnb_url

    # ── Musement ──────────────────────────────────────────────────────────────
    musement_slug = MUSEMENT_CITIES.get(city_lower)
    if musement_slug:
        cat_path = cat_params.get("musement", "")
        links["musement"] = f"https://www.musement.com/us/{musement_slug}{cat_path}"

    return links


def format_experience_links(
    city: str,
    links: dict[str, str],
    kids: bool = False,
    category: str = "",
) -> str:
    """
    Format experience links as a human-readable block.

    Returns a clean multi-line string suitable for Telegram or WhatsApp.
    """
    lines = [f"🎯 Book experiences in {city}"]
    lines.append("")

    platform_names = {
        "getyourguide": "GetYourGuide",
        "viator": "Viator",
        "klook": "Klook",
        "airbnb": "Airbnb Experiences",
        "musement": "Musement",
    }

    for platform, url in links.items():
        icon = PLATFORM_ICONS.get(platform, "🔗")
        name = platform_names.get(platform, platform.title())
        lines.append(f"{icon} {name} → {url}")

    lines.append("")

    # Contextual tips
    tips = []
    if kids:
        tips.append("👨‍👩‍👧 Kids-friendly filter applied ✅")
    if category and _normalize_category(category):
        tips.append(f"🔍 Filtered for: {category}")

    city_lower = city.lower()
    if any(c in city_lower for c in ["vienna", "barcelona", "rome", "paris", "prague", "budapest", "amsterdam"]):
        tips.append("💡 GYG and Musement have the widest selection for this city.")
    elif any(c in city_lower for c in ["tel aviv", "jerusalem", "haifa"]):
        tips.append("💡 Airbnb Experiences has strong local options for this city.")
    elif any(c in city_lower for c in ["new york", "nyc", "chicago", "miami"]):
        tips.append("💡 Viator has the widest US selection.")
    elif any(c in city_lower for c in ["tokyo", "osaka", "bangkok", "singapore", "seoul"]):
        tips.append("💡 Klook is strongest for this region.")
    else:
        tips.append("💡 GYG and Viator have the widest global selection.")

    lines.extend(tips)
    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    import sys
    args = argv if argv is not None else sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return

    city = args[0]
    category = ""
    kids = False

    if "--kids" in args or "--family" in args:
        kids = True
    if "--category" in args:
        idx = args.index("--category")
        category = args[idx + 1] if idx + 1 < len(args) else ""
    if "--cat" in args:
        idx = args.index("--cat")
        category = args[idx + 1] if idx + 1 < len(args) else ""

    links = get_experience_links(city, category=category, kids=kids)
    print(format_experience_links(city, links, kids=kids, category=category))
