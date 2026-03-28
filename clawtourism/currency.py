"""
currency.py — Frankfurter Exchange Rate API integration for clawtourism.

Free, no API key, no rate limits. Data from central banks.
URL: https://api.frankfurter.dev

Usage:
    python -m clawtourism currency convert 250 EUR ILS
    python -m clawtourism currency convert 1200 USD ILS,EUR,GBP
    python -m clawtourism currency rates EUR
    python -m clawtourism currency historical 2026-03-01 EUR ILS

When to use:
    - "How much is €250 in shekels?" → currency convert 250 EUR ILS
    - "What are EUR rates today?" → currency rates EUR
    - "What was the rate on date X?" → currency historical <date> EUR ILS
"""

from __future__ import annotations

import json
import urllib.request
import urllib.parse
from typing import Optional

BASE_URL = "https://api.frankfurter.app"
TIMEOUT = 5


def _get(path: str) -> dict:
    url = f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "clawtourism/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def get_rates(base: str = "EUR") -> dict:
    """Return all exchange rates from a base currency."""
    data = _get(f"/latest?from={base.upper()}")
    if "error" in data:
        return data
    return {
        "base": data.get("base"),
        "date": data.get("date"),
        "rates": data.get("rates", {}),
    }


def convert(amount: float, from_currency: str, to_currencies: list[str]) -> dict:
    """
    Convert amount from one currency to one or more target currencies.

    Returns: {"ILS": 1045.2, "GBP": 211.3, "date": "2026-03-28", "base_amount": 250, "base_currency": "EUR"}
    """
    to_str = ",".join(c.upper() for c in to_currencies)
    from_upper = from_currency.upper()
    data = _get(f"/latest?amount={amount}&from={from_upper}&to={to_str}")
    if "error" in data:
        return data
    result = {
        "base_amount": amount,
        "base_currency": from_upper,
        "date": data.get("date"),
        **data.get("rates", {}),
    }
    return result


def historical(date: str, base: str, to_currencies: list[str]) -> dict:
    """
    Get historical exchange rates for a specific date (YYYY-MM-DD).

    Returns same shape as get_rates() but for the given date.
    """
    to_str = ",".join(c.upper() for c in to_currencies)
    data = _get(f"/{date}?from={base.upper()}&to={to_str}")
    if "error" in data:
        return data
    return {
        "base": data.get("base"),
        "date": data.get("date"),
        "rates": data.get("rates", {}),
    }


def format_conversion(result: dict) -> str:
    """Human-readable conversion result."""
    if "error" in result:
        return f"Currency conversion unavailable: {result['error']}"
    lines = []
    base = result.get("base_currency", "?")
    amount = result.get("base_amount", 1)
    date = result.get("date", "?")
    for currency, value in result.items():
        if currency in ("base_currency", "base_amount", "date"):
            continue
        lines.append(f"  {amount} {base} = {value:,.2f} {currency}")
    lines.append(f"  (rates as of {date})")
    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    import sys
    args = argv if argv is not None else sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return

    cmd = args[0]

    if cmd == "convert":
        if len(args) < 4:
            print("Usage: currency convert <amount> <FROM> <TO[,TO2,...]>")
            return
        amount = float(args[1])
        from_c = args[2]
        to_list = [c.strip() for c in args[3].split(",")]
        result = convert(amount, from_c, to_list)
        print(format_conversion(result))

    elif cmd == "rates":
        base = args[1] if len(args) > 1 else "EUR"
        result = get_rates(base)
        if "error" in result:
            print(f"Error: {result['error']}")
            return
        print(f"Rates from {result['base']} ({result['date']}):")
        for currency, rate in sorted(result["rates"].items()):
            print(f"  1 {result['base']} = {rate:,.4f} {currency}")

    elif cmd == "historical":
        if len(args) < 4:
            print("Usage: currency historical <YYYY-MM-DD> <FROM> <TO[,TO2,...]>")
            return
        date = args[1]
        from_c = args[2]
        to_list = [c.strip() for c in args[3].split(",")]
        result = historical(date, from_c, to_list)
        if "error" in result:
            print(f"Error: {result['error']}")
            return
        print(f"Rates from {result['base']} on {result['date']}:")
        for currency, rate in sorted(result["rates"].items()):
            print(f"  1 {result['base']} = {rate:,.4f} {currency}")

    else:
        print(f"Unknown command: {cmd}. Try: convert, rates, historical")
