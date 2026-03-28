"""Tests for foursquare.py — Foursquare Places API integration."""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from clawtourism.foursquare import (
    search_places,
    search_restaurants,
    search_bars,
    search_cafes,
    get_place_details,
    format_place,
    format_report,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mock_response(data: dict):
    mock = MagicMock()
    mock.read.return_value = json.dumps(data).encode()
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


SAMPLE_PLACES = {
    "results": [
        {
            "fsq_place_id": "abc123",
            "name": "Café Central",
            "rating": 8.6,
            "price": 2,
            "popularity": 0.999,
            "categories": [{"fsq_category_id": "cafe01", "name": "Café", "short_name": "Café", "plural_name": "Cafés", "icon": {"prefix": "https://", "suffix": ".png"}}],
            "location": {"address": "Herrengasse 14", "locality": "Wien", "country": "AT", "formatted_address": "Herrengasse 14, 1010 Wien"},
            "tastes": ["great coffee", "historic", "cozy"],
            "hours": {"open_now": True},
        },
        {
            "fsq_place_id": "def456",
            "name": "Low Rated Place",
            "rating": 5.0,
            "price": 1,
            "popularity": 0.1,
            "categories": [{"fsq_category_id": "rest01", "name": "Restaurant", "short_name": "Restaurant", "plural_name": "Restaurants", "icon": {"prefix": "https://", "suffix": ".png"}}],
            "location": {"address": "Some St", "locality": "Wien", "country": "AT", "formatted_address": "Some St, Wien"},
            "tastes": [],
        },
        {
            "fsq_place_id": "ghi789",
            "name": "Gerstner",
            "rating": 8.7,
            "price": 1,
            "popularity": 0.995,
            "categories": [{"fsq_category_id": "cafe02", "name": "Bakery", "short_name": "Bakery", "plural_name": "Bakeries", "icon": {"prefix": "https://", "suffix": ".png"}}],
            "location": {"address": "Kärntner Str. 51", "locality": "Wien", "country": "AT", "formatted_address": "Kärntner Str. 51, 1010 Wien"},
            "tastes": ["pastries", "desserts"],
        },
    ]
}

SAMPLE_DETAILS = {
    "fsq_place_id": "abc123",
    "name": "Café Central",
    "rating": 8.6,
    "price": 2,
    "location": {"formatted_address": "Herrengasse 14, 1010 Wien"},
    "categories": [{"name": "Café"}],
    "tastes": ["great coffee", "historic"],
}


# ── search_places ─────────────────────────────────────────────────────────────

class TestSearchPlaces:
    def test_returns_places_filtered_by_min_rating(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(SAMPLE_PLACES)):
            results = search_places("Vienna", query="restaurant", min_rating=7.0, top_n=10)
        # Low Rated Place (5.0) should be filtered out
        names = [r["name"] for r in results]
        assert "Café Central" in names
        assert "Low Rated Place" not in names

    def test_respects_top_n(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(SAMPLE_PLACES)):
            results = search_places("Vienna", min_rating=0, top_n=2)
        assert len(results) <= 2

    def test_uses_near_for_city_names(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(SAMPLE_PLACES)) as mock_open:
            search_places("Vienna", min_rating=0, top_n=5)
        req = mock_open.call_args[0][0]
        assert "near=Vienna" in req.full_url

    def test_uses_ll_for_coordinates(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(SAMPLE_PLACES)) as mock_open:
            search_places("48.2,16.35", min_rating=0, top_n=5)
        req = mock_open.call_args[0][0]
        assert "ll=48.2" in req.full_url

    def test_api_error_returns_empty_list(self):
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            results = search_places("Vienna", min_rating=0, top_n=5)
        assert results == []

    def test_includes_query_param(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(SAMPLE_PLACES)) as mock_open:
            search_places("Vienna", query="tapas", min_rating=0, top_n=5)
        req = mock_open.call_args[0][0]
        assert "query=tapas" in req.full_url

    def test_uses_bearer_auth(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(SAMPLE_PLACES)) as mock_open, \
             patch("clawtourism.foursquare._get_key", return_value="TEST_KEY"):
            search_places("Vienna", min_rating=0, top_n=3)
        req = mock_open.call_args[0][0]
        assert req.get_header("Authorization") == "Bearer TEST_KEY"

    def test_uses_api_version_header(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(SAMPLE_PLACES)) as mock_open:
            search_places("Vienna", min_rating=0, top_n=3)
        req = mock_open.call_args[0][0]
        assert req.get_header("X-places-api-version") == "2025-06-17"


# ── search_restaurants / bars / cafes ─────────────────────────────────────────

class TestHelperSearches:
    def test_search_restaurants_uses_restaurant_query(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(SAMPLE_PLACES)) as mock_open:
            search_restaurants("Vienna", top_n=5)
        req = mock_open.call_args[0][0]
        assert "query=restaurant" in req.full_url

    def test_search_bars_uses_bar_query(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(SAMPLE_PLACES)) as mock_open:
            search_bars("Tel Aviv", top_n=5)
        req = mock_open.call_args[0][0]
        assert "query=bar" in req.full_url

    def test_search_bars_custom_type(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(SAMPLE_PLACES)) as mock_open:
            search_bars("Tel Aviv", top_n=5, bar_type="wine bar")
        req = mock_open.call_args[0][0]
        assert "wine" in req.full_url

    def test_search_cafes_uses_coffee_query(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(SAMPLE_PLACES)) as mock_open:
            search_cafes("Barcelona", top_n=5)
        req = mock_open.call_args[0][0]
        assert "query=coffee" in req.full_url


# ── get_place_details ─────────────────────────────────────────────────────────

class TestGetPlaceDetails:
    def test_returns_place_details(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(SAMPLE_DETAILS)):
            result = get_place_details("abc123")
        assert result["name"] == "Café Central"
        assert result["rating"] == 8.6

    def test_uses_correct_url(self):
        with patch("urllib.request.urlopen", return_value=_mock_response(SAMPLE_DETAILS)) as mock_open:
            get_place_details("abc123")
        req = mock_open.call_args[0][0]
        assert "/abc123" in req.full_url

    def test_api_error_returns_error_dict(self):
        with patch("urllib.request.urlopen", side_effect=Exception("not found")):
            result = get_place_details("abc123")
        assert "error" in result


# ── format_place ──────────────────────────────────────────────────────────────

class TestFormatPlace:
    def test_formats_place_with_all_fields(self):
        place = SAMPLE_PLACES["results"][0]
        output = format_place(place, idx=1)
        assert "Café Central" in output
        assert "8.6" in output
        assert "Wien" in output

    def test_shows_open_now(self):
        place = SAMPLE_PLACES["results"][0]  # has hours.open_now=True
        output = format_place(place)
        assert "✅" in output

    def test_shows_price_as_euros(self):
        place = SAMPLE_PLACES["results"][0]  # price=2
        output = format_place(place)
        assert "€€" in output

    def test_shows_tastes(self):
        place = SAMPLE_PLACES["results"][0]
        output = format_place(place)
        assert "great coffee" in output or "historic" in output or "cozy" in output

    def test_numbered_prefix(self):
        place = SAMPLE_PLACES["results"][0]
        output = format_place(place, idx=3)
        assert output.startswith("3.")


# ── format_report ─────────────────────────────────────────────────────────────

class TestFormatReport:
    def test_empty_list_returns_no_results(self):
        output = format_report([], "Test Title")
        assert "No results" in output

    def test_title_in_report(self):
        places = [SAMPLE_PLACES["results"][0]]
        output = format_report(places, "🍽️ Restaurants near Vienna")
        assert "Restaurants near Vienna" in output

    def test_all_places_included(self):
        places = [p for p in SAMPLE_PLACES["results"] if p.get("rating", 0) >= 7.0]
        output = format_report(places, "Test")
        assert "Café Central" in output
        assert "Gerstner" in output
