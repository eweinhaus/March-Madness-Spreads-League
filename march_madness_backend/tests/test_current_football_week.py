"""
Tests for current football week calculation.

Verifies that week boundaries work correctly across DST transitions
and that clamping to week_0/week_14 works as expected.
"""

import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sport_config import get_football_week_labels, FOOTBALL_SEASON_START_DATE


def get_current_football_week_backend(dt_utc):
    """
    Backend version of getCurrentFootballWeek for testing.
    
    Given a UTC datetime, returns the week key (week_0..week_14).
    Before season start → clamp to week_0. After season end → clamp to week_14.
    """
    week_labels = get_football_week_labels()
    
    # Before season starts → clamp to week_0
    season_start = datetime.fromisoformat(week_labels[0]["start_date"])
    if dt_utc < season_start:
        return "week_0"
    
    # Find which week contains dt_utc
    for i, week_info in enumerate(week_labels):
        start_dt = datetime.fromisoformat(week_info["start_date"])
        # End is 7 days later (civil week, not 168 hours)
        end_dt = start_dt.replace(tzinfo=None)
        end_dt = datetime(
            end_dt.year, end_dt.month, end_dt.day,
            tzinfo=ZoneInfo("America/New_York")
        )
        # Add 7 days in ET timezone (handles DST)
        from datetime import timedelta
        end_dt = end_dt + timedelta(weeks=1)
        end_dt = end_dt.astimezone(timezone.utc)
        
        if start_dt <= dt_utc < end_dt:
            return f"week_{i}"
    
    # After season ends → clamp to week_14
    return "week_14"


def test_aug_22_2026_is_week_0():
    """2026-08-22 (Fri before season start Wed 08-26) → week_0 (clamped)."""
    dt = datetime(2026, 8, 22, 12, 0, 0, tzinfo=timezone.utc)
    assert get_current_football_week_backend(dt) == "week_0"


def test_aug_29_2026_is_week_0():
    """2026-08-29 (Sat in week 0) → week_0."""
    dt = datetime(2026, 8, 29, 20, 0, 0, tzinfo=timezone.utc)
    assert get_current_football_week_backend(dt) == "week_0"


def test_nov_04_2026_00_00_et_correct_week():
    """
    2026-11-04 00:00 ET (Wed after DST ends 2026-11-01) → correct week.
    
    DST ends 2026-11-01 02:00 → 01:00. Week starting 2026-11-04 should be week_10.
    This tests that we use ET civil date math, not raw milliseconds.
    """
    # Nov 4 2026 00:00 ET → UTC
    # Nov 4 is after DST ends (EST = UTC-5)
    dt_et = datetime(2026, 11, 4, 0, 0, 0, tzinfo=ZoneInfo("America/New_York"))
    dt_utc = dt_et.astimezone(timezone.utc)
    
    # Week 0: Aug 26
    # Week 10: Aug 26 + 10 weeks = Oct 28 ... Nov 4
    # Count: 0=Aug26, 1=Sep2, 2=Sep9, 3=Sep16, 4=Sep23, 5=Sep30, 6=Oct7,
    #        7=Oct14, 8=Oct21, 9=Oct28, 10=Nov4
    assert get_current_football_week_backend(dt_utc) == "week_10"


def test_dec_10_2026_is_week_14():
    """2026-12-10 (Thu after season end Wed 12-09) → week_14 (clamped)."""
    dt = datetime(2026, 12, 10, 12, 0, 0, tzinfo=timezone.utc)
    assert get_current_football_week_backend(dt) == "week_14"


def test_week_0_start_exact():
    """2026-08-26 00:00 ET (season start) → week_0."""
    dt_et = datetime(2026, 8, 26, 0, 0, 0, tzinfo=ZoneInfo("America/New_York"))
    dt_utc = dt_et.astimezone(timezone.utc)
    assert get_current_football_week_backend(dt_utc) == "week_0"


def test_week_1_start_exact():
    """2026-09-02 00:00 ET (week 1 start) → week_1."""
    dt_et = datetime(2026, 9, 2, 0, 0, 0, tzinfo=ZoneInfo("America/New_York"))
    dt_utc = dt_et.astimezone(timezone.utc)
    assert get_current_football_week_backend(dt_utc) == "week_1"


def test_week_14_last_second():
    """2026-12-08 23:59:59 ET (last second of week 14) → week_14."""
    dt_et = datetime(2026, 12, 8, 23, 59, 59, tzinfo=ZoneInfo("America/New_York"))
    dt_utc = dt_et.astimezone(timezone.utc)
    assert get_current_football_week_backend(dt_utc) == "week_14"
