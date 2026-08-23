"""
Unit tests for sport_config module.

Tests sport mode detection, app config, and league ID retrieval.
"""

import os
import pytest
from unittest import mock
from sport_config import (
    get_sport_mode,
    get_league_id,
    get_app_config,
    get_sport_display_config,
    get_scoreboard_urls,
    SportMode,
)


def test_get_sport_mode_default():
    """Test that default sport mode is football when not set."""
    with mock.patch.dict(os.environ, {}, clear=True):
        mode = get_sport_mode()
        assert mode == SportMode.FOOTBALL


def test_get_sport_mode_football():
    """Test football mode explicitly set."""
    with mock.patch.dict(os.environ, {"SPORT_MODE": "football"}):
        mode = get_sport_mode()
        assert mode == SportMode.FOOTBALL


def test_get_sport_mode_march_madness():
    """Test march_madness mode."""
    with mock.patch.dict(os.environ, {"SPORT_MODE": "march_madness"}):
        mode = get_sport_mode()
        assert mode == SportMode.MARCH_MADNESS


def test_get_sport_mode_invalid_defaults_to_football():
    """Test that invalid sport mode defaults to football with warning."""
    with mock.patch.dict(os.environ, {"SPORT_MODE": "invalid_sport"}):
        mode = get_sport_mode()
        assert mode == SportMode.FOOTBALL


def test_get_sport_mode_case_insensitive():
    """Test that sport mode is case insensitive."""
    with mock.patch.dict(os.environ, {"SPORT_MODE": "FOOTBALL"}):
        mode = get_sport_mode()
        assert mode == SportMode.FOOTBALL
    
    with mock.patch.dict(os.environ, {"SPORT_MODE": "March_Madness"}):
        mode = get_sport_mode()
        assert mode == SportMode.MARCH_MADNESS


def test_get_league_id_default():
    """Test default league ID when not set."""
    with mock.patch.dict(os.environ, {}, clear=True):
        league_id = get_league_id()
        assert league_id == "football_2026"


def test_get_league_id_custom():
    """Test custom league ID from environment."""
    with mock.patch.dict(os.environ, {"LEAGUE_ID": "football_2026"}):
        league_id = get_league_id()
        assert league_id == "football_2026"


def test_get_app_config_football():
    """Test complete app config for football mode."""
    with mock.patch.dict(os.environ, {"SPORT_MODE": "football", "LEAGUE_ID": "football_2026"}):
        config = get_app_config()
        
        assert config["product_name"] == "Spreads"
        assert config["league_id"] == "football_2026"
        assert config["sport_mode"] == "football"
        assert config["display_name"] == "Football Season 2026"
        assert config["season_label"] == "2026 Season"
        assert config["pick_noun"] == "game"
        assert config["period_type"] == "week"
        assert config["lock_label"] == "lock of the week"


def test_get_app_config_march_madness():
    """Test complete app config for march_madness mode."""
    with mock.patch.dict(os.environ, {"SPORT_MODE": "march_madness", "LEAGUE_ID": "march_madness_2025"}):
        config = get_app_config()
        
        assert config["product_name"] == "Spreads"
        assert config["league_id"] == "march_madness_2025"
        assert config["sport_mode"] == "march_madness"
        assert config["display_name"] == "March Madness 2025"
        assert config["season_label"] == "March Madness 2025"
        assert config["pick_noun"] == "matchup"
        assert config["period_type"] == "round"
        assert config["lock_label"] == "lock of the day"


def test_get_sport_display_config_football():
    """Test legacy sport display config for football."""
    with mock.patch.dict(os.environ, {"SPORT_MODE": "football"}):
        config = get_sport_display_config()
        
        assert config["sport_mode"] == "football"
        assert config["pick_noun"] == "game"
        assert config["period_type"] == "week"


def test_get_sport_display_config_march_madness():
    """Test legacy sport display config for march_madness."""
    with mock.patch.dict(os.environ, {"SPORT_MODE": "march_madness"}):
        config = get_sport_display_config()
        
        assert config["sport_mode"] == "march_madness"
        assert config["pick_noun"] == "matchup"
        assert config["period_type"] == "round"


def test_get_scoreboard_urls_football():
    """Test scoreboard URLs for football mode."""
    with mock.patch.dict(os.environ, {"SPORT_MODE": "football"}):
        urls = get_scoreboard_urls()
        
        assert "nfl" in urls
        assert "cfb" in urls
        assert "cbssports.com" in urls["nfl"]
        assert "cbssports.com" in urls["cfb"]


def test_get_scoreboard_urls_march_madness():
    """Test scoreboard URLs for march_madness mode."""
    with mock.patch.dict(os.environ, {"SPORT_MODE": "march_madness"}):
        urls = get_scoreboard_urls()
        
        assert "college-basketball" in urls
        assert "cbssports.com" in urls["college-basketball"]
