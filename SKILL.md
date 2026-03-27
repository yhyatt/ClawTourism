---
name: clawtourism
description: From confirmation email to curated itinerary — automatically. Scans Gmail travel bookings, builds structured trip files, and delivers proactive intelligence: flight alerts, pre-trip checklists, day plans, visa checks, transfer suggestions, and restaurant release-day alerts. Supports family and group trips.
version: 0.1.0
homepage: https://github.com/yhyatt/ClawTourism
---

# ClawTourism

Travel intelligence skill for OpenClaw agents.

## Setup

1. Label your travel confirmation emails in Gmail with `Trips`
2. Set `GOG_KEYRING_PASSWORD` in your environment
3. (Optional) Set `AERODATABOX_API_KEY` for live flight monitoring
4. Run: `python -m clawtourism scan`

## Flight Status CLI (token-free, no API key)

```bash
# clawtourism is not pip-installed — always set PYTHONPATH:
SKILLS=/home/openclaw/.openclaw/workspace/skills/clawtourism

# One-shot status check
PYTHONPATH=$SKILLS python3 -m clawtourism flight-status W43048
PYTHONPATH=$SKILLS python3 -m clawtourism flight-status W43048 --date 2026-03-27

# Stateful monitor — prints ONLY on change (departure, landing, delay ≥15m)
# Designed for cron use in group agents
PYTHONPATH=$SKILLS python3 -m clawtourism flight-monitor W43048 --state-file /tmp/w43048_state.json
```

Output is WhatsApp-ready Hebrew text. Uses FlightRadar24 (no key needed).
Group agents: use `flight-monitor` in your cron, wire output directly to the group.

## Usage

Ask your agent:
- *"Scan my travel emails and update my trips"*
- *"What's missing from my NYC trip?"*
- *"Set up flight monitoring for my upcoming flights"*
- *"Generate a packing list for the cruise"*
- *"What's the plan for Day 3 in Barcelona?"*
- *"Do I need a visa for my next trip?"*

## Output

Trip files written to `memory/trips/{slug}.json` and `memory/trips/{slug}.md`.
Cron jobs registered for: D-14/7/3/1 checklists, flight monitoring, restaurant release-day alerts.
