"""
Sport configuration module.

Provides sport mode detection and display configuration for the app.
Supports football and march_madness modes via SPORT_MODE env var.
"""

import os
from enum import Enum
from typing import Dict, Any


class SportMode(str, Enum):
    """Available sport modes."""
    FOOTBALL = "football"
    MARCH_MADNESS = "march_madness"


def get_sport_mode() -> SportMode:
    """
    Read SPORT_MODE environment variable and return the configured sport mode.
    
    Defaults to FOOTBALL if not set or if an invalid value is provided.
    
    Returns:
        SportMode: The configured sport mode
    """
    mode_str = os.getenv("SPORT_MODE", "football").lower()
    
    try:
        return SportMode(mode_str)
    except ValueError:
        # Invalid mode, default to football
        return SportMode.FOOTBALL


def get_sport_display_config() -> Dict[str, Any]:
    """
    Get display configuration for the current sport mode.
    
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
        "display_name": "Spread Pools",
        "season_label": "Current Season",
        "pick_noun": "game",
        "period_type": "week",
    }
