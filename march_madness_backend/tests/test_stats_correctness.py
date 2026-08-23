"""
Tests for stats correctness - ensuring unsettled picks are handled properly.

These tests verify that:
1. Unsettled picks (no winning_team) are excluded from totals and incorrect counts
2. Settled losses still count as incorrect
3. Push games (winning_team == "PUSH") count in push_games, not incorrect_picks
4. Streaks ignore unsettled picks (they don't break or extend W/L streaks)
"""

from datetime import datetime, timezone


def test_pick_is_settled_with_winner():
    """Game with winning_team set (including PUSH) is settled."""
    from main import pick_is_settled
    
    # Regular win
    game = {"winning_team": "Duke"}
    assert pick_is_settled(game) is True
    
    # Push is settled
    game = {"winning_team": "PUSH"}
    assert pick_is_settled(game) is True


def test_pick_is_settled_no_winner():
    """Game without winning_team is unsettled."""
    from main import pick_is_settled
    
    # Empty string
    game = {"winning_team": ""}
    assert pick_is_settled(game) is False
    
    # None
    game = {"winning_team": None}
    assert pick_is_settled(game) is False
    
    # Missing key
    game = {}
    assert pick_is_settled(game) is False


def test_pick_is_settled_none_game():
    """None game dict is treated as unsettled."""
    from main import pick_is_settled
    
    assert pick_is_settled(None) is False


def test_compute_stats_excludes_unsettled():
    """_compute_player_stats_list should exclude unsettled picks from all counts."""
    from main import _compute_player_stats_list
    from unittest.mock import MagicMock
    
    # Mock database
    mock_db = MagicMock()
    
    # Mock user
    user_doc = MagicMock()
    user_doc.to_dict.return_value = {
        "uid": "user1",
        "display_name": "Test User",
        "created_at": None,
    }
    mock_db.collection.return_value.where.return_value.stream.return_value = [user_doc]
    
    # Mock games - one settled, one unsettled
    game1 = MagicMock()
    game1.id = "game1"
    game1.to_dict.return_value = {
        "winning_team": "Duke",  # Settled
    }
    
    game2 = MagicMock()
    game2.id = "game2"
    game2.to_dict.return_value = {
        "winning_team": "",  # Unsettled
    }
    
    # Mock picks - one for each game
    pick1 = MagicMock()
    pick1.to_dict.return_value = {
        "user_id": "user1",
        "game_id": "game1",
        "points_awarded": 0,  # Lost
        "lock": False,
    }
    
    pick2 = MagicMock()
    pick2.to_dict.return_value = {
        "user_id": "user1",
        "game_id": "game2",
        "points_awarded": 0,  # Unsettled (but appears like a loss)
        "lock": False,
    }
    
    # Setup mock to return different collections
    def collection_side_effect(name):
        mock_collection = MagicMock()
        if name == "users":
            mock_collection.where.return_value.stream.return_value = [user_doc]
        elif name == "games":
            mock_collection.stream.return_value = [game1, game2]
        elif name == "picks":
            mock_collection.stream.return_value = [pick1, pick2]
        return mock_collection
    
    mock_db.collection.side_effect = collection_side_effect
    
    # Run computation
    result = _compute_player_stats_list(mock_db)
    
    # Verify: only 1 pick counted (the settled loss), unsettled excluded
    assert len(result) == 1
    user_stats = result[0]
    assert user_stats["total_picks"] == 1  # Only settled pick
    assert user_stats["correct_picks"] == 0
    assert user_stats["incorrect_picks"] == 1  # Only the settled loss
    assert user_stats["push_games"] == 0


def test_compute_stats_push_not_incorrect():
    """Push games should count in push_games, NOT incorrect_picks."""
    from main import _compute_player_stats_list
    from unittest.mock import MagicMock
    
    mock_db = MagicMock()
    
    # Mock user
    user_doc = MagicMock()
    user_doc.to_dict.return_value = {
        "uid": "user1",
        "display_name": "Test User",
        "created_at": None,
    }
    
    # Mock game with PUSH result
    game = MagicMock()
    game.id = "game1"
    game.to_dict.return_value = {
        "winning_team": "PUSH",
    }
    
    # Mock pick
    pick = MagicMock()
    pick.to_dict.return_value = {
        "user_id": "user1",
        "game_id": "game1",
        "points_awarded": 0,  # Push scores 0
        "lock": False,
    }
    
    def collection_side_effect(name):
        mock_collection = MagicMock()
        if name == "users":
            mock_collection.where.return_value.stream.return_value = [user_doc]
        elif name == "games":
            mock_collection.stream.return_value = [game]
        elif name == "picks":
            mock_collection.stream.return_value = [pick]
        return mock_collection
    
    mock_db.collection.side_effect = collection_side_effect
    
    result = _compute_player_stats_list(mock_db)
    
    assert len(result) == 1
    user_stats = result[0]
    assert user_stats["total_picks"] == 1
    assert user_stats["correct_picks"] == 0
    assert user_stats["incorrect_picks"] == 0  # Push is NOT incorrect
    assert user_stats["push_games"] == 1  # Push counted here


def test_detailed_stats_pending_label():
    """get_player_detailed_stats should label unsettled picks as 'pending'."""
    from main import pick_is_settled
    
    # Simulate the logic in get_player_detailed_stats
    def classify_pick(pts, wt):
        game_dict = {"winning_team": wt}
        if not pick_is_settled(game_dict):
            return "pending"
        elif pts > 0:
            return "correct"
        elif wt == "PUSH":
            return "push"
        else:
            return "incorrect"
    
    # Test cases
    assert classify_pick(0, "") == "pending"  # Unsettled
    assert classify_pick(0, None) == "pending"  # Unsettled
    assert classify_pick(1, "Duke") == "correct"  # Win
    assert classify_pick(0, "PUSH") == "push"  # Push
    assert classify_pick(0, "Duke") == "incorrect"  # Loss


def test_streaks_ignore_unsettled():
    """Streaks should skip unsettled picks - they don't break W/L runs."""
    from main import pick_is_settled
    
    # Simulate streak calculation logic
    # 3 wins, 1 unsettled, 2 losses (most recent to oldest)
    mock_picks = [
        {"points_awarded": 0, "winning_team": "UNC"},      # L
        {"points_awarded": 0, "winning_team": "Duke"},     # L
        {"points_awarded": 0, "winning_team": ""},         # Unsettled (skip)
        {"points_awarded": 1, "winning_team": "Duke"},     # W
        {"points_awarded": 1, "winning_team": "UNC"},      # W
        {"points_awarded": 1, "winning_team": "Duke"},     # W
    ]
    
    # Build streak results (skip unsettled)
    streak_results = []
    for p in mock_picks:
        game_dict = {"winning_team": p["winning_team"]}
        if not pick_is_settled(game_dict):
            continue  # Skip unsettled
        
        pts = p["points_awarded"]
        wt = p["winning_team"]
        if pts > 0:
            streak_results.append("W")
        elif wt == "PUSH":
            streak_results.append("P")
        else:
            streak_results.append("L")
    
    # Expected: [L, L, W, W, W] (unsettled excluded)
    assert streak_results == ["L", "L", "W", "W", "W"]
    
    # Current streak (most recent) should be 2 losses
    assert streak_results[0] == "L"
    count = 1
    for r in streak_results[1:]:
        if r == "L":
            count += 1
        else:
            break
    assert count == 2
    
    # Best win streak should be 3
    max_w = 0
    current_w = 0
    for r in streak_results:
        if r == "W":
            current_w += 1
            max_w = max(max_w, current_w)
        else:
            current_w = 0
    assert max_w == 3


def test_streaks_push_breaks_streak():
    """Push (settled) should break W/L streaks per existing logic."""
    from main import pick_is_settled
    
    # W, W, PUSH, W, W
    mock_picks = [
        {"points_awarded": 1, "winning_team": "Duke"},     # W
        {"points_awarded": 1, "winning_team": "UNC"},      # W
        {"points_awarded": 0, "winning_team": "PUSH"},     # P (breaks)
        {"points_awarded": 1, "winning_team": "Duke"},     # W
        {"points_awarded": 1, "winning_team": "UNC"},      # W
    ]
    
    streak_results = []
    for p in mock_picks:
        game_dict = {"winning_team": p["winning_team"]}
        if not pick_is_settled(game_dict):
            continue
        
        pts = p["points_awarded"]
        wt = p["winning_team"]
        if pts > 0:
            streak_results.append("W")
        elif wt == "PUSH":
            streak_results.append("P")
        else:
            streak_results.append("L")
    
    assert streak_results == ["W", "W", "P", "W", "W"]
    
    # Current streak: 2 wins (push breaks earlier streak)
    # Max win streak should still be 2 (not 4, because push breaks)
    max_w = 0
    current_w = 0
    for r in streak_results:
        if r == "W":
            current_w += 1
            max_w = max(max_w, current_w)
        else:
            current_w = 0  # Push or Loss breaks
    assert max_w == 2
