# Changelog

## [0.3.0] - 2026-03-28

### Added
- **`currency.py`** — Exchange rates via Frankfurter API (free, no key, central bank data, 150+ currencies). Convert, get all rates, historical lookups. CLI: `currency convert/rates/historical`
- **`destination.py`** — Destination intelligence combining RestCountries (country facts: currency, language, timezone, calling code) and Wikivoyage (full travel guides: See/Do/Eat/Drink/Sleep/Get in/Get around). CLI: `destination info/country/guide`
- **Live test suite** — `scripts/test-live-minimal.sh` (10 APIs, weekly) and `scripts/test-live-thorough.sh` (full destination stack, auto-fires at D-7 pre-trip)
- Weekly crons: `weekly-skill-tests` (unit tests, Mon 9AM) and `weekly-live-smoke-tests` (live API check, Mon 9AM)
- D-7 pre-trip cron now runs `test-live-thorough.sh` before the briefing — catches broken integrations a week before departure

### Fixed
- `flight_status_cli.py` — timezone now resolved from airport IATA code (was hardcoded `+3`). European DST handled correctly using `ZoneInfo`
- `pre_trip.py` — D-7 checkpoint enriched with integration test block before briefing


## [0.2.0] - 2026-03-27

### Added
- **`accommodation.py`** — Hotel search via Booking.com RapidAPI. Search by city/district, check-in/out dates, adults + children ages, min rating. Returns ranked hotels with prices, scores, and reviews. CLI: `accommodation search/details`
- **`airbnb.py`** — Airbnb listing search via Apify scraper. Filters by location, dates, guests, bedrooms, rating. Returns ranked apartments/houses. CLI: `airbnb search`
- **`places.py`** — Google Places API (New). Restaurants, attractions, POIs near a city or neighborhood. Supports family filter (adds zoo, aquarium, amusement park). CLI: `places restaurants/attractions/search`
- **`flights.py`** — Flight price search via Booking.com RapidAPI. Origin/destination by IATA code or city name, date, passengers. 14 tests. CLI: `flights search`
- **`weather.py`** — Open-Meteo 7–14 day forecast (free, no key). City-name geocoding built in
- **`packing.py`** — Weather-aware packing lists (kids + trip-type aware)
- **`packing_profile.py`** — Persistent per-member packing templates
- **`day_planner.py`** — Morning/afternoon/evening day plans; cruise port days with back-by constraint
- **`transfers.py`** — Airport/pier → hotel suggestions (TLV, EWR, JFK, BCN, Piraeus)
- **`visa_check.py`** — Israeli passport entry requirements, 35+ countries


## [0.1.0] - 2026-03-03

### Added
- Email scanner (Gmail label:Trips, forwarded email traversal, RTL Hebrew)
- PDF ticket/voucher parser
- Trip assembler — flights, hotels, restaurants, cruises → unified Trip model
- Gap detector — missing return flights, accommodation, documents, kids considerations
- Markdown + JSON trip renderer
- Pre-trip checklists: D-14, D-7, D-3, D-1 cron specs
- Flight status/monitor — live status, delays, gate, arrival via FlightRadar24 (no key)
- Restaurant release-day alerts (Resy 28-day, OpenTable 30-day)
- Known booking sources: El Al, Wizz Air, Blue Bird, Amsalem, MSC, Booking.com, Airbnb, Club Med
