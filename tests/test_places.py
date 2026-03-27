"""
Tests for places.py (Google Places API New).

All tests mock HTTP — no real API calls.
"""
import pytest
from unittest.mock import patch, MagicMock
import json

from clawtourism.places import (
    _geocode,
    _get_key,
    search_places,
    search_restaurants,
    search_attractions,
    format_report,
    KNOWN_COORDS,
)


MOCK_PLACES_RESPONSE = {
    "places": [
        {
            "displayName": {"text": "Schnitzelwirt"},
            "rating": 4.4,
            "userRatingCount": 11907,
            "formattedAddress": "Neubaugasse 52, 1070 Wien, Austria",
            "primaryTypeDisplayName": {"text": "Austrian restaurant"},
            "editorialSummary": {"text": "Classic Viennese schnitzel joint"},
            "priceLevel": "PRICE_LEVEL_INEXPENSIVE",
            "googleMapsUri": "https://maps.google.com/?cid=123",
            "websiteUri": "https://schnitzelwirt.at",
        },
        {
            "displayName": {"text": "Café Sperl"},
            "rating": 4.0,
            "userRatingCount": 5534,
            "formattedAddress": "Gumpendorfer Str. 11, 1060 Wien",
            "primaryTypeDisplayName": {"text": "Café"},
            "editorialSummary": {"text": "Historic Viennese coffeehouse"},
            "priceLevel": "PRICE_LEVEL_MODERATE",
            "googleMapsUri": "https://maps.google.com/?cid=456",
        },
        {
            "displayName": {"text": "Bad Rating Place"},
            "rating": 3.5,
            "userRatingCount": 50,
            "formattedAddress": "Somewhere",
            "primaryTypeDisplayName": {"text": "Restaurant"},
        },
    ]
}

MOCK_GEOCODE_RESPONSE = {
    "results": [
        {
            "geometry": {
                "location": {"lat": 48.2000, "lng": 16.3500}
            }
        }
    ]
}


class TestGeocoding:
    def test_known_coords_no_api_call(self):
        """Known cities should return coords without any HTTP call."""
        with patch("clawtourism.places.urllib.request.urlopen") as mock_url:
            lat, lng = _geocode("vienna")
        mock_url.assert_not_called()
        assert lat == KNOWN_COORDS["vienna"][0]
        assert lng == KNOWN_COORDS["vienna"][1]

    def test_known_coords_case_insensitive(self):
        lat, lng = _geocode("Vienna")
        assert (lat, lng) == KNOWN_COORDS["vienna"]

    def test_known_district(self):
        lat, lng = _geocode("neubau vienna")
        assert (lat, lng) == KNOWN_COORDS["neubau vienna"]

    def test_fallback_to_geocoding_api(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(MOCK_GEOCODE_RESPONSE).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("clawtourism.places.urllib.request.urlopen", return_value=mock_resp):
            lat, lng = _geocode("Some Unknown Place, Nowhere")
        assert lat == 48.2000
        assert lng == 16.3500

    def test_geocoding_no_results_raises(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"results": []}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("clawtourism.places.urllib.request.urlopen", return_value=mock_resp):
            with pytest.raises(ValueError, match="Could not geocode"):
                _geocode("Unknown Place XYZ")

    def test_lat_lon_string_bypasses_geocoding(self):
        with patch("clawtourism.places.urllib.request.urlopen") as mock_url:
            from clawtourism.places import search_places
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"places": []}).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_url.return_value = mock_resp
            search_places("48.2000,16.3500", ["restaurant"])
        # Only one call (to Places API), not two (geocoding + Places)
        assert mock_url.call_count == 1


class TestSearchPlaces:
    def _mock_urlopen(self, response_dict):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_dict).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_returns_filtered_results(self):
        with patch("clawtourism.places.urllib.request.urlopen",
                   return_value=self._mock_urlopen(MOCK_PLACES_RESPONSE)):
            results = search_places("vienna", ["restaurant"], min_rating=4.0, min_reviews=100)
        # Bad Rating Place (3.5 rating) and low reviews should be filtered
        assert len(results) == 2
        assert all(r["rating"] >= 4.0 for r in results)

    def test_sorted_by_rating_then_reviews(self):
        with patch("clawtourism.places.urllib.request.urlopen",
                   return_value=self._mock_urlopen(MOCK_PLACES_RESPONSE)):
            results = search_places("vienna", ["restaurant"], min_rating=4.0, min_reviews=100)
        assert results[0]["rating"] >= results[1]["rating"]

    def test_result_fields(self):
        with patch("clawtourism.places.urllib.request.urlopen",
                   return_value=self._mock_urlopen(MOCK_PLACES_RESPONSE)):
            results = search_places("vienna", ["restaurant"], min_rating=4.0, min_reviews=100)
        r = results[0]
        assert r["name"] == "Schnitzelwirt"
        assert r["rating"] == 4.4
        assert r["reviews"] == 11907
        assert r["price"] == "€"
        assert "Neubaugasse" in r["address"]
        assert r["summary"] == "Classic Viennese schnitzel joint"

    def test_price_level_mapping(self):
        with patch("clawtourism.places.urllib.request.urlopen",
                   return_value=self._mock_urlopen(MOCK_PLACES_RESPONSE)):
            results = search_places("vienna", ["restaurant"], min_rating=4.0, min_reviews=100)
        price_map = {r["name"]: r["price"] for r in results}
        assert price_map["Schnitzelwirt"] == "€"
        assert price_map["Café Sperl"] == "€€"

    def test_max_results_respected(self):
        with patch("clawtourism.places.urllib.request.urlopen",
                   return_value=self._mock_urlopen(MOCK_PLACES_RESPONSE)):
            results = search_places("vienna", ["restaurant"], min_rating=4.0, min_reviews=100, max_results=1)
        assert len(results) == 1

    def test_empty_response(self):
        with patch("clawtourism.places.urllib.request.urlopen",
                   return_value=self._mock_urlopen({"places": []})):
            results = search_places("vienna", ["restaurant"])
        assert results == []


class TestSearchHelpers:
    def _mock_urlopen(self, response_dict):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_dict).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_search_restaurants(self):
        with patch("clawtourism.places.urllib.request.urlopen",
                   return_value=self._mock_urlopen(MOCK_PLACES_RESPONSE)):
            results = search_restaurants("neubau vienna")
        assert isinstance(results, list)

    def test_search_attractions_family_types(self):
        """Family mode should include amusement_park, zoo, aquarium in the request."""
        with patch("clawtourism.places.urllib.request.urlopen",
                   return_value=self._mock_urlopen({"places": []})) as mock_url:
            search_attractions("vienna", family_types=True)
        call_body = json.loads(mock_url.call_args[0][0].data.decode())
        assert "amusement_park" in call_body["includedTypes"]
        assert "zoo" in call_body["includedTypes"]
        assert "aquarium" in call_body["includedTypes"]


class TestFormatReport:
    def test_empty_places(self):
        report = format_report([], "Test Title")
        assert "No places found" in report

    def test_contains_name_and_rating(self):
        places = [
            {"name": "Test Place", "rating": 4.5, "reviews": 1000, "address": "123 Test St",
             "type": "Restaurant", "price": "€€", "summary": "A test place", "maps_url": "", "website": ""}
        ]
        report = format_report(places, "Test")
        assert "Test Place" in report
        assert "4.5" in report
        assert "1,000" in report
        assert "€€" in report

    def test_summary_included(self):
        places = [
            {"name": "Place", "rating": 4.5, "reviews": 100, "address": "Addr",
             "type": "Café", "price": "", "summary": "Historic coffeehouse", "maps_url": "", "website": ""}
        ]
        report = format_report(places, "Cafés")
        assert "Historic coffeehouse" in report

    def test_maps_url_included(self):
        places = [
            {"name": "Place", "rating": 4.5, "reviews": 100, "address": "Addr",
             "type": "", "price": "", "summary": "", "maps_url": "https://maps.google.com/?cid=123", "website": ""}
        ]
        report = format_report(places, "Places")
        assert "maps.google.com" in report


class TestGetKey:
    def test_reads_from_file(self, tmp_path):
        f = tmp_path / "google-places-key.txt"
        f.write_text("AIzaTestKey123")
        with patch("clawtourism.places.KEY_FILE", f):
            assert _get_key() == "AIzaTestKey123"

    def test_env_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GOOGLE_PLACES_KEY", "AIzaEnvKey456")
        with patch("clawtourism.places.KEY_FILE", tmp_path / "nope.txt"):
            assert _get_key() == "AIzaEnvKey456"

    def test_raises_without_key(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GOOGLE_PLACES_KEY", raising=False)
        with patch("clawtourism.places.KEY_FILE", tmp_path / "nope.txt"):
            with pytest.raises(RuntimeError, match="No Google Places"):
                _get_key()
