"""
Unit tests for live scores fetching.

Tests that fetch_live_scores_merged correctly uses get_scoreboard_urls
and calls the appropriate CBS scoreboards based on sport mode.
"""

import os
import pytest
from unittest import mock
from unittest.mock import patch, MagicMock


def test_fetch_live_scores_uses_scoreboard_urls_football():
    """Test that fetch_live_scores_merged uses get_scoreboard_urls for football mode."""
    with mock.patch.dict(os.environ, {"SPORT_MODE": "football"}):
        # Import after setting env to ensure correct mode
        from main import fetch_live_scores_merged
        from sport_config import get_scoreboard_urls
        
        # Mock the CBS scraping function
        with patch('main.fetch_cbs_games_data') as mock_fetch:
            mock_fetch.return_value = [{"team": "Test", "score": 21}]
            
            # Get expected URLs
            expected_urls = get_scoreboard_urls()
            
            # Call the function
            result = fetch_live_scores_merged()
            
            # Verify it called fetch_cbs_games_data with both NFL and CFB URLs
            assert mock_fetch.call_count == 2
            call_args = [call[0][0] for call in mock_fetch.call_args_list]
            
            assert expected_urls["nfl"] in call_args
            assert expected_urls["cfb"] in call_args
            assert "cbssports.com/nfl/scoreboard" in call_args[0] or "cbssports.com/nfl/scoreboard" in call_args[1]
            assert "cbssports.com/college-football/scoreboard" in call_args[0] or "cbssports.com/college-football/scoreboard" in call_args[1]


def test_fetch_live_scores_uses_scoreboard_urls_march_madness():
    """Test that fetch_live_scores_merged uses get_scoreboard_urls for march_madness mode."""
    with mock.patch.dict(os.environ, {"SPORT_MODE": "march_madness"}):
        # Import after setting env to ensure correct mode
        from main import fetch_live_scores_merged
        from sport_config import get_scoreboard_urls
        
        # Mock the CBS scraping function
        with patch('main.fetch_cbs_games_data') as mock_fetch:
            mock_fetch.return_value = [{"team": "Test", "score": 75}]
            
            # Get expected URL
            expected_urls = get_scoreboard_urls()
            
            # Call the function
            result = fetch_live_scores_merged()
            
            # Verify it called fetch_cbs_games_data with basketball URL
            mock_fetch.assert_called_once()
            call_url = mock_fetch.call_args[0][0]
            
            assert "cbssports.com/college-basketball/scoreboard" in call_url


def test_fetch_live_scores_merges_football_results():
    """Test that football mode merges NFL and CFB results."""
    with mock.patch.dict(os.environ, {"SPORT_MODE": "football"}):
        from main import fetch_live_scores_merged
        
        nfl_games = [{"team": "Chiefs", "score": 28}]
        cfb_games = [{"team": "Alabama", "score": 35}]
        
        with patch('main.fetch_cbs_games_data') as mock_fetch:
            # Return different results for each call
            mock_fetch.side_effect = [nfl_games, cfb_games]
            
            result = fetch_live_scores_merged()
            
            # Should contain both sets of games
            assert len(result) == 2
            assert result[0] == nfl_games[0]
            assert result[1] == cfb_games[0]


def test_fetch_live_scores_handles_partial_failure():
    """Test that fetch_live_scores_merged continues if one board fails."""
    with mock.patch.dict(os.environ, {"SPORT_MODE": "football"}):
        from main import fetch_live_scores_merged
        
        nfl_games = [{"team": "Chiefs", "score": 28}]
        
        with patch('main.fetch_cbs_games_data') as mock_fetch:
            # First call (NFL) succeeds, second (CFB) fails
            mock_fetch.side_effect = [nfl_games, Exception("Network error")]
            
            result = fetch_live_scores_merged()
            
            # Should still return NFL games even though CFB failed
            assert len(result) == 1
            assert result[0] == nfl_games[0]
