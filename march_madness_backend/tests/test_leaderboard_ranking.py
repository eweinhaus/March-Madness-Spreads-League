"""
Tests for football leaderboard ranking.

Football sort: total_wins DESC, correct_locks DESC, display_name ASC
(case-insensitive). Numerical TB is not a sort key. March Madness sort is
unchanged (points, then locks, then TB diffs on non-overall).
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from main import _leaderboard_list_for_filter
from sport_config import SportMode


SEP5 = datetime(2026, 9, 5, 19, 0, 0, tzinfo=timezone.utc)
SEP6 = datetime(2026, 9, 6, 20, 0, 0, tzinfo=timezone.utc)


def _pick(uid, game_id, points_awarded, lock=False, game_date=SEP5):
    return {
        "user_id": uid,
        "game_id": game_id,
        "points_awarded": points_awarded,
        "lock": lock,
        "game_date": game_date,
    }


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
def blair_kyle_users():
    return {
        "blair": {"uid": "blair", "display_name": "Blair", "make_picks": True},
        "kyle": {"uid": "kyle", "display_name": "Kyle", "make_picks": True},
    }


@pytest.fixture
def mock_games():
    """Mock games for testing."""
    games = {
        "game1": {
            "id": "game1",
            "home_team": "Team A",
            "away_team": "Team B",
            "spread": 3.5,
            "game_date": SEP5,
        },
        "game2": {
            "id": "game2",
            "home_team": "Team C",
            "away_team": "Team D",
            "spread": -7.0,
            "game_date": SEP6,
        },
    }
    for i in range(3, 9):
        games[f"game{i}"] = {
            "id": f"game{i}",
            "home_team": f"Home{i}",
            "away_team": f"Away{i}",
            "spread": 3.5,
            "game_date": SEP5,
        }
    return games


@pytest.fixture
def mock_tiebreakers():
    """Mock tiebreakers with answer set."""
    return {
        "tb1": {
            "id": "tb1",
            "question": "Total points in game?",
            "start_time": SEP5,
            "answer": "45",
        },
        "tb2": {
            "id": "tb2",
            "question": "Another question?",
            "start_time": SEP6,
            "answer": "30",
        },
    }


@pytest.mark.parametrize("filter_key", ["overall", "week_1"])
@patch("main.get_sport_mode")
def test_football_blair_kyle_same_points_wins_rank(
    mock_mode, blair_kyle_users, mock_games, mock_tiebreakers, filter_key
):
    """Blair 7-1 / 7 pts / missed lock ranks above Kyle 6-2 / 7 pts / hit lock."""
    mock_mode.return_value = SportMode.FOOTBALL

    # Blair: 7 correct unlocks (7 pts, 7 wins) + 1 missed lock
    blair_picks = [_pick("blair", f"game{i}", 1, lock=False) for i in range(1, 8)]
    blair_picks.append(_pick("blair", "game8", 0, lock=True))

    # Kyle: 5 correct unlocks + 1 correct lock (7 pts, 6 wins) + 2 misses
    kyle_picks = [_pick("kyle", f"game{i}", 1, lock=False) for i in range(1, 6)]
    kyle_picks.append(_pick("kyle", "game6", 2, lock=True))
    kyle_picks.append(_pick("kyle", "game7", 0, lock=False))
    kyle_picks.append(_pick("kyle", "game8", 0, lock=False))

    # Kyle has the better numerical TB (would have ranked him first under PRD-03)
    all_tb_picks = [
        {"user_id": "blair", "tiebreaker_id": "tb1", "answer": "50", "points_awarded": 0, "start_time": SEP5},
        {"user_id": "kyle", "tiebreaker_id": "tb1", "answer": "45", "points_awarded": 0, "start_time": SEP5},
    ]

    leaderboard = _leaderboard_list_for_filter(
        blair_kyle_users, mock_games, mock_tiebreakers, blair_picks + kyle_picks, all_tb_picks, filter_key
    )
    by_uid = {row["uid"]: row for row in leaderboard}

    assert by_uid["blair"]["total_points"] == 7
    assert by_uid["kyle"]["total_points"] == 7
    assert by_uid["blair"]["total_wins"] == 7
    assert by_uid["kyle"]["total_wins"] == 6
    assert by_uid["blair"]["correct_locks"] == 0
    assert by_uid["kyle"]["correct_locks"] == 1
    assert leaderboard[0]["uid"] == "blair"
    assert leaderboard[1]["uid"] == "kyle"


@patch("main.get_sport_mode")
def test_football_higher_wins_rank_above_more_points_and_locks(
    mock_mode, mock_users, mock_games, mock_tiebreakers
):
    """More ATS wins rank first even when the other player has more points and locks."""
    mock_mode.return_value = SportMode.FOOTBALL

    # Charlie (later name) has 4 unlocks / 4 pts / 0 locks.
    # Alice has 3 correct locks / 6 pts / 3 locks — still ranks below.
    all_picks = [
        _pick("user3", "game1", 1),
        _pick("user3", "game2", 1, game_date=SEP6),
        _pick("user3", "game3", 1),
        _pick("user3", "game4", 1),
        _pick("user1", "game1", 2, lock=True),
        _pick("user1", "game2", 2, lock=True, game_date=SEP6),
        _pick("user1", "game3", 2, lock=True),
    ]

    leaderboard = _leaderboard_list_for_filter(
        mock_users, mock_games, mock_tiebreakers, all_picks, [], "overall"
    )

    assert leaderboard[0]["uid"] == "user3"
    assert leaderboard[0]["total_wins"] == 4
    assert leaderboard[0]["total_points"] == 4
    assert leaderboard[0]["correct_locks"] == 0
    assert leaderboard[1]["uid"] == "user1"
    assert leaderboard[1]["total_wins"] == 3
    assert leaderboard[1]["total_points"] == 6
    assert leaderboard[1]["correct_locks"] == 3


@patch("main.get_sport_mode")
def test_football_equal_wins_more_correct_locks_ranks_higher(
    mock_mode, mock_users, mock_games, mock_tiebreakers
):
    """Equal wins: more correct locks ranks higher (even if name would sort later)."""
    mock_mode.return_value = SportMode.FOOTBALL

    # Alice: 2 unlocks (2 wins, 0 locks). Charlie: 1 unlock + 1 correct lock (2 wins, 1 lock).
    all_picks = [
        _pick("user1", "game1", 1),
        _pick("user1", "game2", 1, game_date=SEP6),
        _pick("user3", "game1", 1),
        _pick("user3", "game2", 2, lock=True, game_date=SEP6),
    ]

    leaderboard = _leaderboard_list_for_filter(
        mock_users, mock_games, mock_tiebreakers, all_picks, [], "overall"
    )

    assert leaderboard[0]["uid"] == "user3"
    assert leaderboard[0]["total_wins"] == 2
    assert leaderboard[0]["correct_locks"] == 1
    assert leaderboard[1]["uid"] == "user1"
    assert leaderboard[1]["total_wins"] == 2
    assert leaderboard[1]["correct_locks"] == 0


@patch("main.get_sport_mode")
def test_football_equal_wins_and_locks_sort_by_name(
    mock_mode, mock_users, mock_games, mock_tiebreakers
):
    """Equal wins and locks: case-insensitive display_name ascending."""
    mock_mode.return_value = SportMode.FOOTBALL

    all_picks = [
        _pick("user3", "game1", 1),
        _pick("user1", "game1", 1),
    ]

    leaderboard = _leaderboard_list_for_filter(
        mock_users, mock_games, mock_tiebreakers, all_picks, [], "overall"
    )

    assert leaderboard[0]["display_name"] == "Alice"
    assert leaderboard[1]["display_name"] == "Charlie"


@patch("main.get_sport_mode")
def test_football_name_sort_is_case_insensitive(
    mock_mode, mock_games, mock_tiebreakers
):
    """Name fallback compares case-insensitively (alice before Bob)."""
    mock_mode.return_value = SportMode.FOOTBALL
    users = {
        "user_b": {"uid": "user_b", "display_name": "Bob", "make_picks": True},
        "user_a": {"uid": "user_a", "display_name": "alice", "make_picks": True},
    }
    all_picks = [
        _pick("user_b", "game1", 1),
        _pick("user_a", "game1", 1),
    ]

    leaderboard = _leaderboard_list_for_filter(
        users, mock_games, mock_tiebreakers, all_picks, [], "overall"
    )

    assert [row["display_name"] for row in leaderboard[:2]] == ["alice", "Bob"]


@patch("main.get_sport_mode")
def test_football_correct_lock_counts_as_one_win(
    mock_mode, mock_users, mock_games, mock_tiebreakers
):
    """A correct lock is one win (not two) even though it awards 2 points."""
    mock_mode.return_value = SportMode.FOOTBALL

    all_picks = [
        _pick("user1", "game1", 2, lock=True),
        _pick("user1", "game2", 1, game_date=SEP6),
    ]

    leaderboard = _leaderboard_list_for_filter(
        mock_users, mock_games, mock_tiebreakers, all_picks, [], "overall"
    )

    alice = next(row for row in leaderboard if row["uid"] == "user1")
    assert alice["total_wins"] == 2
    assert alice["total_points"] == 3
    assert alice["correct_locks"] == 1


@patch("main.get_sport_mode")
def test_football_push_incorrect_unsettled_are_not_wins(
    mock_mode, mock_users, mock_games, mock_tiebreakers
):
    """PUSH, misses, and unsettled picks (0 / None points) are not wins."""
    mock_mode.return_value = SportMode.FOOTBALL

    all_picks = [
        _pick("user1", "game1", 1),
        _pick("user1", "game2", 0, game_date=SEP6),  # miss or PUSH
        _pick("user1", "game3", None),  # unsettled
        _pick("user1", "game4", 0, lock=True),  # missed lock
    ]

    leaderboard = _leaderboard_list_for_filter(
        mock_users, mock_games, mock_tiebreakers, all_picks, [], "overall"
    )

    alice = next(row for row in leaderboard if row["uid"] == "user1")
    assert alice["total_wins"] == 1
    assert alice["total_points"] == 1
    assert alice["correct_locks"] == 0


@patch("main.get_sport_mode")
def test_football_tb_diff_not_used_for_sort(
    mock_mode, mock_users, mock_games, mock_tiebreakers
):
    """Same wins/locks: better TB does not outrank an earlier display_name."""
    mock_mode.return_value = SportMode.FOOTBALL

    all_picks = [
        _pick("user1", "game1", 1),
        _pick("user1", "game2", 1, game_date=SEP6),
        _pick("user2", "game1", 1),
        _pick("user2", "game2", 1, game_date=SEP6),
    ]
    all_tb_picks = [
        {"user_id": "user1", "tiebreaker_id": "tb1", "answer": "50", "points_awarded": 0, "start_time": SEP5},
        {"user_id": "user2", "tiebreaker_id": "tb1", "answer": "43", "points_awarded": 0, "start_time": SEP5},
    ]

    leaderboard = _leaderboard_list_for_filter(
        mock_users, mock_games, mock_tiebreakers, all_picks, all_tb_picks, "overall"
    )

    assert leaderboard[0]["uid"] == "user1"
    assert leaderboard[0]["first_tiebreaker_diff"] == 5.0
    assert leaderboard[1]["uid"] == "user2"
    assert leaderboard[1]["first_tiebreaker_diff"] == 2.0


@patch("main.get_sport_mode")
def test_football_tb_points_excluded(mock_mode, mock_users, mock_games, mock_tiebreakers):
    """TB points_awarded is not included in football total_points."""
    mock_mode.return_value = SportMode.FOOTBALL

    all_picks = [
        _pick("user1", "game1", 2, lock=True),
    ]
    all_tb_picks = [
        {"user_id": "user1", "tiebreaker_id": "tb1", "answer": "45", "points_awarded": 3, "start_time": SEP5},
    ]

    leaderboard = _leaderboard_list_for_filter(
        mock_users, mock_games, mock_tiebreakers, all_picks, all_tb_picks, "overall"
    )

    assert leaderboard[0]["total_points"] == 2
    assert leaderboard[0]["total_wins"] == 1


@patch("main.get_sport_mode")
def test_football_tb_diff_still_computed(mock_mode, mock_users, mock_games, mock_tiebreakers):
    """TB closeness is still stored on the row (display), using earliest TB."""
    mock_mode.return_value = SportMode.FOOTBALL

    all_picks = [
        _pick("user1", "game1", 1),
    ]
    all_tb_picks = [
        {"user_id": "user1", "tiebreaker_id": "tb1", "answer": "50", "points_awarded": 0, "start_time": SEP5},
        {"user_id": "user1", "tiebreaker_id": "tb2", "answer": "31", "points_awarded": 0, "start_time": SEP6},
    ]

    leaderboard = _leaderboard_list_for_filter(
        mock_users, mock_games, mock_tiebreakers, all_picks, all_tb_picks, "overall"
    )

    assert leaderboard[0]["uid"] == "user1"
    assert leaderboard[0]["first_tiebreaker_diff"] == 5.0


@patch("main.get_sport_mode")
def test_football_missing_tb_pick_gets_sentinel_diff(
    mock_mode, mock_users, mock_games, mock_tiebreakers
):
    """User with no TB pick still gets 999999 first_tiebreaker_diff for display."""
    mock_mode.return_value = SportMode.FOOTBALL

    all_picks = [
        _pick("user1", "game1", 1),
        _pick("user2", "game1", 1),
    ]
    all_tb_picks = [
        {"user_id": "user1", "tiebreaker_id": "tb1", "answer": "45", "points_awarded": 0, "start_time": SEP5},
    ]

    leaderboard = _leaderboard_list_for_filter(
        mock_users, mock_games, mock_tiebreakers, all_picks, all_tb_picks, "overall"
    )
    by_uid = {row["uid"]: row for row in leaderboard}

    assert by_uid["user1"]["first_tiebreaker_diff"] == 0.0
    assert by_uid["user2"]["first_tiebreaker_diff"] == 999999


@patch("main.get_sport_mode")
def test_march_madness_ranking_unchanged(mock_mode, mock_users, mock_games, mock_tiebreakers):
    """March Madness still uses 3 TBs and includes TB points; no total_wins field."""
    mock_mode.return_value = SportMode.MARCH_MADNESS

    all_picks = [
        _pick("user1", "game1", 1),
    ]
    all_tb_picks = [
        {"user_id": "user1", "tiebreaker_id": "tb1", "answer": "45", "points_awarded": 3, "start_time": SEP5},
    ]

    leaderboard = _leaderboard_list_for_filter(
        mock_users, mock_games, mock_tiebreakers, all_picks, all_tb_picks, "overall"
    )

    assert leaderboard[0]["total_points"] == 4  # 1 game + 3 TB
    assert "total_wins" not in leaderboard[0]
    assert leaderboard[0]["second_tiebreaker_diff"] == 999999
    assert leaderboard[0]["third_tiebreaker_diff"] == 999999


@patch("main.get_sport_mode")
def test_march_madness_period_sort_still_points_then_locks(
    mock_mode, mock_users, mock_games, mock_tiebreakers
):
    """MM non-overall: more points still beat more locks / better TB."""
    mock_mode.return_value = SportMode.MARCH_MADNESS

    # Dates are after Mar 24 2026 so they fall in second_half.
    all_picks = [
        _pick("user1", "game1", 1),
        _pick("user1", "game2", 1, game_date=SEP6),
        _pick("user1", "game3", 1),
        _pick("user2", "game1", 2, lock=True),
    ]
    all_tb_picks = [
        {"user_id": "user2", "tiebreaker_id": "tb1", "answer": "45", "points_awarded": 0, "start_time": SEP5},
    ]

    leaderboard = _leaderboard_list_for_filter(
        mock_users, mock_games, mock_tiebreakers, all_picks, all_tb_picks, "second_half"
    )

    assert leaderboard[0]["uid"] == "user1"
    assert leaderboard[0]["total_points"] == 3
    assert leaderboard[1]["uid"] == "user2"
    assert leaderboard[1]["total_points"] == 2
    assert leaderboard[1]["correct_locks"] == 1


@patch("main._release_leaderboard_build_lock")
@patch("main._compute_and_store_leaderboard_cache")
@patch("main._try_acquire_leaderboard_build_lock", return_value=True)
def test_stale_sort_version_rebuilds_cache(mock_lock, mock_compute, mock_release):
    """Cached ranks from the old points→TB→locks sort must not be served."""
    from unittest.mock import MagicMock

    from main import LEADERBOARD_SORT_VERSION, _get_leaderboard_response

    rebuilt = [{"uid": "blair", "total_wins": 7, "correct_locks": 0}]
    mock_compute.return_value = {"overall": rebuilt}

    db = MagicMock()
    cache_doc = MagicMock()
    db.collection.return_value.document.return_value = cache_doc
    snap = MagicMock()
    snap.exists = True
    snap.to_dict.return_value = {
        "overall": [{"uid": "kyle", "total_points": 7, "correct_locks": 1}],
        "sort_version": "prd03_points_tb_locks",
    }
    cache_doc.get.return_value = snap

    result = _get_leaderboard_response(db, "overall")

    assert result == rebuilt
    mock_compute.assert_called_once_with(db)
    assert LEADERBOARD_SORT_VERSION == "football_wins_locks_name_v1"


@patch("main._compute_and_store_leaderboard_cache")
def test_matching_sort_version_serves_cache(mock_compute):
    """Current sort_version cache is returned without a full rebuild."""
    from unittest.mock import MagicMock

    from main import LEADERBOARD_SORT_VERSION, _get_leaderboard_response

    cached_row = [{"uid": "blair", "total_wins": 7, "correct_locks": 0}]
    db = MagicMock()
    cache_doc = MagicMock()
    db.collection.return_value.document.return_value = cache_doc
    snap = MagicMock()
    snap.exists = True
    snap.to_dict.return_value = {
        "overall": cached_row,
        "sort_version": LEADERBOARD_SORT_VERSION,
    }
    cache_doc.get.return_value = snap

    result = _get_leaderboard_response(db, "overall")

    assert result == cached_row
    mock_compute.assert_not_called()
