from datetime import datetime, timedelta, timezone

from scoring import (
    compute_covering_team,
    get_lock_day_bounds,
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
