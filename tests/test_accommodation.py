"""
Tests for accommodation.py (Booking.com RapidAPI).

These tests mock the HTTP layer so no real API calls are made.
"""
import pytest
from unittest.mock import patch, MagicMock
import json

from clawtourism.accommodation import (
    search_destination,
    search_hotels,
    get_hotel_reviews,
    search_and_report,
    _get_key,
)


MOCK_DESTINATION_RESPONSE = {
    "data": [
        {"dest_id": "279", "dest_type": "district", "name": "07. Neubau"},
        {"dest_id": "190454", "dest_type": "city", "name": "Vienna"},
    ]
}

MOCK_HOTELS_RESPONSE = {
    "data": {
        "hotels": [
            {
                "hotel_id": 14726732,
                "property": {
                    "name": "HeyMi Apartments Brick Lane Vienna",
                    "reviewScore": 9.5,
                    "reviewCount": 198,
                    "address": "Zieglergasse 6, Wien",
                    "priceBreakdown": {
                        "grossPrice": {"value": 929.0, "currency": "EUR"}
                    },
                },
            },
            {
                "hotel_id": 9375806,
                "property": {
                    "name": "HeyMi Apartments Mondschein",
                    "reviewScore": 9.1,
                    "reviewCount": 2223,
                    "address": "Mondscheingasse 16, Wien",
                    "priceBreakdown": {
                        "grossPrice": {"value": 936.0, "currency": "EUR"}
                    },
                },
            },
            {
                "hotel_id": 99999,
                "property": {
                    "name": "Low Rated Hotel",
                    "reviewScore": 6.0,
                    "reviewCount": 10,
                    "address": "Somewhere",
                    "priceBreakdown": {
                        "grossPrice": {"value": 500.0, "currency": "EUR"}
                    },
                },
            },
        ]
    }
}

MOCK_REVIEWS_RESPONSE = {
    "data": {
        "result": [
            {
                "average_score_out_of_10": 10,
                "title": "Great Stay With Kids",
                "pros": "Very lovely and big flat",
                "cons": "",
            },
            {
                "average_score_out_of_10": 9,
                "title": "Excellent location",
                "pros": "Brand new, everything provided",
                "cons": "None",
            },
        ]
    }
}


def make_mock_get(responses):
    """Create a mock _get that returns different responses per path."""
    call_count = [0]
    def mock_get(path, params):
        resp = responses[call_count[0] % len(responses)]
        call_count[0] += 1
        return resp
    return mock_get


class TestSearchDestination:
    def test_returns_destinations(self):
        with patch("clawtourism.accommodation._get", return_value=MOCK_DESTINATION_RESPONSE):
            results = search_destination("Neubau, Vienna")
        assert len(results) == 2
        assert results[0]["dest_id"] == "279"
        assert results[0]["dest_type"] == "district"

    def test_empty_response(self):
        with patch("clawtourism.accommodation._get", return_value={"data": []}):
            results = search_destination("Nowhere")
        assert results == []


class TestSearchHotels:
    def test_filters_by_min_rating(self):
        with patch("clawtourism.accommodation._get", return_value=MOCK_HOTELS_RESPONSE):
            results = search_hotels("279", "district", "2026-04-03", "2026-04-10", min_rating=8.5)
        # Should filter out the 6.0 rated hotel
        assert len(results) == 2
        assert all(h["rating"] >= 8.5 for h in results)

    def test_result_fields(self):
        with patch("clawtourism.accommodation._get", return_value=MOCK_HOTELS_RESPONSE):
            results = search_hotels("279", "district", "2026-04-03", "2026-04-10", min_rating=0)
        assert results[0]["hotel_id"] == 14726732
        assert results[0]["name"] == "HeyMi Apartments Brick Lane Vienna"
        assert results[0]["price_total_eur"] == 929.0
        assert results[0]["rating"] == 9.5
        assert results[0]["review_count"] == 198

    def test_no_results(self):
        with patch("clawtourism.accommodation._get", return_value={"data": {"hotels": []}}):
            results = search_hotels("279", "district", "2026-04-03", "2026-04-10")
        assert results == []


class TestGetHotelReviews:
    def test_returns_reviews(self):
        with patch("clawtourism.accommodation._get", return_value=MOCK_REVIEWS_RESPONSE):
            reviews = get_hotel_reviews(14726732, limit=2)
        assert len(reviews) == 2
        assert reviews[0]["title"] == "Great Stay With Kids"
        assert reviews[0]["pros"] == "Very lovely and big flat"

    def test_limit_respected(self):
        with patch("clawtourism.accommodation._get", return_value=MOCK_REVIEWS_RESPONSE):
            reviews = get_hotel_reviews(14726732, limit=1)
        assert len(reviews) == 1


class TestSearchAndReport:
    def test_report_contains_key_info(self):
        with patch("clawtourism.accommodation._get") as mock_get:
            mock_get.side_effect = [
                MOCK_DESTINATION_RESPONSE,
                MOCK_HOTELS_RESPONSE,
                MOCK_REVIEWS_RESPONSE,  # reviews for hotel 1
                MOCK_REVIEWS_RESPONSE,  # reviews for hotel 2
            ]
            report = search_and_report(
                city="Vienna", checkin="2026-04-03", checkout="2026-04-10",
                district="Neubau", min_rating=8.5, top_n=2, with_reviews=True
            )
        assert "Vienna" in report
        assert "HeyMi Apartments Brick Lane" in report
        assert "€" in report
        assert "⭐" in report

    def test_no_destination_found(self):
        with patch("clawtourism.accommodation._get", return_value={"data": []}):
            report = search_and_report(city="Nowhere", checkin="2026-04-03", checkout="2026-04-10")
        assert "No destination found" in report

    def test_no_apartments_available(self):
        with patch("clawtourism.accommodation._get") as mock_get:
            mock_get.side_effect = [
                MOCK_DESTINATION_RESPONSE,
                {"data": {"hotels": []}},
            ]
            report = search_and_report(city="Vienna", checkin="2026-04-03", checkout="2026-04-10")
        assert "No apartments found" in report

    def test_nightly_price_calculation(self):
        """7 nights: €929 total = €133/night"""
        with patch("clawtourism.accommodation._get") as mock_get:
            mock_get.side_effect = [
                MOCK_DESTINATION_RESPONSE,
                MOCK_HOTELS_RESPONSE,
                MOCK_REVIEWS_RESPONSE,
                MOCK_REVIEWS_RESPONSE,
            ]
            report = search_and_report(
                city="Vienna", checkin="2026-04-03", checkout="2026-04-10",
                min_rating=8.5, with_reviews=False
            )
        assert "€133/night" in report


class TestGetKey:
    def test_reads_from_file(self, tmp_path):
        key_file = tmp_path / "test-key.txt"
        key_file.write_text("test_api_key_123")
        with patch("clawtourism.accommodation.KEY_FILE", key_file):
            assert _get_key() == "test_api_key_123"

    def test_falls_back_to_env(self, tmp_path, monkeypatch):
        missing_file = tmp_path / "nonexistent.txt"
        monkeypatch.setenv("RAPIDAPI_BOOKING_KEY", "env_key_456")
        with patch("clawtourism.accommodation.KEY_FILE", missing_file):
            assert _get_key() == "env_key_456"

    def test_raises_if_no_key(self, tmp_path, monkeypatch):
        missing_file = tmp_path / "nonexistent.txt"
        monkeypatch.delenv("RAPIDAPI_BOOKING_KEY", raising=False)
        with patch("clawtourism.accommodation.KEY_FILE", missing_file):
            with pytest.raises(RuntimeError, match="No RapidAPI"):
                _get_key()
