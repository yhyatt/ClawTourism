"""Tests for currency.py — Frankfurter exchange rate API."""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock
import urllib.error

import pytest

from clawtourism.currency import convert, get_rates, historical, format_conversion


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mock_response(data: dict):
    """Create a mock urllib response that returns JSON data."""
    mock = MagicMock()
    mock.read.return_value = json.dumps(data).encode()
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


RATES_RESPONSE = {
    "base": "EUR",
    "date": "2026-03-28",
    "rates": {
        "ILS": 4.18,
        "USD": 1.09,
        "GBP": 0.855,
        "JPY": 163.5,
    },
}

CONVERT_RESPONSE = {
    "base": "EUR",
    "date": "2026-03-28",
    "rates": {
        "ILS": 1045.0,
        "GBP": 213.75,
    },
}

HISTORICAL_RESPONSE = {
    "base": "EUR",
    "date": "2026-03-01",
    "rates": {
        "ILS": 4.10,
        "USD": 1.08,
    },
}


# ── get_rates ────────────────────────────────────────────────────────────────

class TestGetRates:
    def test_returns_rates_dict(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(RATES_RESPONSE)):
            result = get_rates("EUR")
        assert result["base"] == "EUR"
        assert result["date"] == "2026-03-28"
        assert "ILS" in result["rates"]
        assert result["rates"]["ILS"] == 4.18

    def test_default_base_is_eur(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(RATES_RESPONSE)) as mock_open:
            get_rates()
        req = mock_open.call_args[0][0]
        assert "from=EUR" in req.full_url

    def test_uppercase_base(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(RATES_RESPONSE)) as mock_open:
            get_rates("eur")
        req = mock_open.call_args[0][0]
        assert "from=EUR" in req.full_url

    def test_api_unreachable_returns_error(self):
        with patch("urllib.request.urlopen", side_effect=Exception("connection refused")):
            result = get_rates("EUR")
        assert "error" in result

    def test_returns_multiple_currencies(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(RATES_RESPONSE)):
            result = get_rates("EUR")
        assert len(result["rates"]) == 4


# ── convert ──────────────────────────────────────────────────────────────────

class TestConvert:
    def test_single_target_currency(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(CONVERT_RESPONSE)):
            result = convert(250, "EUR", ["ILS"])
        assert result["ILS"] == 1045.0
        assert result["base_currency"] == "EUR"
        assert result["base_amount"] == 250

    def test_multiple_target_currencies(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(CONVERT_RESPONSE)):
            result = convert(250, "EUR", ["ILS", "GBP"])
        assert result["ILS"] == 1045.0
        assert result["GBP"] == 213.75

    def test_includes_metadata(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(CONVERT_RESPONSE)):
            result = convert(250, "EUR", ["ILS"])
        assert "base_amount" in result
        assert "base_currency" in result
        assert "date" in result

    def test_uppercase_currencies(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(CONVERT_RESPONSE)) as mock_open:
            convert(100, "eur", ["ils", "gbp"])
        req = mock_open.call_args[0][0]
        assert "from=EUR" in req.full_url
        assert "ILS" in req.full_url

    def test_api_error_returns_error_dict(self):
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            result = convert(100, "EUR", ["ILS"])
        assert "error" in result


# ── historical ───────────────────────────────────────────────────────────────

class TestHistorical:
    def test_returns_historical_rates(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(HISTORICAL_RESPONSE)):
            result = historical("2026-03-01", "EUR", ["ILS", "USD"])
        assert result["base"] == "EUR"
        assert result["date"] == "2026-03-01"
        assert result["rates"]["ILS"] == 4.10

    def test_uses_correct_date_in_url(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(HISTORICAL_RESPONSE)) as mock_open:
            historical("2026-03-01", "EUR", ["ILS"])
        req = mock_open.call_args[0][0]
        assert "2026-03-01" in req.full_url

    def test_api_error_returns_error_dict(self):
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            result = historical("2026-03-01", "EUR", ["ILS"])
        assert "error" in result


# ── format_conversion ────────────────────────────────────────────────────────

class TestFormatConversion:
    def test_formats_nicely(self):
        result = {
            "base_currency": "EUR",
            "base_amount": 250,
            "date": "2026-03-28",
            "ILS": 1045.0,
        }
        output = format_conversion(result)
        assert "250 EUR" in output
        assert "1,045.00 ILS" in output
        assert "2026-03-28" in output

    def test_error_returns_fallback_string(self):
        result = {"error": "connection refused"}
        output = format_conversion(result)
        assert "unavailable" in output.lower()

    def test_multiple_currencies_all_shown(self):
        result = {
            "base_currency": "EUR",
            "base_amount": 100,
            "date": "2026-03-28",
            "ILS": 418.0,
            "USD": 109.0,
        }
        output = format_conversion(result)
        assert "ILS" in output
        assert "USD" in output
