"""Tests for clawtourism.flights module."""

import json
import os
from pathlib import Path
from unittest import mock

import pytest

from clawtourism.flights import (
    AIRPORT_CODES,
    _get_key,
    _parse_flight_offer,
    city_to_iata,
    search_flights,
    search_flights_report,
)


# ---------------------------------------------------------------------------
# Realistic mock API response data
# ---------------------------------------------------------------------------

def _make_offer(
    price: int,
    airline: str = "Austrian Airlines",
    carrier_code: str = "OS",
    flight_num: str = "781",
    dep: str = "2026-04-03T08:30:00",
    arr: str = "2026-04-03T10:15:00",
    segments_count: int = 1,
) -> dict:
    """Build a realistic flightOffer dict matching the Booking.com API structure."""
    leg = {
        "carriersData": [{"name": airline, "code": carrier_code}],
        "flightInfo": {"flightNumber": flight_num, "carrierCode": carrier_code},
        "departureAirport": {"code": "OTP"},
        "arrivalAirport": {"code": "VIE"},
    }
    segments = []
    for i in range(segments_count):
        segments.append({
            "departureTime": dep if i == 0 else "2026-04-03T13:00:00",
            "arrivalTime": arr if i == segments_count - 1 else "2026-04-03T12:00:00",
            "legs": [leg],
        })
    return {
        "priceBreakdown": {
            "total": {"units": price, "currencyCode": "EUR"},
        },
        "segments": segments,
    }


MOCK_API_RESPONSE = {
    "data": {
        "flightOffers": [
            _make_offer(150, "Austrian Airlines", "OS", "781",
                        "2026-04-03T08:30:00", "2026-04-03T10:15:00", 1),
            _make_offer(95, "Wizz Air", "W6", "3201",
                        "2026-04-03T06:00:00", "2026-04-03T07:45:00", 1),
            _make_offer(220, "Lufthansa", "LH", "1673",
                        "2026-04-03T11:00:00", "2026-04-03T16:30:00", 2),
            _make_offer(180, "TAROM", "RO", "341",
                        "2026-04-03T14:00:00", "2026-04-03T15:30:00", 1),
        ],
    }
}


def _mock_urlopen(response_data: dict):
    """Create a mock for urllib.request.urlopen that returns given data."""
    mock_resp = mock.MagicMock()
    mock_resp.read.return_value = json.dumps(response_data).encode()
    mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = mock.MagicMock(return_value=False)
    return mock.patch("clawtourism.flights.urllib.request.urlopen", return_value=mock_resp)


def _mock_key():
    """Mock _get_key to return a fake key."""
    return mock.patch("clawtourism.flights._get_key", return_value="fake-api-key-123")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCityToIata:
    def test_city_to_iata_lookup(self):
        """Known city returns correct IATA code."""
        assert city_to_iata("bucharest") == "OTP"
        assert city_to_iata("tel aviv") == "TLV"
        assert city_to_iata("new york") == "JFK"

    def test_city_to_iata_case_insensitive(self):
        """Lookup is case-insensitive."""
        assert city_to_iata("BUCHAREST") == "OTP"
        assert city_to_iata("Barcelona") == "BCN"
        assert city_to_iata("Tel Aviv") == "TLV"
        assert city_to_iata("  Vienna  ") == "VIE"

    def test_city_to_iata_unknown_raises(self):
        """Unknown city raises KeyError."""
        with pytest.raises(KeyError, match="Unknown city"):
            city_to_iata("atlantis")


class TestSearchFlights:
    def test_search_flights_returns_sorted_by_price(self):
        """Results are sorted by price ascending."""
        with _mock_key(), _mock_urlopen(MOCK_API_RESPONSE):
            results = search_flights("OTP", "VIE", "2026-04-03")
        assert len(results) == 4
        prices = [r["price_eur"] for r in results]
        assert prices == sorted(prices)
        assert prices[0] == 95  # Wizz Air cheapest

    def test_direct_only_filter(self):
        """direct_only=True excludes multi-segment flights."""
        with _mock_key(), _mock_urlopen(MOCK_API_RESPONSE):
            results = search_flights("OTP", "VIE", "2026-04-03", direct_only=True)
        # The Lufthansa flight has 2 segments, should be excluded
        assert len(results) == 3
        for r in results:
            assert r["stops"] == 0
            assert r["segments_count"] == 1

    def test_result_fields_complete(self):
        """Each result dict has all required fields."""
        required_fields = {
            "price_eur", "currency", "airline", "depart_time",
            "arrive_time", "duration_min", "stops", "flight_number",
            "segments_count",
        }
        with _mock_key(), _mock_urlopen(MOCK_API_RESPONSE):
            results = search_flights("OTP", "VIE", "2026-04-03")
        for r in results:
            assert required_fields.issubset(r.keys()), f"Missing fields: {required_fields - r.keys()}"

    def test_duration_calculation(self):
        """Duration in minutes is correctly computed from dep/arr times."""
        with _mock_key(), _mock_urlopen(MOCK_API_RESPONSE):
            results = search_flights("OTP", "VIE", "2026-04-03")
        # Wizz Air: 06:00 -> 07:45 = 105 min
        wizz = [r for r in results if r["airline"] == "Wizz Air"][0]
        assert wizz["duration_min"] == 105

    def test_network_error_returns_empty(self):
        """Network errors return empty list, don't crash."""
        with _mock_key(), \
             mock.patch("clawtourism.flights.urllib.request.urlopen",
                        side_effect=Exception("Connection refused")):
            results = search_flights("OTP", "VIE", "2026-04-03")
        assert results == []

    def test_city_names_accepted(self):
        """City names are resolved to IATA codes."""
        with _mock_key(), _mock_urlopen(MOCK_API_RESPONSE):
            results = search_flights("bucharest", "vienna", "2026-04-03")
        assert len(results) > 0


class TestReportFormat:
    def test_report_format(self):
        """Report contains header, flight details, and proper formatting."""
        with _mock_key(), _mock_urlopen(MOCK_API_RESPONSE):
            report = search_flights_report("OTP", "VIE", "2026-04-03")
        assert "✈️ Flights:" in report
        assert "OTP" in report
        assert "VIE" in report
        assert "2026-04-03" in report
        assert "€" in report
        # Should have numbered entries
        assert "1." in report
        assert "direct" in report.lower() or "stop" in report.lower()

    def test_report_empty(self):
        """Empty results produce a 'no flights found' message."""
        empty_resp = {"data": {"flightOffers": []}}
        with _mock_key(), _mock_urlopen(empty_resp):
            report = search_flights_report("OTP", "VIE", "2026-04-03")
        assert "No flights found" in report


class TestGetKey:
    def test_get_key_from_file(self, tmp_path):
        """Key is read from file when it exists."""
        key_file = tmp_path / "key.txt"
        key_file.write_text("  my-secret-key-123  \n")
        with mock.patch("clawtourism.flights.KEY_FILE", key_file):
            assert _get_key() == "my-secret-key-123"

    def test_get_key_env_fallback(self, tmp_path):
        """Falls back to env var when file doesn't exist."""
        missing = tmp_path / "nonexistent.txt"
        with mock.patch("clawtourism.flights.KEY_FILE", missing), \
             mock.patch.dict(os.environ, {"RAPIDAPI_BOOKING_KEY": "env-key-456"}):
            assert _get_key() == "env-key-456"

    def test_get_key_raises_without_key(self, tmp_path):
        """Raises RuntimeError when no key source is available."""
        missing = tmp_path / "nonexistent.txt"
        with mock.patch("clawtourism.flights.KEY_FILE", missing), \
             mock.patch.dict(os.environ, {}, clear=True):
            # Ensure the env var is not set
            os.environ.pop("RAPIDAPI_BOOKING_KEY", None)
            with pytest.raises(RuntimeError, match="No RapidAPI Booking key"):
                _get_key()
