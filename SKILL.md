---
name: clawtourism
description: Full-stack travel intelligence — flight status, accommodation search, currency conversion, destination guides, places/attractions, weather, visa checks, and pre-trip checklists. Use when planning trips, booking hotels, checking flights, converting currencies, or getting destination context. Supports family trips with kids.
version: 0.2.0
homepage: https://github.com/yhyatt/ClawTourism
---

# ClawTourism

Full-stack travel intelligence. No API key needed for most modules.

---

## PYTHONPATH — Always required

```bash
SKILLS=/home/openclaw/.openclaw/workspace/skills/clawtourism
PYTHONPATH=$SKILLS python3 -m clawtourism <command>
```

---

## Module Quick Reference

| Module | What it does | Key needed? |
|---|---|---|
| `currency` | Exchange rates (Frankfurter) | ❌ Free |
| `destination` | Country facts + Wikivoyage travel guide | ❌ Free |
| `weather` | 7-14 day forecast (Open-Meteo) | ❌ Free |
| `visa_check` | Visa requirements (IL passport) | ❌ Free |
| `places` | Google Places restaurants/attractions | ✅ Google Places API |
| `accommodation` | Hotel search (Booking.com) | ✅ RapidAPI |
| `airbnb` | Airbnb search (Apify scraper) | ✅ Apify |
| `flights` | Flight price search (Booking.com) | ✅ RapidAPI |
| `flight-status` / `flight-monitor` | Live flight status (FlightRadar24) | ❌ Free |

---

## Currency (`currency.py`)

**When to use:** User asks about exchange rates, price conversions, or "how much is X in shekels?"

```bash
# Convert amount
python3 -m clawtourism currency convert 250 EUR ILS,USD,GBP
# → 250 EUR = 908.22 ILS / 287.92 USD / 216.80 GBP (rates as of 2026-03-27)

# All rates from a base currency
python3 -m clawtourism currency rates EUR

# Historical rate on a specific date
python3 -m clawtourism currency historical 2026-03-01 EUR ILS
```

**Python:**
```python
from clawtourism.currency import convert, get_rates, historical
result = convert(250, "EUR", ["ILS", "USD"])
# → {"ILS": 908.22, "USD": 287.92, "base_currency": "EUR", "date": "..."}
```

**Source:** `api.frankfurter.app` — free, no key, central bank data, 150+ currencies.

---

## Destination Intelligence (`destination.py`)

**When to use:** User asks "what's Morocco like?", "what currency does Austria use?", "what to do in Barcelona?", or pre-trip context enrichment.

```bash
# Full brief: country facts + travel guide summary
python3 -m clawtourism destination info Vienna --country Austria

# Country facts only (fast, ~1 sec)
python3 -m clawtourism destination country Morocco

# Full Wikivoyage travel guide (See, Do, Eat, Drink, Sleep, Get in, Get around)
python3 -m clawtourism destination guide Barcelona
```

**Python:**
```python
from clawtourism.destination import get_country_info, get_travel_guide, get_destination_brief

# Country facts: currency, language, timezone, calling code, capital
info = get_country_info("Austria")
# → {"name": "Austria", "capital": "Vienna", "currencies": {"EUR": {...}}, "languages": ["German"], ...}

# Travel guide sections
guide = get_travel_guide("Vienna", brief=True)  # brief=True → 300 char/section
# → {"destination": "Vienna", "sections": {"See": "...", "Eat": "...", ...}}

# Combined brief (for agent use)
brief = get_destination_brief("Vienna", country="Austria")
# → {"country": {...}, "guide": {"See": "...", "Eat": "..."}}
```

**Sources:**
- RestCountries (`restcountries.com/v3.1`) — free, no key
- Wikivoyage (`en.wikivoyage.org/w/api.php`) — free, no key, community travel guides

---

## Weather (`weather.py`)

**When to use:** "What's the weather in Vienna next week?", pre-trip packing, day planning.

```python
from clawtourism.weather import get_forecast
from datetime import date
forecast = get_forecast("Vienna", start=date.today(), days=7)
# Returns list of DayForecast(date, temp_min, temp_max, description, rain_mm, wind_kph)
```

**Source:** Open-Meteo — free, no key, 16-day forecast.

---

## Visa Check (`visa_check.py`)

**When to use:** "Do I need a visa for Morocco?", pre-trip compliance check.

```python
from clawtourism.visa_check import check, check_trip_destinations, format_visa_block
result = check("Morocco")           # single destination
results = check_trip_destinations(["Vienna", "Barcelona"])  # multi-destination
```

---

## Places — Restaurants & Attractions (`places.py`)

**When to use:** "Best restaurants in Vienna?", "Things to do in Vienna with kids?", day planning.

```bash
python3 -m clawtourism places restaurants --location Vienna --top 8
python3 -m clawtourism places attractions --location Vienna --family --top 8
python3 -m clawtourism places search --location Vienna --type museum --top 5
```

**Python:**
```python
from clawtourism.places import search_restaurants, search_attractions, search_places

restaurants = search_restaurants("Vienna", radius_m=1500, min_rating=4.2, top_n=8)
attractions = search_attractions("Vienna", radius_m=2000, min_rating=4.0, top_n=8, family_types=True)
# family_types=True adds: zoo, aquarium, amusement_park (good for Zoe + Lenny)
```

**Source:** Google Places API (New) — 5,000 req/month free tier. Key at `~/.openclaw/google-places-key.txt`.

---

## Accommodation — Hotels (`accommodation.py`)

**When to use:** "Find hotels in Vienna Apr 3-10", comparing options, checking availability.

```bash
python3 -m clawtourism accommodation search \
  --city Vienna --checkin 2026-04-03 --checkout 2026-04-10 \
  --adults 2 --children-ages 5 1 --min-rating 8.5 --top 5
```

**Python:**
```python
from clawtourism.accommodation import search_and_report
report = search_and_report(
    city="Vienna", checkin="2026-04-03", checkout="2026-04-10",
    adults=2, children_ages=[5, 1], min_rating=8.5, top_n=5
)
# Returns formatted text report
```

**Source:** Booking.com via RapidAPI. Key in env/keyring.

---

## Airbnb (`airbnb.py`)

**When to use:** Apartment/house alternatives to hotels, longer stays, family trips needing space.

```bash
python3 -m clawtourism airbnb search \
  --location Vienna --checkin 2026-04-03 --checkout 2026-04-10 \
  --adults 2 --children 2 --min-bedrooms 2 --top 5
```

**Source:** Apify Airbnb scraper (slow, ~30-60 sec). Falls back gracefully if Apify is down.

---

## Flights — Price Search (`flights.py`)

**When to use:** "Find flights TLV to Vienna Apr 3", comparing prices.

```bash
python3 -m clawtourism flights search \
  --from TLV --to VIE --date 2026-04-03 \
  --adults 2 --children 2
# City names also work: --from "Tel Aviv" --to Vienna
```

**Source:** Booking.com Flights RapidAPI.

---

## Flight Status & Monitor (`flight_status_cli.py`)

**When to use:** Tracking a specific flight (departure, arrival, delays), active flight crons.

```bash
# One-shot status
python3 -m clawtourism flight-status W43048
python3 -m clawtourism flight-status W43048 --date 2026-04-03

# Stateful monitor (for crons — prints ONLY on change)
python3 -m clawtourism flight-monitor W43048 --state-file /tmp/w43048_state.json
```

Output is WhatsApp-ready Hebrew text. Uses FlightRadar24 — no key needed.

---

## Trip Scanning & Pre-Trip Checklists (`scanner.py`, `pre_trip.py`)

**When to use:** After booking confirmation emails arrive; sets up D-14/7/3/1 briefing crons.

```bash
python3 -m clawtourism scan          # scans Gmail Trips label, creates trip files
python3 -m clawtourism gap-detect    # what's missing (hotel, transfers, etc.)
```

D-7 cron automatically runs `test-live-thorough.sh` for the destination before the briefing.

---

## Assembler / Briefings (`assembler.py`, `briefing.py`)

```python
from clawtourism.briefing import generate
print(generate("msc-cruise-2026", days_before=7))
# → Full pre-trip brief: weather, packing, visa, transfers, restaurant alerts
```

---

## Testing

```bash
# Unit tests (no API calls)
cd skills/clawtourism && python3 -m pytest tests/ -q

# Weekly live smoke test (10 APIs, ~30 sec)
bash scripts/test-live-minimal.sh

# Pre-trip thorough test (all APIs for destination)
bash scripts/test-live-thorough.sh --destination Vienna --country Austria \
  --checkin 2026-04-03 --checkout 2026-04-10
```
