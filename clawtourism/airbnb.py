"""
airbnb.py — Airbnb search via Apify scraper.

Uses Apify actor GsNzxEKzE2vQ5d9HN (tri_angle/airbnb-scraper).

API key: stored at ~/.openclaw/apify-key.txt or APIFY_TOKEN env var.

Usage:
    python -m clawtourism airbnb search \
        --location "Neubau, Vienna, Austria" \
        --checkin 2026-04-03 --checkout 2026-04-10 \
        --adults 2 --children 2 --min-bedrooms 2 \
        --top 8
"""

from __future__ import annotations

import os
import re
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional

APIFY_ACTOR = "GsNzxEKzE2vQ5d9HN"  # tri_angle/airbnb-scraper
APIFY_BASE = "https://api.apify.com/v2"
KEY_FILE = Path.home() / ".openclaw" / "apify-key.txt"
USD_TO_EUR = 0.92  # approximate — update periodically


def _get_key() -> str:
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    key = os.environ.get("APIFY_TOKEN", "")
    if not key:
        raise RuntimeError(
            f"No Apify token found. Store at {KEY_FILE} or set APIFY_TOKEN env var."
        )
    return key


def _api(method: str, path: str, body: dict | None = None) -> dict:
    token = _get_key()
    url = f"{APIFY_BASE}/{path}?token={token}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _parse_price_usd(price_obj: dict | None) -> int | None:
    if not isinstance(price_obj, dict):
        return None
    label = price_obj.get("label", "")
    m = re.search(r"\$([0-9,]+)\s+total", label)
    if m:
        return int(m.group(1).replace(",", ""))
    return None


def _parse_rating(r) -> tuple[float, int]:
    if isinstance(r, dict):
        return round(r.get("guestSatisfaction", 0.0), 2), int(r.get("reviewsCount", 0))
    return 0.0, 0


def search(
    location: str,
    checkin: str,
    checkout: str,
    adults: int = 2,
    children: int = 0,
    min_bedrooms: int = 1,
    max_items: int = 20,
    timeout_secs: int = 120,
) -> list[dict]:
    """
    Run Airbnb scraper and return parsed listing dicts.
    Each dict: title, price_eur_total, price_eur_nightly, rating, reviews, bedrooms, url
    """
    airbnb_url = (
        f"https://www.airbnb.com/s/{urllib.parse.quote(location)}/homes"
        f"?checkin={checkin}&checkout={checkout}"
        f"&adults={adults}&children={children}"
        f"&min_bedrooms={min_bedrooms}"
    )

    run = _api("POST", f"acts/{APIFY_ACTOR}/runs", {
        "startUrls": [{"url": airbnb_url}],
        "maxItems": max_items,
    })
    run_id = run["data"]["id"]
    dataset_id = run["data"]["defaultDatasetId"]

    # Poll until done
    elapsed = 0
    while elapsed < timeout_secs:
        time.sleep(8)
        elapsed += 8
        status = _api("GET", f"acts/{APIFY_ACTOR}/runs/{run_id}")
        state = status["data"]["status"]
        if state in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break

    if state != "SUCCEEDED":
        raise RuntimeError(f"Apify run ended with status: {state}")

    # Fetch results
    items_data = _api("GET", f"datasets/{dataset_id}/items")
    # Note: items endpoint returns list directly (no 'data' wrapper)
    if isinstance(items_data, list):
        items = items_data
    else:
        items = items_data.get("data", {}).get("items", [])

    nights = (
        __import__("datetime").date.fromisoformat(checkout)
        - __import__("datetime").date.fromisoformat(checkin)
    ).days

    results = []
    for item in items:
        price_usd = _parse_price_usd(item.get("price", {}))
        price_eur_total = round(price_usd * USD_TO_EUR) if price_usd else None
        price_eur_nightly = round(price_eur_total / nights) if price_eur_total and nights else None
        rating, reviews = _parse_rating(item.get("rating", {}))
        results.append({
            "title": item.get("title", item.get("name", "?")),
            "price_eur_total": price_eur_total,
            "price_eur_nightly": price_eur_nightly,
            "rating": rating,
            "reviews": reviews,
            "bedrooms": item.get("bedroom", item.get("bedrooms", "?")),
            "url": item.get("url", ""),
        })

    # Sort: best rating first, then cheapest
    results.sort(key=lambda x: (-(x["rating"] or 0), x["price_eur_total"] or 9999))
    return results


def search_and_report(
    location: str,
    checkin: str,
    checkout: str,
    adults: int = 2,
    children: int = 0,
    min_bedrooms: int = 1,
    top_n: int = 8,
    min_rating: float = 4.5,
) -> str:
    """High-level: search and return formatted text report for agents."""
    try:
        results = search(
            location=location,
            checkin=checkin,
            checkout=checkout,
            adults=adults,
            children=children,
            min_bedrooms=min_bedrooms,
        )
    except Exception as e:
        return f"Airbnb search failed: {e}"

    nights = (
        __import__("datetime").date.fromisoformat(checkout)
        - __import__("datetime").date.fromisoformat(checkin)
    ).days

    filtered = [r for r in results if (r["rating"] or 0) >= min_rating]
    if not filtered:
        filtered = results

    lines = [f"🏠 Airbnb — {location} | {checkin}→{checkout} ({nights} nights)\n"]
    for r in filtered[:top_n]:
        nightly = f"€{r['price_eur_nightly']}/night" if r['price_eur_nightly'] else "?"
        total = f"€{r['price_eur_total']} total" if r['price_eur_total'] else "?"
        lines.append(
            f"⭐{r['rating']} ({r['reviews']} reviews) | {r['bedrooms']}BR | "
            f"{nightly} ({total})\n   {r['title'][:60]}\n   → {r['url'][:80]}"
        )
    return "\n".join(lines)
