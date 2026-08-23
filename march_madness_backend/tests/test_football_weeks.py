"""Tests for football week mapping and labels."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from scoring import get_week_bounds
from sport_config import get_football_week_labels, FOOTBALL_SEASON_START_DATE


def get_week_index_and_label(dt_utc: datetime) -> tuple[int | None, str | None]:
    """
    Map a datetime to its week index and label using season table.
    
    Returns (week_index, label) or (None, None) if outside season.
    """
    week_start_utc, _ = get_week_bounds(dt_utc)
    
    # Get all weeks
    weeks = get_football_week_labels()
    
    for week in weeks:
        week_table_start = datetime.fromisoformat(week["start_date"])
        # Check if the computed week start matches this week's start
        if week_start_utc == week_table_start:
            # Extract week number from key (e.g., "week_0" -> 0)
            week_num = int(week["key"].split("_")[1])
            return week_num, week["label"]
    
    return None, None


def test_saturday_aug_29_week_0():
    """Sat 2026-08-29 → week 0, label CFB Week 0."""
    # Saturday 2026-08-29 12:00 ET (within week 0: Wed 8/26 - Wed 9/2)
    sat = datetime(2026, 8, 29, 16, 0, tzinfo=timezone.utc)  # 12:00 ET = 16:00 UTC (EDT)
    week_idx, label = get_week_index_and_label(sat)
    assert week_idx == 0
    assert label == "CFB Week 0"


def test_wednesday_sep_09_week_2():
    """Wed 2026-09-09 → week 2, label includes NFL Week 1."""
    # Wednesday 2026-09-09 00:00 ET (start of week 2)
    wed = datetime(2026, 9, 9, 4, 0, tzinfo=timezone.utc)  # 00:00 ET = 04:00 UTC (EDT)
    week_idx, label = get_week_index_and_label(wed)
    assert week_idx == 2
    assert label == "CFB Week 2, NFL Week 1"


def test_tuesday_sep_08_end_of_week_1():
    """Tue 2026-09-08 23:59 ET → still week 1, label CFB Week 1 (no NFL)."""
    # Tuesday 2026-09-08 23:59:59 ET (last second of week 1)
    tue = datetime(2026, 9, 9, 3, 59, 59, tzinfo=timezone.utc)  # 23:59:59 ET = 03:59:59 UTC (EDT)
    week_idx, label = get_week_index_and_label(tue)
    assert week_idx == 1
    assert label == "CFB Week 1"


def test_same_week_within_week_0():
    """Two games on different days within week 0 should be same week."""
    # Wed 2026-08-27 (within week 0)
    wed = datetime(2026, 8, 27, 16, 0, tzinfo=timezone.utc)
    # Sat 2026-08-30 (also within week 0)
    sat = datetime(2026, 8, 30, 20, 0, tzinfo=timezone.utc)
    
    wed_start, wed_end = get_week_bounds(wed)
    sat_start, sat_end = get_week_bounds(sat)
    
    assert wed_start == sat_start
    assert wed_end == sat_end


def test_different_weeks_across_boundary():
    """Games on Tue night and Wed morning should be different weeks."""
    # Tue 2026-09-01 23:59 ET (end of week 0)
    tue = datetime(2026, 9, 2, 3, 59, tzinfo=timezone.utc)
    # Wed 2026-09-02 00:01 ET (start of week 1)
    wed = datetime(2026, 9, 2, 4, 1, tzinfo=timezone.utc)
    
    tue_start, tue_end = get_week_bounds(tue)
    wed_start, wed_end = get_week_bounds(wed)
    
    assert tue_start != wed_start  # Different weeks
    assert tue_end == wed_start  # Tuesday's week ends when Wednesday's starts


def test_week_14_label():
    """Week 14 should have correct label: CFB Week 14, NFL Week 13."""
    # Wednesday 2026-12-02 00:00 ET (start of week 14)
    wed = datetime(2026, 12, 2, 5, 0, tzinfo=timezone.utc)  # 00:00 ET = 05:00 UTC (EST)
    week_idx, label = get_week_index_and_label(wed)
    assert week_idx == 14
    assert label == "CFB Week 14, NFL Week 13"


def test_all_week_labels_correct():
    """Verify all 15 week labels match PRD requirements."""
    weeks = get_football_week_labels()
    assert len(weeks) == 15
    
    # Week 0: CFB Week 0
    assert weeks[0]["key"] == "week_0"
    assert weeks[0]["label"] == "CFB Week 0"
    
    # Week 1: CFB Week 1 (NO NFL)
    assert weeks[1]["key"] == "week_1"
    assert weeks[1]["label"] == "CFB Week 1"
    
    # Week 2+: CFB Week i, NFL Week i-1
    for i in range(2, 15):
        assert weeks[i]["key"] == f"week_{i}"
        assert weeks[i]["label"] == f"CFB Week {i}, NFL Week {i-1}"
    
    # Week 14 specifically
    assert weeks[14]["label"] == "CFB Week 14, NFL Week 13"
