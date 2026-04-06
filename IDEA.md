# ClawTourism — Full-Stack Travel Intelligence Agent

> An open-source Python toolkit that gives any AI agent the ability to search flights, track arrivals, find hotels, discover restaurants, check visas, convert currencies, and deliver pre-trip briefings — all from a single CLI.

## Problem

AI agents can reason about travel but can't actually DO anything useful: they can't check live flight status, search real hotel prices, or tell you if you need a visa. Every travel tool requires a different API, different auth, different data format. Building travel capability into an agent means wiring 10+ APIs yourself.

## Idea

A unified `python3 -m clawtourism` CLI that abstracts 12+ travel APIs into simple subcommands. Any agent (OpenClaw, Claude Code, Codex, custom) just runs a shell command and gets structured, WhatsApp-ready output. No API key management, no data parsing, no provider-specific logic.

## How It Works

1. Agent receives user request: "Find flights TLV→VIE under $300 next Friday"
2. Agent runs: `python3 -m clawtourism flights search --origin TLV --destination VIE --date 2026-05-02 --budget 300`
3. ClawTourism queries Booking.com API, parses results, returns structured text
4. Agent delivers answer to user in their native channel (WhatsApp, Telegram, etc.)

For monitoring: `flight-monitor` runs as a cron, checks FR24 every 15min, only outputs on status change. Zero-token monitoring.

## Key Decisions

- **Python over TypeScript**: Travel APIs have mature Python SDKs (requests, httpx); agent exec is shell-native
- **CLI-first, not library**: Agents exec shell commands. A library would require language-specific bindings per agent runtime
- **Token-free where possible**: Flight tracking (FR24), currency (Frankfurter), weather (Open-Meteo), visa checks, destination info — all free, no API keys
- **Paid APIs behind keys**: Hotels (Booking.com), flights (Booking.com RapidAPI), places (Google/Foursquare) — keys in `~/.openclaw/` or env vars
- **Output format: WhatsApp-ready**: Hebrew-friendly text with emoji, designed for phone screens, not JSON

## Requirements

- 12+ modules: flights, flight-status, flight-monitor, accommodation, airbnb, places, currency, destination, weather, visa_check, foursquare, briefing
- Unit tests: 146 tests covering all modules
- Live smoke tests: 10 API health checks (cron-friendly, `scripts/test-live-minimal.sh`)
- Pre-trip thorough test: validates all modules for a specific destination + dates
- Zero-dependency setup for free modules (no pip install needed for FR24/weather/currency)
- Structured output: consistent format across all modules (header, results table, footer)

## Nice to Have

- Multi-city trip planner (chain flights + hotels + activities)
- Restaurant reservation integration (TheFork, Resy, OpenTable)
- Google Maps saves ingestion (personal recommendations > generic)
- Offline caching for frequently-searched routes
- Travel budget tracker with real-time currency conversion

## Similar / Inspiration

- Google Travel (unified travel search, but no agent API)
- TripIt (itinerary management, but read-only)
- Nomad List (city data, but no booking)
- SerpApi (travel search API, but expensive and generic)

## Open Questions

- Should the briefing module include packing suggestions based on weather forecast?
- Is there demand for train/rail integration (Europe-focused)?
- Partnership opportunity with Booking.com for higher API rate limits?

## Meta

- **Author**: Yonatan Hyatt / Kai
- **Date**: 2026-04-06
- **Status**: building
- **Complexity**: high
- **Build time estimate**: ongoing (core complete, expanding modules)
- **Repo**: https://github.com/yhyatt/clawtourism
- **License**: MIT
