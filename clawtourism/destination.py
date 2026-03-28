"""
destination.py — Destination intelligence via RestCountries + Wikivoyage.

No API key required. Free forever.

Sources:
  RestCountries: https://restcountries.com/v3.1/  (country facts)
  Wikivoyage:    https://en.wikivoyage.org/w/api.php  (travel guides)

Usage:
    python -m clawtourism destination info Morocco
    python -m clawtourism destination country Austria
    python -m clawtourism destination guide Barcelona

When to use:
    - "Tell me about Morocco" → destination info Morocco
    - "What currency does Austria use?" → destination country Austria
    - "What should I do in Barcelona?" → destination guide Barcelona
    - Pre-trip context enrichment → destination info <country>
"""

from __future__ import annotations

import json
import re
import urllib.request
import urllib.parse
from typing import Optional

RESTCOUNTRIES_URL = "https://restcountries.com/v3.1"
WIKIVOYAGE_URL = "https://en.wikivoyage.org/w/api.php"
TIMEOUT = 8

# Wikivoyage sections we care about (case-insensitive match)
GUIDE_SECTIONS = [
    "Understand", "See", "Do", "Eat", "Drink", "Sleep",
    "Get in", "Get around", "Stay safe", "Buy",
]


def _http_get(url: str) -> dict | list | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "clawtourism/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _strip_wiki_markup(text: str) -> str:
    """Remove wiki markup and return clean plain text."""
    # Remove {{templates}}
    text = re.sub(r'\{\{[^}]*\}\}', '', text)
    # [[link|display]] → display
    text = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', text)
    # [url text] → text
    text = re.sub(r'\[https?://\S+\s+([^\]]+)\]', r'\1', text)
    # ==headers==
    text = re.sub(r'={2,}[^=]+=+', '', text)
    # '''bold''' and ''italic''
    text = re.sub(r"'{2,3}", '', text)
    # HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Multiple blank lines → single
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def get_country_info(country_name: str) -> dict:
    """
    Return structured country facts from RestCountries.

    Returns: {name, capital, currencies, languages, timezones, calling_code,
              population, region, subregion, flag}
    """
    encoded = urllib.parse.quote(country_name)
    data = _http_get(f"{RESTCOUNTRIES_URL}/name/{encoded}?fullText=false")

    if not data or not isinstance(data, list):
        # Try search by partial name
        data = _http_get(f"{RESTCOUNTRIES_URL}/name/{encoded}")

    if not data or not isinstance(data, list) or len(data) == 0:
        return {"error": f"Country not found: {country_name}"}

    c = data[0]

    # Currencies: {"EUR": {"name": "Euro", "symbol": "€"}}
    currencies = {}
    for code, info in (c.get("currencies") or {}).items():
        currencies[code] = {
            "name": info.get("name", ""),
            "symbol": info.get("symbol", ""),
        }

    # Languages: {"deu": "German"}
    languages = list((c.get("languages") or {}).values())

    # Calling codes
    idd = c.get("idd", {})
    root = idd.get("root", "")
    suffixes = idd.get("suffixes", [""])
    calling_code = f"{root}{suffixes[0]}" if root else ""

    return {
        "name": c.get("name", {}).get("common", country_name),
        "official_name": c.get("name", {}).get("official", ""),
        "capital": (c.get("capital") or [""])[0],
        "region": c.get("region", ""),
        "subregion": c.get("subregion", ""),
        "population": c.get("population", 0),
        "currencies": currencies,
        "languages": languages,
        "timezones": c.get("timezones", []),
        "calling_code": calling_code,
        "flag": c.get("flag", ""),
    }


def get_travel_guide(destination: str, brief: bool = False) -> dict:
    """
    Return Wikivoyage travel guide sections for a destination.

    Args:
        destination: City, region, or country name
        brief: If True, truncate each section to 300 chars

    Returns: {destination, sections: {See: "...", Do: "...", Eat: "...", ...}}
    """
    def fetch_guide(page_name: str) -> dict | None:
        # Get section list
        params = urllib.parse.urlencode({
            "action": "parse",
            "page": page_name,
            "prop": "sections",
            "format": "json",
        })
        data = _http_get(f"{WIKIVOYAGE_URL}?{params}")
        if not data or "error" in data or "parse" not in data:
            return None

        sections_list = data["parse"].get("sections", [])
        result = {}

        for section in sections_list:
            title = section.get("line", "")
            # Strip HTML from title
            clean_title = re.sub(r'<[^>]+>', '', title).strip()
            # Check if this is a section we want
            if not any(g.lower() in clean_title.lower() for g in GUIDE_SECTIONS):
                continue

            idx = section.get("index", "")
            params2 = urllib.parse.urlencode({
                "action": "parse",
                "page": page_name,
                "prop": "wikitext",
                "section": idx,
                "format": "json",
            })
            section_data = _http_get(f"{WIKIVOYAGE_URL}?{params2}")
            if not section_data or "parse" not in section_data:
                continue

            raw = section_data["parse"].get("wikitext", {}).get("*", "")
            clean = _strip_wiki_markup(raw)

            if not clean:
                continue

            if brief:
                clean = clean[:300] + ("…" if len(clean) > 300 else "")

            # Use the clean section title as key
            result[clean_title] = clean

        return result if result else None

    # Try exact name first
    sections = fetch_guide(destination)

    # Fallback: try "<destination> (city)"
    if not sections:
        sections = fetch_guide(f"{destination} (city)")

    if not sections:
        return {"error": f"No Wikivoyage guide found for: {destination}"}

    return {
        "destination": destination,
        "sections": sections,
    }


def get_destination_brief(destination: str, country: Optional[str] = None) -> dict:
    """
    Combined destination brief: country facts + Wikivoyage guide summary.

    Args:
        destination: City/region name (for guide)
        country: Country name (for facts). If None, tries destination as country too.
    """
    result: dict = {"destination": destination}

    # Country facts
    country_query = country or destination
    country_info = get_country_info(country_query)
    if "error" not in country_info:
        result["country"] = country_info
    elif country != destination:
        # destination itself might not be a country — that's fine
        pass

    # Travel guide (brief mode)
    guide = get_travel_guide(destination, brief=True)
    if "error" not in guide:
        result["guide"] = guide["sections"]
    else:
        result["guide_error"] = guide["error"]

    return result


def format_country_info(info: dict) -> str:
    if "error" in info:
        return f"Country info unavailable: {info['error']}"

    currencies_str = ", ".join(
        f"{code} ({v['name']} {v['symbol']})"
        for code, v in info.get("currencies", {}).items()
    )
    languages_str = ", ".join(info.get("languages", []))
    timezones_str = ", ".join(info.get("timezones", [])[:3])
    pop = info.get("population", 0)
    pop_str = f"{pop:,}"

    return (
        f"🌍 {info.get('flag', '')} {info['name']} ({info.get('official_name', '')})\n"
        f"  Capital:     {info.get('capital', '—')}\n"
        f"  Region:      {info.get('subregion', info.get('region', '—'))}\n"
        f"  Population:  {pop_str}\n"
        f"  Currency:    {currencies_str or '—'}\n"
        f"  Language(s): {languages_str or '—'}\n"
        f"  Timezone(s): {timezones_str or '—'}\n"
        f"  Calling:     {info.get('calling_code', '—')}"
    )


def format_guide(guide_data: dict, max_section_chars: int = 500) -> str:
    if "error" in guide_data:
        return f"Travel guide unavailable: {guide_data['error']}"

    lines = [f"📖 Wikivoyage: {guide_data['destination']}"]
    for section, text in guide_data.get("sections", {}).items():
        truncated = text[:max_section_chars] + ("…" if len(text) > max_section_chars else "")
        lines.append(f"\n### {section}\n{truncated}")
    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    import sys
    args = argv if argv is not None else sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return

    cmd = args[0]

    if cmd == "info":
        if len(args) < 2:
            print("Usage: destination info <destination> [--country <country>]")
            return
        destination = args[1]
        country = None
        if "--country" in args:
            idx = args.index("--country")
            country = args[idx + 1] if idx + 1 < len(args) else None
        result = get_destination_brief(destination, country)
        if "country" in result:
            print(format_country_info(result["country"]))
            print()
        if "guide" in result:
            print(format_guide({"destination": destination, "sections": result["guide"]}))
        if "guide_error" in result:
            print(f"[Guide: {result['guide_error']}]")

    elif cmd == "country":
        if len(args) < 2:
            print("Usage: destination country <country>")
            return
        result = get_country_info(args[1])
        print(format_country_info(result))

    elif cmd == "guide":
        if len(args) < 2:
            print("Usage: destination guide <destination>")
            return
        result = get_travel_guide(" ".join(args[1:]))
        print(format_guide(result))

    else:
        print(f"Unknown command: {cmd}. Try: info, country, guide")
