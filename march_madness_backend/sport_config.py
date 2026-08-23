"""
Sport configuration module.

Provides sport mode detection and display configuration for the app.
Supports football and march_madness modes via SPORT_MODE env var.
"""

import os
import logging
from enum import Enum
from typing import Dict, Any, List
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class SportMode(str, Enum):
    """Available sport modes."""
    FOOTBALL = "football"
    MARCH_MADNESS = "march_madness"


def get_sport_mode() -> SportMode:
    """
    Read SPORT_MODE environment variable and return the configured sport mode.
    
    Defaults to FOOTBALL if not set or if an invalid value is provided.
    Logs a warning when an invalid mode is provided.
    
    Returns:
        SportMode: The configured sport mode
    """
    mode_str = os.getenv("SPORT_MODE", "football").lower()
    
    try:
        return SportMode(mode_str)
    except ValueError:
        # Invalid mode, default to football with warning
        logger.warning(
            f"Invalid SPORT_MODE '{mode_str}' provided. Defaulting to 'football'. "
            f"Valid options: {', '.join([m.value for m in SportMode])}"
        )
        return SportMode.FOOTBALL


# Football season configuration
FOOTBALL_SEASON_START_DATE = "2026-08-26"  # Wednesday, CFB Week 0

# Live score scraping URLs
FOOTBALL_SCOREBOARD_URLS = {
    "nfl": "https://www.cbssports.com/nfl/scoreboard/?layout=compact",
    "cfb": "https://www.cbssports.com/college-football/scoreboard/?layout=compact",
}

MARCH_MADNESS_SCOREBOARD_URL = "https://www.cbssports.com/college-basketball/scoreboard/?layout=compact"


def get_scoreboard_urls() -> Dict[str, str]:
    """
    Get live score scraping URLs for the current sport mode.
    
    Returns:
        Dict mapping sport keys to CBS scoreboard URLs.
        Football mode: {"nfl": "...", "cfb": "..."}
        March Madness mode: {"college-basketball": "..."}
    """
    mode = get_sport_mode()
    
    if mode == SportMode.FOOTBALL:
        return FOOTBALL_SCOREBOARD_URLS
    elif mode == SportMode.MARCH_MADNESS:
        return {"college-basketball": MARCH_MADNESS_SCOREBOARD_URL}
    
    # Fallback
    return FOOTBALL_SCOREBOARD_URLS


def get_football_week_labels() -> List[Dict[str, Any]]:
    """
    Return 15 weeks of football season with labels.
    
    Week 0: CFB Week 0 (2026-08-26 - 2026-09-02)
    Week 1: CFB Week 1 (2026-09-02 - 2026-09-09) - NO NFL
    Week 2+: CFB Week i, NFL Week i-1
    Week 14: CFB Week 14, NFL Week 13 (2026-12-02 - 2026-12-09)
    
    Returns:
        List of week dictionaries with key, label, and start_date (ISO UTC)
    """
    # Parse season start as Wednesday 00:00 ET
    start = datetime.fromisoformat(FOOTBALL_SEASON_START_DATE).replace(
        hour=0, minute=0, second=0, microsecond=0,
        tzinfo=ZoneInfo("America/New_York")
    )
    
    weeks = []
    for i in range(15):
        week_start_et = start + timedelta(weeks=i)
        week_start_utc = week_start_et.astimezone(timezone.utc)
        
        if i == 0:
            label = "CFB Week 0"
        elif i == 1:
            label = "CFB Week 1"  # No NFL week 1 yet
        else:
            # Week 2+: CFB Week i, NFL Week i-1
            label = f"CFB Week {i}, NFL Week {i-1}"
        
        weeks.append({
            "key": f"week_{i}",
            "label": label,
            "start_date": week_start_utc.isoformat(),
        })
    
    return weeks


def get_league_id() -> str:
    """
    Get the current league ID from environment.
    
    Returns:
        str: League ID (e.g., "football_2026", "march_madness_2025")
    """
    return os.getenv("LEAGUE_ID", "football_2026")


def get_sport_display_config() -> Dict[str, Any]:
    """
    Get display configuration for the current sport mode.
    
    DEPRECATED: Use get_app_config() instead for complete app configuration.
    
    Returns a dictionary with display strings and metadata that the frontend
    can use for conditional rendering and appropriate terminology.
    
    Returns:
        Dict containing:
            - sport_mode: str (e.g., "football", "march_madness")
            - display_name: str (e.g., "Football Season 2026")
            - season_label: str (e.g., "2026 Season", "March Madness 2025")
            - pick_noun: str (e.g., "game", "matchup")
            - period_type: str (e.g., "week", "round")
    """
    mode = get_sport_mode()
    
    if mode == SportMode.FOOTBALL:
        return {
            "sport_mode": "football",
            "display_name": "Football Season 2026",
            "season_label": "2026 Season",
            "pick_noun": "game",
            "period_type": "week",
        }
    elif mode == SportMode.MARCH_MADNESS:
        return {
            "sport_mode": "march_madness",
            "display_name": "March Madness 2025",
            "season_label": "March Madness 2025",
            "pick_noun": "matchup",
            "period_type": "round",
        }
    
    # Fallback (should never reach here due to default in get_sport_mode)
    return {
        "sport_mode": "football",
        "display_name": "Spreads",
        "season_label": "Current Season",
        "pick_noun": "game",
        "period_type": "week",
    }


def get_app_config() -> Dict[str, Any]:
    """
    Get complete app configuration including sport mode, league ID, and display strings.
    
    This is the recommended function for the /app-config endpoint.
    
    Returns:
        Dict containing:
            - product_name: str ("Spreads")
            - league_id: str (from LEAGUE_ID env var)
            - sport_mode: str ("football" or "march_madness")
            - display_name: str (e.g., "Football Season 2026")
            - season_label: str (e.g., "2026 Season")
            - pick_noun: str (e.g., "game", "matchup")
            - period_type: str (e.g., "week", "round")
            - lock_label: str (e.g., "lock of the week", "lock of the day")
    """
    mode = get_sport_mode()
    league_id = get_league_id()
    
    base_config = {
        "product_name": "Spreads",
        "league_id": league_id,
    }
    
    if mode == SportMode.FOOTBALL:
        base_config.update({
            "sport_mode": "football",
            "display_name": "Football Season 2026",
            "season_label": "2026 Season",
            "pick_noun": "game",
            "period_type": "week",
            "lock_label": "lock of the week",
        })
    elif mode == SportMode.MARCH_MADNESS:
        base_config.update({
            "sport_mode": "march_madness",
            "display_name": "March Madness 2025",
            "season_label": "March Madness 2025",
            "pick_noun": "matchup",
            "period_type": "round",
            "lock_label": "lock of the day",
        })
    
    return base_config
