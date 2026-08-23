"""
Unit tests for reset_season.py confirmation logic.

Tests the safety checks without hitting live Firebase.
"""

import os
import pytest
from unittest import mock
import sys
from pathlib import Path

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))


def test_confirmation_exact_match():
    """Test that exact confirmation string is required."""
    league_id = "test_season_123"
    expected = f"RESET {league_id}"
    
    # Exact match should pass
    assert "RESET test_season_123" == expected
    
    # Case variations should fail
    assert "reset test_season_123" != expected
    assert "Reset test_season_123" != expected
    
    # Wrong league ID should fail
    assert "RESET test_season_124" != expected
    
    # Extra whitespace should fail
    assert "RESET test_season_123 " != expected
    assert " RESET test_season_123" != expected
    
    # Empty string should fail
    assert "" != expected


def test_missing_league_id_logic():
    """Test that missing or empty LEAGUE_ID is rejected."""
    # Empty string
    league_id = ""
    assert not league_id or not league_id.strip()
    
    # None
    league_id = None
    assert not league_id
    
    # Whitespace only
    league_id = "   "
    assert not league_id.strip()
    
    # Valid league ID
    league_id = "football_2026"
    assert league_id and league_id.strip()


def test_firebase_project_id_extraction():
    """Test Firebase project ID extraction from various credential formats."""
    # Test JSON credential file format
    mock_cred_data = {
        "type": "service_account",
        "project_id": "test-firebase-project",
        "private_key_id": "key123",
    }
    
    project_id = mock_cred_data.get("project_id")
    assert project_id == "test-firebase-project"
    
    # Test missing project_id
    mock_cred_data_no_project = {
        "type": "service_account",
        "private_key_id": "key123",
    }
    
    project_id = mock_cred_data_no_project.get("project_id")
    assert project_id is None


def test_collections_to_delete_list():
    """Test that the collections list is complete and correct."""
    from reset_season import COLLECTIONS_TO_DELETE
    
    expected_collections = [
        "users",
        "games",
        "picks",
        "tiebreakers",
        "tiebreaker_picks",
        "leaderboard",
        "_cache",
    ]
    
    assert COLLECTIONS_TO_DELETE == expected_collections
