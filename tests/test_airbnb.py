"""
Tests for airbnb.py (Apify-based Airbnb scraper).

All tests mock the HTTP layer — no real API calls.
"""
import pytest
from unittest.mock import patch, MagicMock

from clawtourism.airbnb import (
    _parse_price_usd,
    _parse_rating,
    search_and_report,
    _get_key,
)


MOCK_RUN_RESPONSE = {
    "data": {
        "id": "test_run_id_123",
        "defaultDatasetId": "test_dataset_id_456",
        "status": "READY",
    }
}

MOCK_STATUS_SUCCEEDED = {"data": {"status": "SUCCEEDED"}}

MOCK_AIRBNB_ITEMS = [
    {
        "title": "Viennese duplex with terrace",
        "price": {"label": "$1,079 total, originally $1,549", "qualifier": "total"},
        "rating": {
            "guestSatisfaction": 4.88,
            "reviewsCount": 287,
            "cleanliness": 4.84,
        },
        "bedroom": 2,
        "url": "https://www.airbnb.com/rooms/23462756",
    },
    {
        "title": "2BR-5min to Rathaus & Parliament",
        "price": {"label": "$1,355 total, originally $1,802", "qualifier": "total"},
        "rating": {
            "guestSatisfaction": 4.93,
            "reviewsCount": 58,
            "cleanliness": 4.97,
        },
        "bedroom": 2,
        "url": "https://www.airbnb.com/rooms/1381151382891849490",
    },
    {
        "title": "Cheap low-rated place",
        "price": {"label": "$600 total", "qualifier": "total"},
        "rating": {"guestSatisfaction": 3.9, "reviewsCount": 5},
        "bedroom": 1,
        "url": "https://www.airbnb.com/rooms/99999",
    },
]


class TestParsePriceUsd:
    def test_parses_total(self):
        p = {"label": "$1,355 total, originally $1,802"}
        assert _parse_price_usd(p) == 1355

    def test_parses_no_original(self):
        p = {"label": "$600 total"}
        assert _parse_price_usd(p) == 600

    def test_none_input(self):
        assert _parse_price_usd(None) is None

    def test_empty_dict(self):
        assert _parse_price_usd({}) is None

    def test_no_total_label(self):
        p = {"label": "From $50/night"}
        assert _parse_price_usd(p) is None


class TestParseRating:
    def test_dict_input(self):
        r = {"guestSatisfaction": 4.88, "reviewsCount": 287}
        rating, count = _parse_rating(r)
        assert rating == 4.88
        assert count == 287

    def test_zero_reviews(self):
        r = {"guestSatisfaction": 5.0, "reviewsCount": 0}
        rating, count = _parse_rating(r)
        assert rating == 5.0
        assert count == 0

    def test_non_dict(self):
        rating, count = _parse_rating("4.5")
        assert rating == 0.0
        assert count == 0

    def test_none(self):
        rating, count = _parse_rating(None)
        assert rating == 0.0
        assert count == 0


class TestSearchAndReport:
    def _mock_api(self, path, params=None, body=None, method=None):
        if "runs" in path and method == "POST":
            return MOCK_RUN_RESPONSE
        if "runs" in path:
            return MOCK_STATUS_SUCCEEDED
        if "datasets" in path:
            return MOCK_AIRBNB_ITEMS  # list, not wrapped
        return {}

    def test_report_contains_listings(self):
        with patch("clawtourism.airbnb._api") as mock_api, \
             patch("clawtourism.airbnb.time.sleep"):
            mock_api.side_effect = lambda method, path, body=None: (
                MOCK_RUN_RESPONSE if "runs" in path and method == "POST"
                else MOCK_STATUS_SUCCEEDED if "runs" in path
                else MOCK_AIRBNB_ITEMS
            )
            report = search_and_report(
                location="Neubau, Vienna, Austria",
                checkin="2026-04-03",
                checkout="2026-04-10",
            )
        assert "Airbnb" in report
        assert "Viennese duplex" in report or "2BR-5min" in report
        assert "⭐" in report
        assert "€" in report

    def test_min_rating_filter(self):
        with patch("clawtourism.airbnb._api") as mock_api, \
             patch("clawtourism.airbnb.time.sleep"):
            mock_api.side_effect = lambda method, path, body=None: (
                MOCK_RUN_RESPONSE if "runs" in path and method == "POST"
                else MOCK_STATUS_SUCCEEDED if "runs" in path
                else MOCK_AIRBNB_ITEMS
            )
            report = search_and_report(
                location="Neubau, Vienna, Austria",
                checkin="2026-04-03",
                checkout="2026-04-10",
                min_rating=4.8,
            )
        # Low rated (3.9) should be filtered
        assert "Cheap low-rated" not in report

    def test_sorted_by_rating_then_price(self):
        with patch("clawtourism.airbnb._api") as mock_api, \
             patch("clawtourism.airbnb.time.sleep"):
            mock_api.side_effect = lambda method, path, body=None: (
                MOCK_RUN_RESPONSE if "runs" in path and method == "POST"
                else MOCK_STATUS_SUCCEEDED if "runs" in path
                else MOCK_AIRBNB_ITEMS
            )
            report = search_and_report(
                location="Neubau, Vienna, Austria",
                checkin="2026-04-03",
                checkout="2026-04-10",
                min_rating=4.5,
            )
        # 4.93-rated should appear before 4.88-rated
        idx_high = report.find("2BR-5min")
        idx_low = report.find("Viennese duplex")
        assert idx_high < idx_low

    def test_usd_to_eur_conversion(self):
        """$1,079 total × 0.92 = €993 total, / 7 nights = €142/night"""
        with patch("clawtourism.airbnb._api") as mock_api, \
             patch("clawtourism.airbnb.time.sleep"):
            mock_api.side_effect = lambda method, path, body=None: (
                MOCK_RUN_RESPONSE if "runs" in path and method == "POST"
                else MOCK_STATUS_SUCCEEDED if "runs" in path
                else [MOCK_AIRBNB_ITEMS[0]]  # only duplex
            )
            report = search_and_report(
                location="Neubau, Vienna",
                checkin="2026-04-03",
                checkout="2026-04-10",
                min_rating=4.0,
            )
        assert "€993" in report or "€992" in report  # slight rounding variation ok
        assert "€141" in report or "€142" in report


class TestGetKey:
    def test_reads_from_file(self, tmp_path):
        key_file = tmp_path / "apify-key.txt"
        key_file.write_text("apify_test_token_abc")
        with patch("clawtourism.airbnb.KEY_FILE", key_file):
            assert _get_key() == "apify_test_token_abc"

    def test_env_fallback(self, tmp_path, monkeypatch):
        missing = tmp_path / "nope.txt"
        monkeypatch.setenv("APIFY_TOKEN", "apify_env_xyz")
        with patch("clawtourism.airbnb.KEY_FILE", missing):
            assert _get_key() == "apify_env_xyz"

    def test_raises_without_key(self, tmp_path, monkeypatch):
        missing = tmp_path / "nope.txt"
        monkeypatch.delenv("APIFY_TOKEN", raising=False)
        with patch("clawtourism.airbnb.KEY_FILE", missing):
            with pytest.raises(RuntimeError, match="No Apify token"):
                _get_key()
