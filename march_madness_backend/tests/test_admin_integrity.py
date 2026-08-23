"""
Tests for PRD-05: Admin Period Locks + Game Result Integrity

Tests validation helpers, clear-result rescoring, and admin period selection.
"""

import pytest
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from main import validate_picked_team, validate_winning_team, _clear_game_scores
from scoring import get_week_bounds, get_lock_day_bounds
from sport_config import SportMode, get_sport_mode


class TestValidatePickedTeam:
    """Test picked_team validation (allows trailing ' *')."""

    def test_valid_home(self):
        assert validate_picked_team("home") == "home"

    def test_valid_away(self):
        assert validate_picked_team("away") == "away"

    def test_home_with_lock_marker(self):
        """Allow 'home *' (CSV import lock marker)."""
        assert validate_picked_team("home *") == "home"

    def test_away_with_lock_marker(self):
        """Allow 'away *' (CSV import lock marker)."""
        assert validate_picked_team("away *") == "away"

    def test_uppercase_home_rejected(self):
        """Uppercase 'HOME' should be rejected (case-sensitive)."""
        with pytest.raises(ValueError, match="must be 'home' or 'away'"):
            validate_picked_team("HOME")

    def test_uppercase_away_rejected(self):
        """Uppercase 'AWAY' should be rejected (case-sensitive)."""
        with pytest.raises(ValueError, match="must be 'home' or 'away'"):
            validate_picked_team("AWAY")

    def test_invalid_team_neutral(self):
        with pytest.raises(ValueError, match="must be 'home' or 'away'"):
            validate_picked_team("neutral")

    def test_invalid_team_visitor(self):
        with pytest.raises(ValueError, match="must be 'home' or 'away'"):
            validate_picked_team("visitor")

    def test_empty_string(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_picked_team("")

    def test_whitespace_only(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_picked_team("   ")


class TestValidateWinningTeam:
    """Test winning_team validation (home, away, PUSH, or None)."""

    def test_valid_home_lowercase(self):
        assert validate_winning_team("home") == "home"

    def test_valid_away_lowercase(self):
        assert validate_winning_team("away") == "away"

    def test_valid_push_uppercase(self):
        assert validate_winning_team("PUSH") == "PUSH"

    def test_valid_push_lowercase_normalized(self):
        """'push' should be normalized to 'PUSH'."""
        assert validate_winning_team("push") == "PUSH"

    def test_valid_push_mixedcase_normalized(self):
        """'Push' should be normalized to 'PUSH'."""
        assert validate_winning_team("Push") == "PUSH"

    def test_valid_home_uppercase_normalized(self):
        """'HOME' should be normalized to 'home'."""
        assert validate_winning_team("HOME") == "home"

    def test_valid_away_uppercase_normalized(self):
        """'AWAY' should be normalized to 'away'."""
        assert validate_winning_team("AWAY") == "away"

    def test_empty_string_returns_none(self):
        """Empty string should return None (cleared result)."""
        assert validate_winning_team("") is None

    def test_none_returns_none(self):
        """None input should return None."""
        assert validate_winning_team(None) is None

    def test_whitespace_only_returns_none(self):
        """Whitespace-only should return None."""
        assert validate_winning_team("   ") is None

    def test_invalid_team_tie(self):
        with pytest.raises(ValueError, match="must be 'home', 'away', or 'PUSH'"):
            validate_winning_team("tie")

    def test_invalid_team_draw(self):
        with pytest.raises(ValueError, match="must be 'home', 'away', or 'PUSH'"):
            validate_winning_team("draw")

    def test_invalid_team_neutral(self):
        with pytest.raises(ValueError, match="must be 'home', 'away', or 'PUSH'"):
            validate_winning_team("neutral")


class TestClearGameScores:
    """Test _clear_game_scores helper (zeros picks, negative deltas)."""

    def test_clear_game_scores_zeros_picks(self, db_mock):
        """Clearing a result should zero all pick points."""
        # Mock setup: game with 3 picks awarded
        game_id = "game123"
        picks_data = [
            {"id": "pick1", "user_id": "user1", "points_awarded": 2, "game_id": game_id},
            {"id": "pick2", "user_id": "user2", "points_awarded": 1, "game_id": game_id},
            {"id": "pick3", "user_id": "user3", "points_awarded": 0, "game_id": game_id},
        ]
        
        # Mock Firestore queries
        db_mock.collection("picks").where("game_id", "==", game_id).stream.return_value = [
            MockSnapshot(p["id"], p) for p in picks_data
        ]
        
        # Execute
        affected, deltas = _clear_game_scores(db_mock, game_id)
        
        # Verify all picks zeroed
        assert len(affected) == 3
        assert all(p["points_awarded"] == 0 for p in affected)
        
        # Verify negative deltas
        assert deltas["user1"] == -2
        assert deltas["user2"] == -1
        assert deltas["user3"] == 0  # Already zero

    def test_clear_game_scores_no_picks(self, db_mock):
        """Clearing a game with no picks should return empty results."""
        game_id = "game456"
        db_mock.collection("picks").where("game_id", "==", game_id).stream.return_value = []
        
        affected, deltas = _clear_game_scores(db_mock, game_id)
        
        assert len(affected) == 0
        assert len(deltas) == 0


class TestAdminPeriodSelection:
    """Test admin lock period selection by sport mode."""

    def test_football_uses_week_bounds(self, monkeypatch):
        """Football mode should use get_week_bounds for admin lock checking."""
        # Mock sport mode as football
        monkeypatch.setenv("SPORT_MODE", "football")
        
        # Test timestamp: Thursday, Sept 3, 2026, 8:00 PM ET
        test_time = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)  # Midnight UTC = 8pm ET prev day
        
        start, end = get_week_bounds(test_time)
        
        # Should be in Week 1 (Wed Sep 2 - Tue Sep 8)
        expected_start = datetime(2026, 9, 2, 4, 0, tzinfo=timezone.utc)  # Wed 00:00 ET = 04:00 UTC (EDT)
        expected_end = datetime(2026, 9, 9, 4, 0, tzinfo=timezone.utc)    # Next Wed 00:00 ET
        
        assert start == expected_start
        assert end == expected_end

    def test_march_madness_uses_day_bounds(self, monkeypatch):
        """March Madness mode should use get_lock_day_bounds for admin lock checking."""
        # Mock sport mode as march_madness
        monkeypatch.setenv("SPORT_MODE", "march_madness")
        
        # Test timestamp: March 15, 2026, 8:00 PM ET
        test_time = datetime(2026, 3, 16, 0, 0, tzinfo=timezone.utc)  # Midnight UTC
        
        start, end = get_lock_day_bounds(test_time)
        
        # Should be 3am-3am ET day bounds
        # At 8pm ET (midnight UTC), we're in the 3am-same-day window
        et_tz = ZoneInfo("America/New_York")
        local = test_time.astimezone(et_tz)
        expected_day = local.date()  # March 15
        
        expected_start = datetime(2026, 3, 15, 3, 0, tzinfo=et_tz).astimezone(timezone.utc)
        expected_end = datetime(2026, 3, 16, 3, 0, tzinfo=et_tz).astimezone(timezone.utc)
        
        assert start == expected_start
        assert end == expected_end

    def test_football_week_spans_multiple_days(self):
        """Football week should include games from Wednesday through Tuesday."""
        # Monday Sept 7, 2026 at 9pm ET (still in Week 1)
        monday_et = datetime(2026, 9, 7, 21, 0, tzinfo=ZoneInfo("America/New_York"))
        monday_utc = monday_et.astimezone(timezone.utc)
        
        start, end = get_week_bounds(monday_utc)
        
        # Should still be Week 1 (Wed Sep 2 - Tue Sep 8)
        assert start == datetime(2026, 9, 2, 4, 0, tzinfo=timezone.utc)
        assert end == datetime(2026, 9, 9, 4, 0, tzinfo=timezone.utc)
        
        # Monday 9pm should be within this week
        assert start <= monday_utc < end


# Test fixtures

class MockSnapshot:
    """Mock Firestore document snapshot."""
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data
        self.reference = MockReference(doc_id)
    
    def to_dict(self):
        return self._data


class MockReference:
    """Mock Firestore document reference."""
    def __init__(self, doc_id):
        self.id = doc_id
        self.updates = []
    
    def update(self, data):
        self.updates.append(data)


@pytest.fixture
def db_mock(mocker):
    """Mock Firestore database."""
    db = mocker.MagicMock()
    return db
