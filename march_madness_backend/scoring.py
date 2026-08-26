"""Pure scoring and pick-lock helpers (no Firebase dependencies)."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Callable, List, Sequence, Tuple

PICK_LOCK_BEFORE_TIP = timedelta(minutes=1)


def normalize_datetime(dt):
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=timezone.utc)


def get_lock_day_bounds(dt_utc):
    """Lock-of-the-day window: 3:00 AM ET through next day 3:00 AM ET."""
    dt_utc = normalize_datetime(dt_utc)
    z = ZoneInfo("America/New_York")
    local = dt_utc.astimezone(z)
    if local.hour < 3:
        day = local.date() - timedelta(days=1)
    else:
        day = local.date()
    start_ny = datetime(day.year, day.month, day.day, 3, 0, 0, tzinfo=z)
    end_ny = start_ny + timedelta(days=1)
    return start_ny.astimezone(timezone.utc), end_ny.astimezone(timezone.utc)


def get_week_bounds(dt_utc):
    """
    Football week window: Wednesday 00:00 ET through next Wednesday 00:00 ET (half-open).
    
    Uses America/New_York ZoneInfo to handle DST transitions correctly.
    Returns UTC datetimes for [start, end) interval.
    """
    dt_utc = normalize_datetime(dt_utc)
    z = ZoneInfo("America/New_York")
    local = dt_utc.astimezone(z)
    
    # Find the most recent Wednesday 00:00 ET on or before local time
    # weekday(): Monday=0, Tuesday=1, Wednesday=2, Thursday=3, ...
    days_since_wed = (local.weekday() - 2) % 7
    week_start_date = local.date() - timedelta(days=days_since_wed)
    
    # Create Wednesday 00:00:00 ET
    start_ny = datetime(
        week_start_date.year, 
        week_start_date.month, 
        week_start_date.day, 
        0, 0, 0, 
        tzinfo=z
    )
    
    # Next Wednesday 00:00:00 ET (7 days later)
    end_ny = start_ny + timedelta(weeks=1)
    
    return start_ny.astimezone(timezone.utc), end_ny.astimezone(timezone.utc)


def current_pick_period_bounds(
    now: datetime,
    upcoming_game_dates: Sequence,
    bounds_fn: Callable,
) -> List[Tuple[datetime, datetime]]:
    """
    Periods that count as the current pick window for lock-of-week/day status.

    If any upcoming games exist (game_date > now), use the unique week / lock-day
    bounds of those games (so a Tuesday lock on next week's slate counts).
    Otherwise fall back to bounds_fn(now).
    """
    now = normalize_datetime(now)
    periods: List[Tuple[datetime, datetime]] = []
    seen = set()
    for gd in upcoming_game_dates:
        gd = normalize_datetime(gd)
        if gd is None or now is None or gd <= now:
            continue
        start, end = bounds_fn(gd)
        key = (start, end)
        if key not in seen:
            seen.add(key)
            periods.append((start, end))
    if periods:
        return periods
    return [bounds_fn(now)]


def datetime_in_periods(dt, periods: Sequence[Tuple[datetime, datetime]]) -> bool:
    """True if dt falls in any half-open [start, end) period."""
    dt = normalize_datetime(dt)
    if dt is None:
        return False
    for start, end in periods:
        if start <= dt < end:
            return True
    return False


def picks_locked_for_game(current_time, scheduled_utc) -> bool:
    """True when picks may no longer be submitted or changed."""
    scheduled_utc = normalize_datetime(scheduled_utc)
    if scheduled_utc is None:
        return False
    return current_time >= scheduled_utc - PICK_LOCK_BEFORE_TIP


def compute_covering_team(
    home_pts: int, away_pts: int, spread: float, home_team: str, away_team: str
) -> str:
    """
    spread > 0  -> home favored by spread (home -spread).
    spread < 0  -> away favored by |spread|.
    spread == 0 -> pick'em (straight winner / push on tie).
    """
    s = float(spread)
    if s == 0:
        if home_pts > away_pts:
            return home_team
        if away_pts > home_pts:
            return away_team
        return "PUSH"
    if s > 0:
        margin = home_pts - away_pts
        if margin > s:
            return home_team
        if margin < s:
            return away_team
        return "PUSH" if s == int(s) else away_team
    fav = -s
    away_margin = away_pts - home_pts
    if away_margin > fav:
        return away_team
    if away_margin < fav:
        return home_team
    return "PUSH" if fav == int(fav) else home_team


def score_pick_points(picked_team: str, winning_team: str, is_lock: bool) -> int:
    """Points for a single pick given the covering team (or PUSH)."""
    if winning_team == "PUSH":
        return 0
    norm_picked = picked_team.rstrip(" *")
    norm_winner = winning_team.rstrip(" *")
    if norm_picked == norm_winner:
        return 2 if is_lock else 1
    return 0
