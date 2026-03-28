"""Tests for destination.py — RestCountries + Wikivoyage destination intelligence."""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from clawtourism.destination import (
    get_country_info,
    get_travel_guide,
    get_destination_brief,
    format_country_info,
    format_guide,
    _strip_wiki_markup,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mock_url_response(data):
    mock = MagicMock()
    mock.read.return_value = json.dumps(data).encode()
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


# ── Fixture data ──────────────────────────────────────────────────────────────

AUSTRIA_RESPONSE = [
    {
        "name": {"common": "Austria", "official": "Republic of Austria"},
        "capital": ["Vienna"],
        "region": "Europe",
        "subregion": "Central Europe",
        "population": 9000000,
        "currencies": {"EUR": {"name": "Euro", "symbol": "€"}},
        "languages": {"deu": "German"},
        "timezones": ["UTC+01:00"],
        "idd": {"root": "+4", "suffixes": ["3"]},
        "flag": "🇦🇹",
    }
]

MOROCCO_RESPONSE = [
    {
        "name": {"common": "Morocco", "official": "Kingdom of Morocco"},
        "capital": ["Rabat"],
        "region": "Africa",
        "subregion": "Northern Africa",
        "population": 37000000,
        "currencies": {"MAD": {"name": "Moroccan dirham", "symbol": "MAD"}},
        "languages": {"ara": "Arabic", "ber": "Berber"},
        "timezones": ["UTC+01:00"],
        "idd": {"root": "+2", "suffixes": ["12"]},
        "flag": "🇲🇦",
    }
]

WIKIVOYAGE_SECTIONS_RESPONSE = {
    "parse": {
        "sections": [
            {"line": "See", "index": "1"},
            {"line": "Do", "index": "2"},
            {"line": "Eat", "index": "3"},
            {"line": "Drink", "index": "4"},
            {"line": "Sleep", "index": "5"},
        ]
    }
}

WIKIVOYAGE_SECTION_CONTENT = {
    "parse": {
        "wikitext": {
            "*": "==See==\n[[St. Stephen's Cathedral]] is the most visited sight. {{main|Vienna museums}}\n"
                 "The [[Kunsthistorisches Museum]] has one of Europe's finest art collections."
        }
    }
}

WIKIVOYAGE_NOT_FOUND = {
    "error": {"code": "missingtitle", "info": "The page you requested doesn't exist."}
}


# ── _strip_wiki_markup ────────────────────────────────────────────────────────

class TestStripWikiMarkup:
    def test_removes_templates(self):
        text = "Hello {{main|Vienna museums}} world"
        result = _strip_wiki_markup(text)
        assert "{{" not in result
        assert "Hello" in result

    def test_extracts_link_display_text(self):
        text = "Visit [[St. Stephen's Cathedral|the cathedral]] today"
        result = _strip_wiki_markup(text)
        assert "the cathedral" in result
        assert "[[" not in result

    def test_removes_headers(self):
        text = "==See==\nSome content here"
        result = _strip_wiki_markup(text)
        assert "==" not in result
        assert "Some content here" in result

    def test_removes_bold_italic(self):
        text = "'''Vienna''' is ''beautiful''"
        result = _strip_wiki_markup(text)
        assert "'''" not in result
        assert "''" not in result
        assert "Vienna" in result
        assert "beautiful" in result

    def test_removes_html_tags(self):
        text = "This is <b>bold</b> and <i>italic</i>"
        result = _strip_wiki_markup(text)
        assert "<b>" not in result
        assert "bold" in result


# ── get_country_info ──────────────────────────────────────────────────────────

class TestGetCountryInfo:
    def test_austria_basic_facts(self):
        with patch("urllib.request.urlopen", return_value=_mock_url_response(AUSTRIA_RESPONSE)):
            result = get_country_info("Austria")
        assert result["name"] == "Austria"
        assert result["capital"] == "Vienna"
        assert "EUR" in result["currencies"]
        assert result["currencies"]["EUR"]["name"] == "Euro"
        assert "German" in result["languages"]

    def test_austria_timezones(self):
        with patch("urllib.request.urlopen", return_value=_mock_url_response(AUSTRIA_RESPONSE)):
            result = get_country_info("Austria")
        assert "UTC+01:00" in result["timezones"]

    def test_austria_calling_code(self):
        with patch("urllib.request.urlopen", return_value=_mock_url_response(AUSTRIA_RESPONSE)):
            result = get_country_info("Austria")
        assert result["calling_code"] == "+43"

    def test_morocco_multiple_languages(self):
        with patch("urllib.request.urlopen", return_value=_mock_url_response(MOROCCO_RESPONSE)):
            result = get_country_info("Morocco")
        assert "Arabic" in result["languages"]
        assert "Berber" in result["languages"]

    def test_not_found_returns_error(self):
        with patch("urllib.request.urlopen", return_value=_mock_url_response([])):
            result = get_country_info("Neverland")
        assert "error" in result

    def test_api_unreachable_returns_error(self):
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            result = get_country_info("Austria")
        assert "error" in result

    def test_includes_flag(self):
        with patch("urllib.request.urlopen", return_value=_mock_url_response(AUSTRIA_RESPONSE)):
            result = get_country_info("Austria")
        assert result["flag"] == "🇦🇹"


# ── get_travel_guide ──────────────────────────────────────────────────────────

class TestGetTravelGuide:
    def _make_side_effect(self, sections_resp, section_content):
        """Return different responses for section list vs section content calls."""
        call_count = [0]
        def side_effect(url, timeout=8):
            call_count[0] += 1
            if call_count[0] == 1:
                return _mock_url_response(sections_resp)
            return _mock_url_response(section_content)
        return side_effect

    def test_returns_sections_dict(self):
        with patch("urllib.request.urlopen",
                   side_effect=self._make_side_effect(WIKIVOYAGE_SECTIONS_RESPONSE, WIKIVOYAGE_SECTION_CONTENT)):
            result = get_travel_guide("Vienna")
        assert "destination" in result
        assert "sections" in result
        assert result["destination"] == "Vienna"

    def test_sections_contain_see(self):
        with patch("urllib.request.urlopen",
                   side_effect=self._make_side_effect(WIKIVOYAGE_SECTIONS_RESPONSE, WIKIVOYAGE_SECTION_CONTENT)):
            result = get_travel_guide("Vienna")
        # At least one section should be populated
        assert len(result.get("sections", {})) > 0

    def test_not_found_returns_error(self):
        with patch("urllib.request.urlopen", return_value=_mock_url_response(WIKIVOYAGE_NOT_FOUND)):
            result = get_travel_guide("Nonexistentcityxyz123")
        assert "error" in result

    def test_brief_mode_truncates(self):
        long_content = {
            "parse": {
                "wikitext": {
                    "*": "==See==\n" + "A" * 500
                }
            }
        }
        with patch("urllib.request.urlopen",
                   side_effect=self._make_side_effect(WIKIVOYAGE_SECTIONS_RESPONSE, long_content)):
            result = get_travel_guide("Vienna", brief=True)
        if "sections" in result:
            for section_text in result["sections"].values():
                assert len(section_text) <= 305  # 300 chars + "…"

    def test_api_error_returns_error(self):
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            result = get_travel_guide("Vienna")
        assert "error" in result


# ── get_destination_brief ─────────────────────────────────────────────────────

class TestGetDestinationBrief:
    def test_combines_country_and_guide(self):
        with patch("clawtourism.destination.get_country_info",
                   return_value={"name": "Austria", "capital": "Vienna", "currencies": {"EUR": {"name": "Euro", "symbol": "€"}}, "languages": ["German"], "timezones": ["UTC+01:00"], "calling_code": "+43", "flag": "🇦🇹", "region": "Europe", "subregion": "Central Europe", "population": 9000000, "official_name": "Republic of Austria"}), \
             patch("clawtourism.destination.get_travel_guide",
                   return_value={"destination": "Vienna", "sections": {"See": "Many museums.", "Eat": "Wiener Schnitzel."}}):
            result = get_destination_brief("Vienna", country="Austria")
        assert "country" in result
        assert "guide" in result
        assert result["country"]["capital"] == "Vienna"
        assert "See" in result["guide"]

    def test_partial_data_when_country_not_found(self):
        with patch("clawtourism.destination.get_country_info", return_value={"error": "not found"}), \
             patch("clawtourism.destination.get_travel_guide",
                   return_value={"destination": "Barcelona", "sections": {"See": "Sagrada Familia."}}):
            result = get_destination_brief("Barcelona", country="Barcelona")
        # Should still have guide even if country facts failed
        assert "guide" in result
        assert "country" not in result


# ── format_country_info ───────────────────────────────────────────────────────

class TestFormatCountryInfo:
    def test_formats_austria(self):
        info = {
            "name": "Austria", "official_name": "Republic of Austria",
            "capital": "Vienna", "region": "Europe", "subregion": "Central Europe",
            "population": 9000000, "flag": "🇦🇹",
            "currencies": {"EUR": {"name": "Euro", "symbol": "€"}},
            "languages": ["German"],
            "timezones": ["UTC+01:00"],
            "calling_code": "+43",
        }
        output = format_country_info(info)
        assert "Austria" in output
        assert "Vienna" in output
        assert "EUR" in output
        assert "German" in output
        assert "+43" in output

    def test_error_returns_fallback(self):
        output = format_country_info({"error": "not found"})
        assert "unavailable" in output.lower()


# ── format_guide ─────────────────────────────────────────────────────────────

class TestFormatGuide:
    def test_formats_sections(self):
        data = {
            "destination": "Vienna",
            "sections": {
                "See": "Great museums.",
                "Eat": "Excellent pastries.",
            }
        }
        output = format_guide(data)
        assert "Vienna" in output
        assert "See" in output
        assert "Eat" in output
        assert "Great museums" in output

    def test_error_returns_fallback(self):
        output = format_guide({"error": "not found"})
        assert "unavailable" in output.lower()

    def test_truncates_long_sections(self):
        data = {
            "destination": "Vienna",
            "sections": {"See": "X" * 1000}
        }
        output = format_guide(data, max_section_chars=100)
        # Should be truncated
        assert "…" in output
