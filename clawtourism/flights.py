"""
flights.py — Flight search (prices & availability) via Booking.com RapidAPI.

When to use:
    Searching for flight prices, schedules, and availability between two cities.
    Ideal for comparing options, finding the cheapest fare, or checking direct routes.

NOT for:
    Real-time flight status tracking (use flight_status_cli.py for that).

Airport codes:
    The API expects IATA codes with a `.AIRPORT` suffix (e.g. OTP.AIRPORT, VIE.AIRPORT).
    This module handles the suffix automatically — just pass the 3-letter IATA code
    (e.g. "OTP") or a city name (e.g. "bucharest") which will be resolved via AIRPORT_CODES.

Common airport codes are in AIRPORT_CODES dict below. Use city_to_iata() for lookup.

API key:
    Stored at ~/.openclaw/rapidapi-booking-key.txt (same key as accommodation.py).
    Fallback: RAPIDAPI_BOOKING_KEY environment variable.

Examples:
    from clawtourism.flights import search_flights, search_flights_report, city_to_iata

    # Search flights
    results = search_flights("OTP", "VIE", "2026-04-03", adults=2, children=2)

    # City name lookup
    iata = city_to_iata("bucharest")  # -> "OTP"

    # Formatted report
    print(search_flights_report("OTP", "VIE", "2026-04-03", adults=2))
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

RAPIDAPI_HOST = "booking-com15.p.rapidapi.com"
KEY_FILE = Path.home() / ".openclaw" / "rapidapi-booking-key.txt"

AIRPORT_CODES: dict[str, str] = {
    "bucharest": "OTP",
    "barcelona": "BCN",
    "vienna": "VIE",
    "tel aviv": "TLV",
    "athens": "ATH",
    "madrid": "MAD",
    "valencia": "VLC",
    "rome": "FCO",
    "naples": "NAP",
    "catania": "CTA",
    "paris": "CDG",
    "london": "LHR",
    "marrakech": "RAK",
    "tenerife": "TFS",
    "larnaca": "LCA",
    "paphos": "PFO",
    "milan": "MXP",
    "amsterdam": "AMS",
    "berlin": "BER",
    "new york": "JFK",
}


def _get_key() -> str:
    """Load the RapidAPI key from file or environment variable.

    Returns:
        The API key string.

    Raises:
        RuntimeError: If no key is found.
    """
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    key = os.environ.get("RAPIDAPI_BOOKING_KEY", "")
    if not key:
        raise RuntimeError(
            f"No RapidAPI Booking key found. "
            f"Store key at {KEY_FILE} or set RAPIDAPI_BOOKING_KEY env var."
        )
    return key


def city_to_iata(city: str) -> str:
    """Convert a city name to its IATA airport code.

    Args:
        city: City name (case-insensitive), e.g. "Bucharest", "Tel Aviv".

    Returns:
        3-letter IATA code, e.g. "OTP".

    Raises:
        KeyError: If the city is not in AIRPORT_CODES.
    """
    key = city.strip().lower()
    if key not in AIRPORT_CODES:
        raise KeyError(
            f"Unknown city '{city}'. Known cities: {', '.join(sorted(AIRPORT_CODES.keys()))}"
        )
    return AIRPORT_CODES[key]


def _resolve_iata(code_or_city: str) -> str:
    """Resolve an IATA code or city name to an IATA code.

    If the input is 3 uppercase letters, it's treated as an IATA code directly.
    Otherwise, it's looked up in AIRPORT_CODES.
    """
    s = code_or_city.strip()
    if len(s) == 3 and s.isalpha() and s.isupper():
        return s
    # Try city lookup
    return city_to_iata(s)


def _parse_flight_offer(offer: dict) -> Optional[dict]:
    """Parse a single flightOffer from the API response into a clean dict.

    Returns None if the offer cannot be parsed.
    """
    try:
        segments = offer.get("segments", [])
        if not segments:
            return None

        # Price
        price_breakdown = offer.get("priceBreakdown", {})
        total = price_breakdown.get("total", {})
        price = total.get("units", 0)
        currency = total.get("currencyCode", "EUR")

        # First segment for departure, last for arrival
        first_seg = segments[0]
        last_seg = segments[-1]

        depart_time = first_seg.get("departureTime", "")
        arrive_time = last_seg.get("arrivalTime", "")

        # Duration: compute from departure/arrival times
        duration_min = 0
        try:
            fmt = "%Y-%m-%dT%H:%M:%S"
            dt_dep = datetime.strptime(depart_time[:19], fmt)
            dt_arr = datetime.strptime(arrive_time[:19], fmt)
            duration_min = int((dt_arr - dt_dep).total_seconds() / 60)
        except (ValueError, TypeError):
            pass

        # Airline: from first segment's legs
        airline = "Unknown"
        flight_number = ""
        legs = first_seg.get("legs", [])
        if legs:
            first_leg = legs[0]
            carriers = first_leg.get("carriersData", [])
            if carriers:
                airline = carriers[0].get("name", "Unknown")
            flight_info = first_leg.get("flightInfo", {})
            flight_number = flight_info.get("flightNumber", "")
            carrier_code = flight_info.get("carrierCode", "")
            if carrier_code and flight_number:
                flight_number = f"{carrier_code}{flight_number}"

        stops = len(segments) - 1

        return {
            "price_eur": price,
            "currency": currency,
            "airline": airline,
            "depart_time": depart_time,
            "arrive_time": arrive_time,
            "duration_min": duration_min,
            "stops": stops,
            "flight_number": flight_number,
            "segments_count": len(segments),
        }
    except Exception as e:
        logger.warning("Failed to parse flight offer: %s", e)
        return None


def search_flights(
    from_iata: str,
    to_iata: str,
    depart_date: str,
    adults: int = 2,
    children: int = 0,
    currency: str = "EUR",
    direct_only: bool = False,
    top_n: int = 8,
) -> list[dict]:
    """Search for flights between two airports on a given date.

    Args:
        from_iata: Origin IATA code (e.g. "OTP") or city name (e.g. "bucharest").
        to_iata: Destination IATA code (e.g. "VIE") or city name.
        depart_date: Departure date in YYYY-MM-DD format.
        adults: Number of adult passengers.
        children: Number of child passengers.
        currency: Currency code for pricing (default EUR).
        direct_only: If True, only return non-stop flights (1 segment).
        top_n: Maximum number of results to return.

    Returns:
        List of flight dicts sorted by price (cheapest first). Each dict contains:
        price_eur, currency, airline, depart_time, arrive_time, duration_min,
        stops, flight_number, segments_count.
        Returns empty list on network/API errors.
    """
    try:
        origin = _resolve_iata(from_iata)
        dest = _resolve_iata(to_iata)
    except KeyError as e:
        logger.warning("Could not resolve airport code: %s", e)
        return []

    try:
        key = _get_key()
    except RuntimeError as e:
        logger.warning("API key error: %s", e)
        return []

    params = {
        "fromId": f"{origin}.AIRPORT",
        "toId": f"{dest}.AIRPORT",
        "departDate": depart_date,
        "adults": str(adults),
        "currency_code": currency,
    }
    if children > 0:
        params["children"] = str(children)

    query = "&".join(
        f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()
    )
    url = f"https://{RAPIDAPI_HOST}/api/v1/flights/searchFlights?{query}"

    req = urllib.request.Request(
        url,
        headers={
            "x-rapidapi-host": RAPIDAPI_HOST,
            "x-rapidapi-key": key,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
    except Exception as e:
        logger.warning("Flight search API request failed: %s", e)
        return []

    offers = body.get("data", {}).get("flightOffers", [])
    results = []
    for offer in offers:
        parsed = _parse_flight_offer(offer)
        if parsed is None:
            continue
        if direct_only and parsed["segments_count"] != 1:
            continue
        results.append(parsed)

    results.sort(key=lambda x: x["price_eur"])
    return results[:top_n]


def search_flights_report(
    from_iata: str,
    to_iata: str,
    depart_date: str,
    adults: int = 2,
    children: int = 0,
    direct_only: bool = False,
) -> str:
    """Search flights and return a formatted text report for agents.

    Args:
        from_iata: Origin IATA code or city name.
        to_iata: Destination IATA code or city name.
        depart_date: Departure date in YYYY-MM-DD format.
        adults: Number of adult passengers.
        children: Number of child passengers.
        direct_only: If True, only show non-stop flights.

    Returns:
        Formatted multi-line text report, or an error/empty message.
    """
    flights = search_flights(
        from_iata=from_iata,
        to_iata=to_iata,
        depart_date=depart_date,
        adults=adults,
        children=children,
        direct_only=direct_only,
    )

    if not flights:
        return f"No flights found from {from_iata} to {to_iata} on {depart_date}."

    lines = [
        f"✈️ Flights: {from_iata.upper()} → {to_iata.upper()} on {depart_date}",
        f"   Passengers: {adults} adults" + (f", {children} children" if children else ""),
        "",
    ]

    for i, f in enumerate(flights, 1):
        dep = f["depart_time"][:16].replace("T", " ") if f["depart_time"] else "?"
        arr = f["arrive_time"][:16].replace("T", " ") if f["arrive_time"] else "?"
        hours = f["duration_min"] // 60
        mins = f["duration_min"] % 60
        duration_str = f"{hours}h{mins:02d}m" if f["duration_min"] > 0 else "?"
        stops_str = "direct" if f["stops"] == 0 else f"{f['stops']} stop{'s' if f['stops'] > 1 else ''}"
        fn = f" ({f['flight_number']})" if f["flight_number"] else ""

        lines.append(
            f"{i}. {f['airline']}{fn} — €{f['price_eur']}"
        )
        lines.append(
            f"   {dep} → {arr}  [{duration_str}, {stops_str}]"
        )
        lines.append("")

    return "\n".join(lines).rstrip()
