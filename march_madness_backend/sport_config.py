"""
Sport configuration module.

Provides sport mode detection and display configuration for the app.
Supports football and march_madness modes via SPORT_MODE env var.
"""

import os
import logging
from enum import Enum
from typing import Dict, Any

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


def get_league_id() -> str:
    """
    Get the current league ID from environment.
    
    Returns:
        str: League ID (e.g., "football_2026", "march_madness_2025")
    """
    return os.getenv("LEAGUE_ID", "march_madness_2025")


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
