"""
Tests for flight_status_cli.py — timezone handling.

These tests exist specifically to prevent the bug where hardcoded tz_offset=+3
caused flights departing from UTC+2 airports to show times 1 hour late.

Root cause (2026-03-27): Israel was UTC+3 (IDT), Athens was UTC+2 (EET, pre-DST).
Hardcoded +3 showed ATH departure as 15:10 instead of correct 14:10.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from clawtourism.flight_status_cli import fmt_time, get_airport_tz


class TestFmtTime:
    # W43048 ATH→BBU dep: 2026-03-27 12:10 UTC
    # pre-European-DST (DST starts Mar 29 2026)
    TS_ATH_DEP_PRE_DST = 1774613400  # 2026-03-27 12:10:00 UTC

    # Same flight time slot after European DST switch
    TS_ATH_DEP_POST_DST = 1775304600  # 2026-04-04 12:10:00 UTC

    def test_athens_pre_dst(self):
        """ATH is EET (UTC+2) before DST — must show 14:10, not 15:10."""
        assert fmt_time(self.TS_ATH_DEP_PRE_DST, "Europe/Athens") == "14:10"

    def test_athens_post_dst(self):
        """ATH is EEST (UTC+3) after DST — must show 15:10."""
        assert fmt_time(self.TS_ATH_DEP_POST_DST, "Europe/Athens") == "15:10"

    def test_israel_pre_dst(self):
        """Israel switches to IDT (UTC+3) earlier than Europe — Mar 27 Israel already UTC+3."""
        assert fmt_time(self.TS_ATH_DEP_PRE_DST, "Asia/Jerusalem") == "15:10"

    def test_bucharest_pre_dst(self):
        """Bucharest same as Athens (EET UTC+2 pre-DST)."""
        assert fmt_time(self.TS_ATH_DEP_PRE_DST, "Europe/Bucharest") == "14:10"

    def test_none_returns_none(self):
        assert fmt_time(None) is None

    def test_new_york_dst(self):
        """NYC is EDT (UTC-4) in late March."""
        assert fmt_time(self.TS_ATH_DEP_PRE_DST, "America/New_York") == "08:10"


class TestGetAirportTz:
    def test_ath(self):
        assert get_airport_tz("ATH") == "Europe/Athens"

    def test_bbu(self):
        assert get_airport_tz("BBU") == "Europe/Bucharest"

    def test_tlv(self):
        assert get_airport_tz("TLV") == "Asia/Jerusalem"

    def test_lowercase(self):
        assert get_airport_tz("ath") == "Europe/Athens"

    def test_unknown_returns_fallback(self):
        assert get_airport_tz("XYZ") == "Asia/Jerusalem"

    def test_none_returns_fallback(self):
        assert get_airport_tz(None) == "Asia/Jerusalem"
