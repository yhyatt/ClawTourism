<p align="center">
  <img src="assets/clawtourism-cover.jpg" alt="ClawTourism" width="640"/>
</p>

<h1 align="center">🧳 ClawTourism</h1>
<h3 align="center">Full-Stack Travel Intelligence for OpenClaw Agents</h3>

<p align="center">
  Currency conversion · Destination guides · Hotel & Airbnb search · Flight tracking<br/>
  Weather forecasts · Restaurant discovery · Visa checks · Pre-trip briefings<br/>
  <strong>Most modules work with zero API keys.</strong>
</p>

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://github.com/yhyatt/ClawTourism)
[![OpenClaw Skill](https://img.shields.io/badge/OpenClaw-Skill-red)](https://clawhub.ai/skills/clawtourism)
[![Version](https://img.shields.io/badge/version-0.3.0-blue)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-146%20passing-brightgreen)](https://github.com/yhyatt/ClawTourism)

</div>

<p align="center">
  <a href="#-modules">Modules</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-api-keys">API Keys</a> •
  <a href="#-pre-trip-pipeline">Pre-Trip Pipeline</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-testing">Testing</a>
</p>

---

## 📦 Modules

### Free — No API Key Required

| Module | What it does | Added | Source |
|--------|-------------|-------|--------|
| **`currency`** | Exchange rates, conversions, historical data | Mar 28 | Frankfurter (central bank data) |
| **`destination`** | Country facts + full travel guide (See/Do/Eat/Sleep/Get in) | Mar 28 | RestCountries + Wikivoyage |
| **`weather`** | 7–14 day forecast, temp, rain, wind | Mar 27 | Open-Meteo |
| **`visa_check`** | Entry requirements for Israeli passport, 35+ countries | Mar 27 | Built-in lookup table |
| **`flight-status`** | Live flight status, delays, gate, arrival | Mar 03 | FlightRadar24 (unofficial) |
| **`flight-monitor`** | Stateful cron monitor — fires only on changes | Mar 03 | FlightRadar24 (unofficial) |

### Requires API Key

| Module | What it does | Added | Key |
|--------|-------------|-------|-----|
| **`places`** | Restaurants, attractions, POIs near a location | Mar 27 | Google Places API |
| **`accommodation`** | Hotel search with ratings, prices, reviews | Mar 27 | Booking.com RapidAPI |
| **`airbnb`** | Apartment/house search | Mar 27 | Apify |
| **`flights`** | Flight price search, schedules | Mar 27 | Booking.com RapidAPI |

---

## 🚀 Quick Start

ClawTourism is not pip-installed — use `PYTHONPATH`:

```bash
SKILLS=/home/openclaw/.openclaw/workspace/skills/clawtourism
alias ct="PYTHONPATH=$SKILLS python3 -m clawtourism"
```

### Currency

```bash
ct currency convert 250 EUR ILS,USD,GBP
# 250.0 EUR = 908.22 ILS
# 250.0 EUR = 287.92 USD
# 250.0 EUR = 216.80 GBP
# (rates as of 2026-03-27)

ct currency rates EUR          # all exchange rates from EUR
ct currency historical 2026-03-01 EUR ILS  # rate on a specific date
```

### Destination Intelligence

```bash
ct destination info Vienna --country Austria
# 🌍 🇦🇹 Austria (Republic of Austria)
#   Capital:     Vienna
#   Currency:    EUR (euro €)
#   Language(s): German
#   Timezone(s): UTC+01:00
#   Calling:     +43
#
# 📖 Wikivoyage: Vienna
# ### See
# Vienna has a rich history as the capital city of the monarchy...
# ### Eat
# ...

ct destination country Morocco   # country facts only (fast)
ct destination guide Barcelona   # full Wikivoyage guide (See/Do/Eat/Drink/Sleep/Get in/Get around)
```

### Weather

```bash
ct weather Vienna --days 7
```

### Places

```bash
ct places restaurants --location Vienna --top 8
ct places attractions --location Vienna --family --top 8   # family=True adds zoo, aquarium, etc.
ct places search --location Vienna --type museum --top 5
```

### Accommodation

```bash
ct accommodation search \
  --city Vienna --checkin 2026-04-03 --checkout 2026-04-10 \
  --adults 2 --children-ages 5 1 --min-rating 8.5 --top 5
```

### Airbnb

```bash
ct airbnb search \
  --location Vienna --checkin 2026-04-03 --checkout 2026-04-10 \
  --adults 2 --children 2 --min-bedrooms 2 --top 5
```

### Flights

```bash
ct flights search --from TLV --to VIE --date 2026-04-03 --adults 2 --children 2
# City names also work: --from "Tel Aviv" --to Vienna
```

### Flight Status

```bash
ct flight-status W43048
ct flight-status W43048 --date 2026-04-03

# Stateful monitor — prints only on change (designed for crons)
ct flight-monitor W43048 --state-file /tmp/w43048_state.json
```

Output is WhatsApp-ready Hebrew text.

### Trip Scanning & Pre-Trip Briefings

```bash
ct scan          # scans Gmail label:Trips → builds trip files
ct gaps          # gap detector (missing hotel, return flight, etc.)
ct checklists    # sets up D-14/7/3/1 briefing crons
```

---

## 🔑 API Keys

| Key | Where | Enables |
|-----|-------|---------|
| `~/.openclaw/google-places-key.txt` | [Google Cloud Console](https://console.cloud.google.com) | `places` module (5K req/month free) |
| `RAPIDAPI_KEY` (env/keyring) | [RapidAPI](https://rapidapi.com) | `accommodation`, `flights` (Booking.com) |
| Apify token (keyring) | [Apify Console](https://apify.com) | `airbnb` module |
| `GOG_KEYRING_PASSWORD` | [gog skill](https://clawhub.ai/skills/gog) | Gmail scanning (`scan` command) |

**No key needed:** `currency`, `destination`, `weather`, `visa_check`, `flight-status`, `flight-monitor`

---

## 🔔 Pre-Trip Pipeline

ClawTourism sets up proactive briefings automatically when a trip is saved.

### Timeline

| Checkpoint | What fires |
|-----------|-----------|
| **On save** | Visa check for all destination countries |
| **D-14** | Passport expiry, insurance, cruise check-in, document gaps |
| **D-7** | 🔬 **Full stack integration test** for destination (see Testing), then: packing list, currency rate, destination guide summary |
| **D-3** | Weather forecast + logistics checklist |
| **D-1** | Flight details, gate, transfer options. Flight tracking starts. |
| **Day-of** | Gate changes, delays >15min, boarding, cancellations — every 45 min |

### Restaurant Release-Day Alerts

```
🍽️ Don Angie opens reservations TOMORROW at midnight ET.
   Open Resy now → resy.com/cities/nyc/don-angie
```

---

## 🏗️ Architecture

```
clawtourism/
│
├── ── Free modules (no API key) ──────────────────────────────────────
├── currency.py           Exchange rates via Frankfurter API
├── destination.py        RestCountries + Wikivoyage destination intelligence  
├── weather.py            Open-Meteo 7–14 day forecast
├── visa_check.py         IL passport requirements, 35+ countries
├── flight_status_cli.py  FlightRadar24 live status + stateful monitor
│
├── ── API-key modules ────────────────────────────────────────────────
├── places.py             Google Places restaurants/attractions/POIs
├── accommodation.py      Booking.com hotel search (RapidAPI)
├── airbnb.py             Airbnb search via Apify scraper
├── flights.py            Booking.com flight price search (RapidAPI)
│
├── ── Trip pipeline ──────────────────────────────────────────────────
├── scanner.py            Gmail label:Trips scanning (via gog)
├── extractor.py          Booking extraction from email text
├── pdf_extractor.py      PDF tickets, vouchers, confirmations
├── assembler.py          Groups emails → Trip objects
├── gap_detector.py       Missing items: return flight, hotel, docs
├── renderer.py           Markdown + JSON trip summaries
├── store.py              Persistence → memory/trips/{slug}.json
│
├── ── Proactive intelligence ─────────────────────────────────────────
├── briefing.py           Consolidated checkpoint briefings (live data at fire time)
├── pre_trip.py           D-14/7/3/1 cron specs (D-7 triggers full stack test)
├── flight_monitor.py     D-1 alert + day-of polling crons
├── resy_alerts.py        Restaurant release-day alerts (Resy 28d, OT 30d)
├── day_planner.py        Morning/afternoon/evening day plans
├── packing.py            Weather + kids + trip-type packing lists
├── packing_profile.py    Persistent per-member packing templates
└── transfers.py          Airport/pier → hotel suggestions
```

---

## 🧪 Testing

146 unit tests, all mocked (no real API calls):

```bash
cd skills/clawtourism
python3 -m pytest tests/ -q
# 146 passed in 0.2s
```

### Live API Smoke Tests

**Weekly minimal** — 10 APIs, ~30 seconds, minimal quota:
```bash
bash scripts/test-live-minimal.sh
# ✅ Frankfurter  ✅ RestCountries  ✅ Wikivoyage  ✅ Google Places
# ✅ Booking.com  ✅ FlightRadar24  ✅ Tabit       ✅ Ontopo
# ✅ Open-Meteo   ✅ Clawevents registry
```

**Pre-trip thorough** — full destination stack, runs automatically at D-7:
```bash
bash scripts/test-live-thorough.sh \
  --destination Vienna --country Austria \
  --checkin 2026-04-03 --checkout 2026-04-10
# Tests: currency, country facts, Wikivoyage guide, Booking.com, Airbnb,
#        Google Places (restaurants + attractions), flights, FR24, weather,
#        Tabit, Ontopo, wanttogo index, events registry, visa check
```

Crons: `weekly-skill-tests` + `weekly-live-smoke-tests` fire every Monday 9:00 AM (Jerusalem). Failures send a Telegram alert.

---

## 🤝 Works With

- 🎉 [ClawEvents](https://clawhub.ai/skills/clawevents) — event discovery for your destination
- 🍽️ [ClawCierge](https://clawhub.ai/skills/clawcierge) — restaurant booking
- 💸 [ClawBack](https://clawhub.ai/skills/clawback) — group expense splitting

---

## 📄 License

MIT — see [LICENSE](LICENSE)
