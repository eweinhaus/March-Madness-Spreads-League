"""
Tests for PRD-05: Admin Period Locks + Game Result Integrity

Tests validation helpers, clear-result rescoring, and admin period selection.
"""

import pytest
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock

from fastapi import HTTPException
from main import assert_valid_pick_team, assert_valid_winning_team, _clear_game_scores
from scoring import get_week_bounds, get_lock_day_bounds
from sport_config import SportMode


# Sample game fixture
MOCK_GAME = {
    "home_team": "Kansas City Chiefs",
    "away_team": "Buffalo Bills",
    "spread": 3.5,
    "game_date": datetime(2026, 9, 10, 1, 0, tzinfo=timezone.utc),
}


class TestValidatePickedTeam:
    """Test picked_team validation (real team names with optional ' *' marker)."""

    def test_valid_home_team(self):
        """Picking the home team should succeed."""
        # Should not raise
        assert_valid_pick_team(MOCK_GAME, "Kansas City Chiefs")

    def test_valid_away_team(self):
        """Picking the away team should succeed."""
        # Should not raise
        assert_valid_pick_team(MOCK_GAME, "Buffalo Bills")

    def test_home_team_with_lock_marker(self):
        """Home team with trailing ' *' (lock marker) should be allowed."""
        # Should not raise
        assert_valid_pick_team(MOCK_GAME, "Kansas City Chiefs *")

    def test_away_team_with_lock_marker(self):
        """Away team with trailing ' *' (lock marker) should be allowed."""
        # Should not raise
        assert_valid_pick_team(MOCK_GAME, "Buffalo Bills *")

    def test_invalid_team_name(self):
        """Picking a team not in the game should fail."""
        with pytest.raises(HTTPException) as exc_info:
            assert_valid_pick_team(MOCK_GAME, "Green Bay Packers")
        assert exc_info.value.status_code == 400
        assert "must be the home or away team" in exc_info.value.detail

    def test_partial_team_name(self):
        """Partial team name should fail."""
        with pytest.raises(HTTPException) as exc_info:
            assert_valid_pick_team(MOCK_GAME, "Kansas City")
        assert exc_info.value.status_code == 400

    def test_empty_string(self):
        """Empty picked_team should fail."""
        with pytest.raises(HTTPException) as exc_info:
            assert_valid_pick_team(MOCK_GAME, "")
        assert exc_info.value.status_code == 400

    def test_case_sensitive(self):
        """Team names are case-sensitive."""
        with pytest.raises(HTTPException) as exc_info:
            assert_valid_pick_team(MOCK_GAME, "kansas city chiefs")
        assert exc_info.value.status_code == 400


class TestValidateWinningTeam:
    """Test winning_team validation (team names or PUSH)."""

    def test_valid_home_team_winner(self):
        """Setting home team as winner should succeed."""
        # Should not raise
        assert_valid_winning_team(MOCK_GAME, "Kansas City Chiefs")

    def test_valid_away_team_winner(self):
        """Setting away team as winner should succeed."""
        # Should not raise
        assert_valid_winning_team(MOCK_GAME, "Buffalo Bills")

    def test_valid_push(self):
        """PUSH is a valid winning_team value."""
        # Should not raise
        assert_valid_winning_team(MOCK_GAME, "PUSH")

    def test_invalid_team_as_winner(self):
        """Setting a team not in the game as winner should fail."""
        with pytest.raises(HTTPException) as exc_info:
            assert_valid_winning_team(MOCK_GAME, "Green Bay Packers")
        assert exc_info.value.status_code == 400
        assert "must be home team, away team, or PUSH" in exc_info.value.detail

    def test_lowercase_push_not_allowed(self):
        """'push' should fail (PUSH must be uppercase)."""
        with pytest.raises(HTTPException) as exc_info:
            assert_valid_winning_team(MOCK_GAME, "push")
        assert exc_info.value.status_code == 400

    def test_tie_not_allowed(self):
        """'tie' is not a valid value."""
        with pytest.raises(HTTPException) as exc_info:
            assert_valid_winning_team(MOCK_GAME, "tie")
        assert exc_info.value.status_code == 400

    def test_draw_not_allowed(self):
        """'draw' is not a valid value."""
        with pytest.raises(HTTPException) as exc_info:
            assert_valid_winning_team(MOCK_GAME, "draw")
        assert exc_info.value.status_code == 400

    def test_empty_string(self):
        """Empty string should fail."""
        with pytest.raises(HTTPException) as exc_info:
            assert_valid_winning_team(MOCK_GAME, "")
        assert exc_info.value.status_code == 400


class TestClearGameScores:
    """Test _clear_game_scores helper (zeros picks, negative deltas)."""

    def test_clear_game_scores_zeros_picks(self):
        """Clearing a result should zero all pick points and create negative deltas."""
        # Mock database
        db_mock = MagicMock()
        game_id = "game123"
        
        # Mock picks data
        picks_data = [
            {"user_id": "user1", "points_awarded": 2, "game_id": game_id},
            {"user_id": "user2", "points_awarded": 1, "game_id": game_id},
            {"user_id": "user3", "points_awarded": 0, "game_id": game_id},
        ]
        
        # Create mock snapshots
        mock_snaps = []
        for i, p in enumerate(picks_data):
            snap = MagicMock()
            snap.id = f"pick{i+1}"
            snap.to_dict.return_value = p
            mock_snaps.append(snap)
        
        # Mock Firestore query chain
        where_mock = MagicMock()
        stream_mock = MagicMock(return_value=mock_snaps)
        where_mock.stream = stream_mock
        
        collection_mock = MagicMock()
        collection_mock.where.return_value = where_mock
        collection_mock.document.return_value.update = MagicMock()
        
        db_mock.collection.return_value = collection_mock
        
        # Execute
        affected, deltas = _clear_game_scores(db_mock, game_id)
        
        # Verify all picks zeroed
        assert len(affected) == 3
        assert all(p["points_awarded"] == 0 for p in affected)
        
        # Verify negative deltas
        assert deltas["user1"] == -2
        assert deltas["user2"] == -1
        assert deltas["user3"] == 0  # Already zero

    def test_clear_game_scores_no_picks(self):
        """Clearing a game with no picks should return empty results."""
        db_mock = MagicMock()
        game_id = "game456"
        
        # Mock empty query result
        where_mock = MagicMock()
        where_mock.stream.return_value = []
        
        collection_mock = MagicMock()
        collection_mock.where.return_value = where_mock
        
        db_mock.collection.return_value = collection_mock
        
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
