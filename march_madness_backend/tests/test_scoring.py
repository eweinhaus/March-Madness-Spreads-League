from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from scoring import (
    compute_covering_team,
    get_lock_day_bounds,
    get_week_bounds,
    picks_locked_for_game,
    score_pick_points,
)


def test_home_favored_covers():
    winner = compute_covering_team(80, 70, 5.5, "Duke", "UNC")
    assert winner == "Duke"


def test_home_favored_does_not_cover():
    winner = compute_covering_team(74, 70, 5.5, "Duke", "UNC")
    assert winner == "UNC"


def test_away_favored_covers():
    winner = compute_covering_team(70, 80, -5.5, "Duke", "UNC")
    assert winner == "UNC"


def test_push_on_integer_spread():
    winner = compute_covering_team(75, 70, 5.0, "Duke", "UNC")
    assert winner == "PUSH"


def test_pick_em_home_wins():
    winner = compute_covering_team(72, 70, 0.0, "Duke", "UNC")
    assert winner == "Duke"


def test_score_pick_regular_and_lock():
    assert score_pick_points("Duke", "Duke", is_lock=False) == 1
    assert score_pick_points("Duke *", "Duke", is_lock=True) == 2
    assert score_pick_points("Duke", "UNC", is_lock=False) == 0
    assert score_pick_points("Duke", "PUSH", is_lock=True) == 0


def test_picks_lock_one_minute_before_tip():
    tip = datetime(2026, 3, 20, 19, 0, tzinfo=timezone.utc)
    assert picks_locked_for_game(tip - timedelta(minutes=1, seconds=1), tip) is False
    assert picks_locked_for_game(tip - timedelta(minutes=1), tip) is True


def test_lock_day_bounds_crosses_midnight_et():
    # 2 AM ET on Mar 20 belongs to the Mar 19 lock day (starts 3 AM ET Mar 19)
    dt = datetime(2026, 3, 20, 6, 0, tzinfo=timezone.utc)
    start, end = get_lock_day_bounds(dt)
    assert start < dt < end


# Football week bounds tests

def test_week_bounds_wednesday_start():
    """Wed 2026-08-26 00:00 ET (season start) belongs to week starting that instant."""
    # Wednesday 2026-08-26 00:00 ET = 04:00 UTC (EDT, UTC-4)
    wed = datetime(2026, 8, 26, 4, 0, tzinfo=timezone.utc)
    start, end = get_week_bounds(wed)
    assert start <= wed < end
    assert (end - start).days == 7
    # Verify start is exactly Wed 00:00 ET
    start_et = start.astimezone(ZoneInfo("America/New_York"))
    assert start_et.weekday() == 2  # Wednesday
    assert start_et.hour == 0
    assert start_et.minute == 0


def test_week_bounds_tuesday_end():
    """Tue 23:59:59 ET belongs to week, but Wed 00:00:00 starts new week."""
    # Tue 2026-09-01 23:59:59 ET = 2026-09-02 03:59:59 UTC (EDT)
    tue_end = datetime(2026, 9, 2, 3, 59, 59, tzinfo=timezone.utc)
    start, end = get_week_bounds(tue_end)
    assert start <= tue_end < end
    
    # Next second (Wed 00:00:00 ET) should be in new week
    wed_start = tue_end + timedelta(seconds=1)
    start2, end2 = get_week_bounds(wed_start)
    assert start2 > start
    assert start2 == end  # New week starts where old week ends


def test_week_bounds_thursday_midweek():
    """Thursday mid-day should be in same week as preceding Wednesday."""
    # Thu 2026-08-27 14:00 ET (day after season start)
    thu = datetime(2026, 8, 27, 18, 0, tzinfo=timezone.utc)  # 14:00 ET = 18:00 UTC
    start, end = get_week_bounds(thu)
    assert start <= thu < end
    # Start should be Wed 2026-08-26 00:00 ET
    start_et = start.astimezone(ZoneInfo("America/New_York"))
    assert start_et.date() == datetime(2026, 8, 26).date()
    assert start_et.hour == 0


def test_week_bounds_dst_transition():
    """DST ends 2026-11-01 2am → 1am ET. Week boundaries remain aligned to Wed 00:00 ET."""
    # DST ends first Sunday of November 2026 (Nov 1)
    # Week starting Wed 2026-11-04 00:00 ET (after DST transition)
    # This is 05:00 UTC (EST, UTC-5) not 04:00 UTC (EDT, UTC-4)
    wed_post_dst = datetime(2026, 11, 4, 5, 0, tzinfo=timezone.utc)
    start, end = get_week_bounds(wed_post_dst)
    assert start <= wed_post_dst < end
    assert (end - start).days == 7
    
    # Verify start is Wed 00:00 ET despite DST
    start_et = start.astimezone(ZoneInfo("America/New_York"))
    assert start_et.weekday() == 2  # Wednesday
    assert start_et.hour == 0
    assert start_et.minute == 0


def test_week_bounds_dst_week_spanning_transition():
    """Week that spans DST transition (Oct 28 - Nov 4, 2026) should have correct boundaries."""
    # Wed 2026-10-28 00:00 ET (before DST ends) = 04:00 UTC (EDT)
    wed_before_dst = datetime(2026, 10, 28, 4, 0, tzinfo=timezone.utc)
    start, end = get_week_bounds(wed_before_dst)
    
    # Start should be Wed 2026-10-28 00:00 ET
    start_et = start.astimezone(ZoneInfo("America/New_York"))
    assert start_et.date() == datetime(2026, 10, 28).date()
    assert start_et.hour == 0
    
    # End should be Wed 2026-11-04 00:00 ET (after DST) = 05:00 UTC (EST)
    end_et = end.astimezone(ZoneInfo("America/New_York"))
    assert end_et.date() == datetime(2026, 11, 4).date()
    assert end_et.hour == 0
    
    # Week span should still be 7 calendar days
    assert (end - start).days == 7


def test_week_bounds_half_open_semantics():
    """Verify half-open interval: Wed 00:00:00 belongs to week starting that instant."""
    # Wed 2026-08-26 00:00:00 ET exactly
    wed_exact = datetime(2026, 8, 26, 4, 0, 0, tzinfo=timezone.utc)
    start, end = get_week_bounds(wed_exact)
    # Should be in [start, end)
    assert start == wed_exact  # Belongs to week starting at this instant
    assert end > wed_exact
    
    # Microsecond before should be in previous week
    before = wed_exact - timedelta(microseconds=1)
    start_before, end_before = get_week_bounds(before)
    assert end_before == start  # Previous week ends where this week starts


def test_week_bounds_season_end():
    """Week 14 ends Wed 2026-12-09 00:00 ET."""
    # Tue 2026-12-08 23:59:59 ET (last second of week 14)
    tue_week14_end = datetime(2026, 12, 9, 4, 59, 59, tzinfo=timezone.utc)  # EST
    start, end = get_week_bounds(tue_week14_end)
    # Should be in week starting Wed 2026-12-02
    start_et = start.astimezone(ZoneInfo("America/New_York"))
    assert start_et.date() == datetime(2026, 12, 2).date()

