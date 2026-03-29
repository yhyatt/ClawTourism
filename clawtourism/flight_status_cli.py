"""
flight_status_cli.py — Token-free flight status via FlightRadar24 API.

No API key required. Used by group agents to check flight status without
spending tokens on web search / scraping trial-and-error.

Usage:
    python -m clawtourism flight-status <FLIGHT_NUMBER> [--date YYYY-MM-DD]
    python -m clawtourism flight-monitor <FLIGHT_NUMBER> --state-file <PATH>
                                          [--date YYYY-MM-DD] [--expires YYYY-MM-DD]

flight-status:
    Prints current status, departure, arrival, delay.
    Exits 0. If nothing found, prints nothing.

flight-monitor:
    Stateful. Only prints if status changed since last run (for cron use).
    State stored in --state-file (JSON). Designed for group agent crons.
    Prints a WhatsApp-ready message if something changed, nothing otherwise.

    IMPORTANT — always pass --date and --expires when creating crons:
    - --date YYYY-MM-DD   The actual flight date. Without this, the monitor
                          defaults to today and will track a different flight
                          (same number, next day) after the original lands.
    - --expires YYYY-MM-DD  Hard expiry: if today > expiry, exits silently.
                            Set to flight_date + 1 day. This is the safety net
                            that prevents zombie crons from running forever.

    The monitor also self-exits if the state file shows the flight already
    landed (arr_real_ts set), regardless of --expires.

Examples:
    python -m clawtourism flight-status W43048
    python -m clawtourism flight-status W43048 --date 2026-03-27
    python -m clawtourism flight-monitor W43048 --state-file /tmp/w43048.json \\
        --date 2026-03-27 --expires 2026-03-28
"""

import json
import sys
import argparse
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional


FR24_BASE = "https://api.flightradar24.com/common/v1/flight/list.json"
FR24_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# IATA airport code → timezone (expand as needed)
AIRPORT_TZ = {
    # Israel
    "TLV": "Asia/Jerusalem",
    "VDA": "Asia/Jerusalem",  # Eilat
    "ETH": "Asia/Jerusalem",  # Eilat Ovda
    # Europe
    "ATH": "Europe/Athens",
    "BBU": "Europe/Bucharest",
    "OTP": "Europe/Bucharest",
    "BCN": "Europe/Madrid",
    "CDG": "Europe/Paris",
    "MRS": "Europe/Paris",    # Marseille
    "GOA": "Europe/Rome",     # Genoa
    "PMO": "Europe/Rome",     # Palermo
    "MLA": "Europe/Malta",    # Valletta
    "FCO": "Europe/Rome",
    "LHR": "Europe/London",
    "AMS": "Europe/Amsterdam",
    "FRA": "Europe/Berlin",
    "JFK": "America/New_York",
    "EWR": "America/New_York",
    "LAX": "America/Los_Angeles",
    # Egypt
    "TCP": "Africa/Cairo",    # Taba
    "CAI": "Africa/Cairo",
}

def get_airport_tz(iata_code: Optional[str], fallback: str = "Asia/Jerusalem") -> str:
    """Return timezone string for an IATA airport code."""
    if not iata_code:
        return fallback
    return AIRPORT_TZ.get(iata_code.upper(), fallback)


def fetch_fr24(flight_number: str) -> list:
    import urllib.request
    url = f"{FR24_BASE}?fetchBy=flight&page=1&limit=10&query={flight_number}"
    req = urllib.request.Request(url, headers=FR24_HEADERS)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    return data.get("result", {}).get("response", {}).get("data", [])


def find_flight_for_date(flights: list, date_str: str) -> Optional[dict]:
    for f in flights:
        dep_sched = f.get("time", {}).get("scheduled", {}).get("departure")
        if dep_sched:
            dep_dt = datetime.utcfromtimestamp(dep_sched)
            if dep_dt.strftime("%Y-%m-%d") == date_str:
                return f
    return None


def fmt_time(ts, tz: str = "Asia/Jerusalem") -> Optional[str]:
    """Convert UTC timestamp to local time using proper timezone (handles DST correctly).
    
    IMPORTANT: Use the airport's local timezone, not the user's timezone.
    e.g. ATH/BBU flights = 'Europe/Athens' or 'Europe/Bucharest' (UTC+2 EET, UTC+3 EEST)
         TLV flights = 'Asia/Jerusalem' (UTC+2 IST, UTC+3 IDT)
    """
    if ts is None:
        return None
    dt = datetime.fromtimestamp(ts, tz=ZoneInfo(tz))
    return dt.strftime("%H:%M")


def parse_flight(flight_number: str, f: dict) -> dict:
    times = f.get("time", {})
    dep_sched = times.get("scheduled", {}).get("departure")
    arr_sched = times.get("scheduled", {}).get("arrival")
    dep_real = times.get("real", {}).get("departure")
    arr_real = times.get("real", {}).get("arrival")
    dep_est = times.get("estimated", {}).get("departure")
    arr_est = times.get("estimated", {}).get("arrival")
    status = f.get("status", {}).get("text", "Unknown")

    # Detect timezones from airport codes in flight data
    airport_data = f.get("airport", {})
    dep_iata = airport_data.get("origin", {}).get("code", {}).get("iata")
    arr_iata = airport_data.get("destination", {}).get("code", {}).get("iata")
    dep_tz = get_airport_tz(dep_iata)
    arr_tz = get_airport_tz(arr_iata)

    delay_min = None
    if dep_est and dep_sched:
        delay_min = round((dep_est - dep_sched) / 60)
    elif dep_real and dep_sched:
        delay_min = round((dep_real - dep_sched) / 60)

    return {
        "flight_number": flight_number,
        "status": status,
        "dep_airport": dep_iata,
        "arr_airport": arr_iata,
        "dep_tz": dep_tz,
        "arr_tz": arr_tz,
        "dep_scheduled": fmt_time(dep_sched, dep_tz),
        "dep_actual": fmt_time(dep_real or dep_est, dep_tz),
        "arr_scheduled": fmt_time(arr_sched, arr_tz),
        "arr_actual": fmt_time(arr_real or arr_est, arr_tz),
        "dep_scheduled_ts": dep_sched,
        "dep_real_ts": dep_real,
        "arr_real_ts": arr_real,
        "delay_min": delay_min,
    }


def cmd_status(flight_number: str, date_str: str):
    try:
        flights = fetch_fr24(flight_number)
    except Exception as e:
        print(f"Error fetching {flight_number}: {e}", file=sys.stderr)
        sys.exit(1)

    f = find_flight_for_date(flights, date_str)
    if not f:
        print(f"No flight {flight_number} found for {date_str}", file=sys.stderr)
        sys.exit(0)

    info = parse_flight(flight_number, f)
    delay_str = f" (+{info['delay_min']}m delay)" if info['delay_min'] and info['delay_min'] > 5 else ""
    arr_str = info['arr_actual'] or info['arr_scheduled'] or "?"
    dep_str = info['dep_actual'] or info['dep_scheduled'] or "?"

    print(f"✈️ {info['flight_number']} — {info['status']}")
    print(f"   Departure: {dep_str}{delay_str}")
    print(f"   Arrival:   {arr_str}")


def cmd_monitor(flight_number: str, date_str: str, state_file: str, expires_str: Optional[str] = None):
    """
    Stateful flight monitor. Only outputs when something noteworthy changes.

    Exits silently (no output) when:
    - Today is past --expires date (zombie-cron guard)
    - State file shows flight already landed (arr_real_ts set)
    - No flight found for the given date
    - FR24 fetch fails
    """
    today = datetime.utcnow().date()

    # ── Expiry guard: if today > expires, this flight is history ─────────────
    if expires_str:
        try:
            exp_date = datetime.strptime(expires_str, "%Y-%m-%d").date()
            if today > exp_date:
                sys.exit(0)
        except ValueError:
            pass  # bad format → ignore, continue

    # ── Already-landed guard: if state shows arr_real_ts, we're done ─────────
    try:
        with open(state_file) as fh:
            saved = json.load(fh)
        if saved.get("arr_real_ts"):
            sys.exit(0)
    except Exception:
        saved = {}

    try:
        flights = fetch_fr24(flight_number)
    except Exception:
        sys.exit(0)

    f = find_flight_for_date(flights, date_str)
    if not f:
        sys.exit(0)

    info = parse_flight(flight_number, f)

    # Use state already loaded above (or empty dict if file didn't exist)
    state = saved

    prev_status = state.get("status", "").lower()
    prev_dep_real = state.get("dep_real_ts")
    prev_arr_real = state.get("arr_real_ts")

    now_status = info["status"].lower()
    message = None

    if "landed" in now_status and "landed" not in prev_status:
        arr = info["arr_actual"] or "?"
        message = f"✈️ {flight_number} נחתה — {arr} 🛬"

    elif info["dep_real_ts"] and not prev_dep_real:
        dep = info["dep_actual"] or "?"
        arr = info["arr_actual"] or info["arr_scheduled"] or "?"
        if info["delay_min"] and info["delay_min"] > 5:
            message = f"✈️ {flight_number} המריאה ({dep}) — עיכוב {info['delay_min']} דק׳\nנחיתה צפויה: {arr}"
        else:
            message = f"✈️ {flight_number} המריאה — {dep}\nנחיתה צפויה: {arr}"

    elif info["delay_min"] and info["delay_min"] > 15:
        prev_delay = state.get("delay_min", 0) or 0
        if abs(info["delay_min"] - prev_delay) >= 10:
            arr = info["arr_actual"] or info["arr_scheduled"] or "?"
            message = f"⏰ {flight_number} עיכוב {info['delay_min']} דק׳ — נחיתה צפויה {arr}"

    # Save state
    try:
        with open(state_file, "w") as fh:
            json.dump({
                "status": now_status,
                "dep_real_ts": info["dep_real_ts"],
                "arr_real_ts": info["arr_real_ts"],
                "delay_min": info["delay_min"],
                "last_check": datetime.utcnow().isoformat(),
            }, fh)
    except Exception:
        pass

    if message:
        print(message)


def main(argv=None):
    parser = argparse.ArgumentParser(description="ClawTourism flight tools")
    sub = parser.add_subparsers(dest="cmd")

    p_status = sub.add_parser("flight-status", help="Get current flight status")
    p_status.add_argument("flight_number")
    p_status.add_argument("--date", default=datetime.utcnow().strftime("%Y-%m-%d"))

    p_monitor = sub.add_parser("flight-monitor", help="Stateful monitor (prints only on change)")
    p_monitor.add_argument("flight_number")
    p_monitor.add_argument("--date", default=datetime.utcnow().strftime("%Y-%m-%d"),
                           help="Flight departure date YYYY-MM-DD (REQUIRED in practice — "
                                "omitting defaults to today, which tracks the wrong flight "
                                "after the original has landed)")
    p_monitor.add_argument("--expires", default=None,
                           help="Hard expiry date YYYY-MM-DD (set to flight_date + 1). "
                                "After this date the monitor exits silently — zombie-cron guard.")
    p_monitor.add_argument("--state-file", required=True)

    args = parser.parse_args(argv)

    if args.cmd == "flight-status":
        cmd_status(args.flight_number, args.date)
    elif args.cmd == "flight-monitor":
        cmd_monitor(args.flight_number, args.date, args.state_file, args.expires)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
