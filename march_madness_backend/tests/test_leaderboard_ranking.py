"""
Tests for PRD-03 leaderboard ranking logic.

Tests football 4-tier ranking: total_points (game picks only) DESC,
first_tiebreaker_diff ASC, correct_locks DESC, display_name ASC.
"""

import pytest
from datetime import datetime, timezone
from main import _leaderboard_list_for_filter
from sport_config import SportMode
from unittest.mock import patch


@pytest.fixture
def mock_users():
    """Mock users for testing."""
    return {
        "user1": {"uid": "user1", "display_name": "Alice", "make_picks": True},
        "user2": {"uid": "user2", "display_name": "Bob", "make_picks": True},
        "user3": {"uid": "user3", "display_name": "Charlie", "make_picks": True},
        "user4": {"uid": "user4", "display_name": "David", "make_picks": True},
    }


@pytest.fixture
def mock_games():
    """Mock games for testing."""
    return {
        "game1": {
            "id": "game1",
            "home_team": "Team A",
            "away_team": "Team B",
            "spread": 3.5,
            "game_date": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc),
        },
        "game2": {
            "id": "game2",
            "home_team": "Team C",
            "away_team": "Team D",
            "spread": -7.0,
            "game_date": datetime(2026, 9, 6, 20, 0, 0, tzinfo=timezone.utc),
        },
    }


@pytest.fixture
def mock_tiebreakers():
    """Mock tiebreakers with answer set."""
    return {
        "tb1": {
            "id": "tb1",
            "question": "Total points in game?",
            "start_time": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc),
            "answer": "45",
        },
        "tb2": {
            "id": "tb2",
            "question": "Another question?",
            "start_time": datetime(2026, 9, 6, 20, 0, 0, tzinfo=timezone.utc),
            "answer": "30",
        },
    }


@patch('main.get_sport_mode')
def test_football_ranking_same_points_different_tb(mock_mode, mock_users, mock_games, mock_tiebreakers):
    """Test football ranking: same game points, different first TB diff."""
    mock_mode.return_value = SportMode.FOOTBALL
    
    # Both users: 2 points from game picks, different TB accuracy
    all_picks = [
        {"user_id": "user1", "game_id": "game1", "points_awarded": 1, "lock": False, "game_date": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},
        {"user_id": "user1", "game_id": "game2", "points_awarded": 1, "lock": False, "game_date": datetime(2026, 9, 6, 20, 0, 0, tzinfo=timezone.utc)},
        {"user_id": "user2", "game_id": "game1", "points_awarded": 1, "lock": False, "game_date": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},
        {"user_id": "user2", "game_id": "game2", "points_awarded": 1, "lock": False, "game_date": datetime(2026, 9, 6, 20, 0, 0, tzinfo=timezone.utc)},
    ]
    
    all_tb_picks = [
        {"user_id": "user1", "tiebreaker_id": "tb1", "answer": "50", "points_awarded": 0, "start_time": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},  # diff = 5
        {"user_id": "user2", "tiebreaker_id": "tb1", "answer": "43", "points_awarded": 0, "start_time": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},  # diff = 2
    ]
    
    leaderboard = _leaderboard_list_for_filter(
        mock_users, mock_games, mock_tiebreakers, all_picks, all_tb_picks, "overall"
    )
    
    # Both have 2 points, but user2 has better TB (2 vs 5)
    assert leaderboard[0]["uid"] == "user2"
    assert leaderboard[0]["total_points"] == 2
    assert leaderboard[0]["first_tiebreaker_diff"] == 2.0
    
    assert leaderboard[1]["uid"] == "user1"
    assert leaderboard[1]["total_points"] == 2
    assert leaderboard[1]["first_tiebreaker_diff"] == 5.0


@patch('main.get_sport_mode')
def test_football_ranking_no_tb_pick(mock_mode, mock_users, mock_games, mock_tiebreakers):
    """Test football ranking: user with no TB pick gets 999999 diff."""
    mock_mode.return_value = SportMode.FOOTBALL
    
    all_picks = [
        {"user_id": "user1", "game_id": "game1", "points_awarded": 2, "lock": False, "game_date": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},
        {"user_id": "user2", "game_id": "game1", "points_awarded": 2, "lock": False, "game_date": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},
    ]
    
    # User1 has TB pick, user2 does not
    all_tb_picks = [
        {"user_id": "user1", "tiebreaker_id": "tb1", "answer": "45", "points_awarded": 0, "start_time": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},  # diff = 0 (exact)
    ]
    
    leaderboard = _leaderboard_list_for_filter(
        mock_users, mock_games, mock_tiebreakers, all_picks, all_tb_picks, "overall"
    )
    
    # User1 ranks first (same points, better TB)
    assert leaderboard[0]["uid"] == "user1"
    assert leaderboard[0]["first_tiebreaker_diff"] == 0.0
    
    assert leaderboard[1]["uid"] == "user2"
    assert leaderboard[1]["first_tiebreaker_diff"] == 999999


@patch('main.get_sport_mode')
def test_football_ranking_multiple_tbs_earliest_only(mock_mode, mock_users, mock_games, mock_tiebreakers):
    """Test football ranking: multiple TBs, only earliest start_time counts."""
    mock_mode.return_value = SportMode.FOOTBALL
    
    all_picks = [
        {"user_id": "user1", "game_id": "game1", "points_awarded": 3, "lock": False, "game_date": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},
    ]
    
    # User1 has 2 TB picks, tb1 is earlier (should be used for ranking)
    all_tb_picks = [
        {"user_id": "user1", "tiebreaker_id": "tb1", "answer": "50", "points_awarded": 0, "start_time": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},  # diff = 5 (earlier)
        {"user_id": "user1", "tiebreaker_id": "tb2", "answer": "31", "points_awarded": 0, "start_time": datetime(2026, 9, 6, 20, 0, 0, tzinfo=timezone.utc)},  # diff = 1 (later)
    ]
    
    leaderboard = _leaderboard_list_for_filter(
        mock_users, mock_games, mock_tiebreakers, all_picks, all_tb_picks, "overall"
    )
    
    # Should use tb1 (earlier) with diff=5, not tb2 with diff=1
    assert leaderboard[0]["uid"] == "user1"
    assert leaderboard[0]["first_tiebreaker_diff"] == 5.0


@patch('main.get_sport_mode')
def test_football_ranking_tb_points_excluded(mock_mode, mock_users, mock_games, mock_tiebreakers):
    """Test football ranking: TB points_awarded not included in total_points."""
    mock_mode.return_value = SportMode.FOOTBALL
    
    all_picks = [
        {"user_id": "user1", "game_id": "game1", "points_awarded": 2, "lock": True, "game_date": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},
    ]
    
    # TB pick with points_awarded (should be ignored in football)
    all_tb_picks = [
        {"user_id": "user1", "tiebreaker_id": "tb1", "answer": "45", "points_awarded": 3, "start_time": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},
    ]
    
    leaderboard = _leaderboard_list_for_filter(
        mock_users, mock_games, mock_tiebreakers, all_picks, all_tb_picks, "overall"
    )
    
    # total_points should be 2 (game only), NOT 5 (game + TB)
    assert leaderboard[0]["total_points"] == 2


@patch('main.get_sport_mode')
def test_football_ranking_correct_locks_tiebreaker(mock_mode, mock_users, mock_games, mock_tiebreakers):
    """Test football ranking: same points, same TB, different correct locks."""
    mock_mode.return_value = SportMode.FOOTBALL
    
    all_picks = [
        {"user_id": "user1", "game_id": "game1", "points_awarded": 1, "lock": False, "game_date": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},
        {"user_id": "user1", "game_id": "game2", "points_awarded": 2, "lock": True, "game_date": datetime(2026, 9, 6, 20, 0, 0, tzinfo=timezone.utc)},  # Correct lock
        {"user_id": "user2", "game_id": "game1", "points_awarded": 2, "lock": True, "game_date": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},  # Correct lock
        {"user_id": "user2", "game_id": "game2", "points_awarded": 1, "lock": False, "game_date": datetime(2026, 9, 6, 20, 0, 0, tzinfo=timezone.utc)},
    ]
    
    # Both same TB accuracy
    all_tb_picks = [
        {"user_id": "user1", "tiebreaker_id": "tb1", "answer": "45", "points_awarded": 0, "start_time": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},
        {"user_id": "user2", "tiebreaker_id": "tb1", "answer": "45", "points_awarded": 0, "start_time": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},
    ]
    
    leaderboard = _leaderboard_list_for_filter(
        mock_users, mock_games, mock_tiebreakers, all_picks, all_tb_picks, "overall"
    )
    
    # Both have 3 points, same TB diff (0), but both have 1 correct lock
    # Should be tied on first 3 criteria, so alphabetical by name
    assert leaderboard[0]["display_name"] == "Alice"
    assert leaderboard[1]["display_name"] == "Bob"


@patch('main.get_sport_mode')
def test_football_ranking_display_name_final_tiebreaker(mock_mode, mock_users, mock_games, mock_tiebreakers):
    """Test football ranking: display_name alphabetical as final tiebreaker."""
    mock_mode.return_value = SportMode.FOOTBALL
    
    all_picks = [
        {"user_id": "user3", "game_id": "game1", "points_awarded": 1, "lock": False, "game_date": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},
        {"user_id": "user1", "game_id": "game1", "points_awarded": 1, "lock": False, "game_date": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},
    ]
    
    # Both same TB accuracy
    all_tb_picks = [
        {"user_id": "user3", "tiebreaker_id": "tb1", "answer": "45", "points_awarded": 0, "start_time": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},
        {"user_id": "user1", "tiebreaker_id": "tb1", "answer": "45", "points_awarded": 0, "start_time": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},
    ]
    
    leaderboard = _leaderboard_list_for_filter(
        mock_users, mock_games, mock_tiebreakers, all_picks, all_tb_picks, "overall"
    )
    
    # Alice < Charlie alphabetically
    assert leaderboard[0]["display_name"] == "Alice"
    assert leaderboard[1]["display_name"] == "Charlie"


@patch('main.get_sport_mode')
def test_march_madness_ranking_unchanged(mock_mode, mock_users, mock_games, mock_tiebreakers):
    """Test march_madness mode still uses 3 TBs and includes TB points."""
    mock_mode.return_value = SportMode.MARCH_MADNESS
    
    all_picks = [
        {"user_id": "user1", "game_id": "game1", "points_awarded": 1, "lock": False, "game_date": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},
    ]
    
    all_tb_picks = [
        {"user_id": "user1", "tiebreaker_id": "tb1", "answer": "45", "points_awarded": 3, "start_time": datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)},
    ]
    
    leaderboard = _leaderboard_list_for_filter(
        mock_users, mock_games, mock_tiebreakers, all_picks, all_tb_picks, "overall"
    )
    
    # March Madness includes TB points in total
    assert leaderboard[0]["total_points"] == 4  # 1 game + 3 TB
    assert leaderboard[0]["second_tiebreaker_diff"] == 999999  # Still tracked
    assert leaderboard[0]["third_tiebreaker_diff"] == 999999   # Still tracked
