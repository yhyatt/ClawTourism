"""Tests for experiences.py — experience booking link generation."""
from __future__ import annotations

import urllib.parse
import pytest

from clawtourism.experiences import (
    get_experience_links,
    format_experience_links,
    _normalize_category,
)


class TestGetExperienceLinks:
    def test_returns_all_platforms(self):
        links = get_experience_links("Vienna")
        assert "getyourguide" in links
        assert "viator" in links
        assert "klook" in links
        assert "airbnb" in links
        # musement only for known cities
        assert "musement" in links  # Vienna is in MUSEMENT_CITIES

    def test_city_encoded_in_urls(self):
        links = get_experience_links("Vienna")
        for platform, url in links.items():
            assert "vienna" in url.lower() or "Wien" in url, f"{platform} URL missing city: {url}"

    def test_spaces_in_city_encoded(self):
        links = get_experience_links("Tel Aviv")
        for platform, url in links.items():
            # No raw spaces allowed in URLs
            assert " " not in url, f"{platform} URL has raw space: {url}"
        # Should be encoded as + or %20
        gyg = links["getyourguide"]
        assert "Tel+Aviv" in gyg or "Tel%20Aviv" in gyg or "tel+aviv" in gyg.lower()

    def test_kids_filter_applied(self):
        links_plain = get_experience_links("Vienna")
        links_kids = get_experience_links("Vienna", kids=True)
        # Kids URLs should differ from plain
        assert links_kids["getyourguide"] != links_plain["getyourguide"]
        assert links_kids["viator"] != links_plain["viator"]
        assert links_kids["airbnb"] != links_plain["airbnb"]
        # Kids params present
        assert "families" in links_kids["getyourguide"] or "suitable" in links_kids["getyourguide"]

    def test_category_food_applied(self):
        links_plain = get_experience_links("Vienna")
        links_food = get_experience_links("Vienna", category="food")
        assert links_food["getyourguide"] != links_plain["getyourguide"]
        assert "food" in links_food["getyourguide"].lower() or "drink" in links_food["getyourguide"].lower()

    def test_category_alias_cooking(self):
        links_cooking = get_experience_links("Barcelona", category="cooking")
        links_food = get_experience_links("Barcelona", category="food")
        assert links_cooking["getyourguide"] == links_food["getyourguide"]

    def test_family_category_sets_kids(self):
        links_family = get_experience_links("Vienna", category="family")
        links_kids = get_experience_links("Vienna", kids=True)
        assert links_family["getyourguide"] == links_kids["getyourguide"]

    def test_musement_only_for_known_cities(self):
        links_vienna = get_experience_links("Vienna")
        links_random = get_experience_links("RandomUnknownCity123")
        assert "musement" in links_vienna
        assert "musement" not in links_random

    def test_musement_url_contains_city_slug(self):
        links = get_experience_links("Barcelona")
        assert "barcelona" in links["musement"]

    def test_unknown_category_ignored(self):
        # Unknown category should not crash, just return plain links
        links = get_experience_links("Vienna", category="zorblax99")
        assert "getyourguide" in links
        assert "viator" in links

    def test_nightlife_not_affected_by_kids(self):
        # Kids + nightlife — nightlife filter should still work (kids param added too)
        links = get_experience_links("Vienna", category="nightlife", kids=True)
        assert "nightlife" in links["getyourguide"].lower()

    def test_new_york_alias(self):
        links = get_experience_links("New York")
        assert "musement" in links
        assert "new-york" in links["musement"]


class TestNormalizeCategory:
    def test_cooking_maps_to_food(self):
        assert _normalize_category("cooking") == "food"

    def test_hiking_maps_to_outdoor(self):
        assert _normalize_category("hiking") == "outdoor"

    def test_art_maps_to_museum(self):
        assert _normalize_category("art") == "museum"

    def test_bar_maps_to_nightlife(self):
        assert _normalize_category("bar") == "nightlife"

    def test_known_category_returns_itself(self):
        assert _normalize_category("food") == "food"
        assert _normalize_category("outdoor") == "outdoor"

    def test_unknown_returns_none(self):
        assert _normalize_category("zorblax") is None

    def test_case_insensitive(self):
        assert _normalize_category("FOOD") == "food"
        assert _normalize_category("Cooking") == "food"


class TestFormatExperienceLinks:
    def test_contains_city_name(self):
        links = get_experience_links("Vienna")
        output = format_experience_links("Vienna", links)
        assert "Vienna" in output

    def test_contains_all_platform_names(self):
        links = get_experience_links("Vienna")
        output = format_experience_links("Vienna", links)
        assert "GetYourGuide" in output
        assert "Viator" in output
        assert "Klook" in output
        assert "Airbnb" in output
        assert "Musement" in output

    def test_kids_filter_shown_in_output(self):
        links = get_experience_links("Vienna", kids=True)
        output = format_experience_links("Vienna", links, kids=True)
        assert "Kids" in output or "kids" in output or "👨" in output

    def test_category_shown_in_output(self):
        links = get_experience_links("Vienna", category="food")
        output = format_experience_links("Vienna", links, category="food")
        assert "food" in output.lower()

    def test_eu_city_tip_in_output(self):
        links = get_experience_links("Barcelona")
        output = format_experience_links("Barcelona", links)
        assert "GYG" in output or "Musement" in output or "widest" in output

    def test_asia_city_tip_in_output(self):
        links = get_experience_links("Tokyo")
        output = format_experience_links("Tokyo", links)
        assert "Klook" in output

    def test_us_city_tip_in_output(self):
        links = get_experience_links("New York")
        output = format_experience_links("New York", links)
        assert "Viator" in output

    def test_empty_links_graceful(self):
        output = format_experience_links("SomeCity", {})
        assert "SomeCity" in output
