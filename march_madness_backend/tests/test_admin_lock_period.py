"""
Admin lock-of-the-week/day status uses the period of games players are picking,
not only the calendar week/lock-day of `now`. Duplicate pick docs collapse
preferring lock=true then deterministic {uid}_{game_id}.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import patch

from auth import User
from main import (
    _collapse_picks_by_game_id,
    _compute_live_data,
    get_game_picks,
    get_picks_data,
    get_tiebreaker_picks_detail,
    get_user_all_picks,
    get_user_picks_status,
)
from sport_config import SportMode


PLAYER_UID = "u_player"
ADMIN_UID = "u_admin"
GAME_ID = "game_slate"


class FakeSnap:
    def __init__(self, id, data, exists=True):
        self.id = id
        self._data = dict(data) if data is not None else {}
        self.exists = exists

    def to_dict(self):
        return dict(self._data)


class FakeDocRef:
    def __init__(self, snap):
        self._snap = snap
        self.id = snap.id

    def get(self):
        return self._snap


class FakeQuery:
    def __init__(self, docs, db=None, name=None):
        self._docs = list(docs)
        self._db = db
        self._name = name

    def where(self, field, op, value):
        filtered = []
        for d in self._docs:
            data = d.to_dict()
            actual = data.get(field)
            if op == "==" and actual == value:
                filtered.append(d)
            elif op == "<=" and actual is not None and actual <= value:
                filtered.append(d)
            elif op == ">" and actual is not None and actual > value:
                filtered.append(d)
            elif op == "in" and actual in value:
                filtered.append(d)
        return FakeQuery(filtered, db=self._db, name=self._name)

    def stream(self):
        return list(self._docs)

    def document(self, doc_id):
        for d in self._docs:
            if d.id == doc_id:
                return FakeDocRef(d)
        missing = FakeSnap(doc_id, {}, exists=False)
        self._docs.append(missing)
        if self._db is not None and self._name is not None:
            self._db._collections.setdefault(self._name, []).append(missing)
        return FakeDocRef(missing)

    def order_by(self, *args, **kwargs):
        return self


class FakeDB:
    def __init__(self, collections):
        self._collections = {
            name: [d if isinstance(d, FakeSnap) else FakeSnap(d["id"], d) for d in docs]
            for name, docs in collections.items()
        }

    def collection(self, name):
        docs = self._collections.setdefault(name, [])
        return FakeQuery(docs, db=self, name=name)


def _user(uid, display_name, make_picks=True, admin=False):
    return {
        "uid": uid,
        "display_name": display_name,
        "email": f"{uid}@example.com",
        "make_picks": make_picks,
        "admin": admin,
        "hidden": False,
    }


def _game(gid, game_date, home="Home", away="Away"):
    return FakeSnap(gid, {
        "home_team": home,
        "away_team": away,
        "spread": 3.5,
        "game_date": game_date,
        "winning_team": "",
    })


def _pick(doc_id, uid, game_id, lock=False, picked_team="Home"):
    return FakeSnap(doc_id, {
        "user_id": uid,
        "game_id": game_id,
        "picked_team": picked_team,
        "lock": lock,
        "points_awarded": 0,
    })


def _admin():
    return User(
        uid=ADMIN_UID,
        email="admin@example.com",
        display_name="Admin",
        league_id="football_2026",
        make_picks=True,
        admin=True,
    )


def _player():
    return User(
        uid=PLAYER_UID,
        email=f"{PLAYER_UID}@example.com",
        display_name="Player One",
        league_id="football_2026",
        make_picks=True,
        admin=False,
    )


def _status_for(db, now, mode=SportMode.FOOTBALL):
    with patch("main.get_db", return_value=db), patch(
        "main.get_current_utc_time", return_value=now
    ), patch("main.get_sport_mode", return_value=mode):
        return asyncio.run(get_user_picks_status(_admin()))


def _player_row(result):
    rows = [r for r in result if r["uid"] == PLAYER_UID]
    assert len(rows) == 1
    return rows[0]


# Frozen Tuesday 2026-08-25 20:00 UTC: now's football week is Aug 19–26 ET.
TUESDAY_NOW = datetime(2026, 8, 25, 20, 0, tzinfo=timezone.utc)
# Friday of next week (season-start week beginning Wed Aug 26 ET)
NEXT_WEEK_GAME = datetime(2026, 8, 28, 23, 0, tzinfo=timezone.utc)
# Saturday of now's week (already started by Tuesday)
THIS_WEEK_PAST = datetime(2026, 8, 22, 20, 0, tzinfo=timezone.utc)


def test_tuesday_lock_on_upcoming_next_week_game_is_submitted():
    db = FakeDB({
        "users": [FakeSnap(PLAYER_UID, _user(PLAYER_UID, "Player One"))],
        "games": [_game(GAME_ID, NEXT_WEEK_GAME)],
        "picks": [_pick(f"{PLAYER_UID}_{GAME_ID}", PLAYER_UID, GAME_ID, lock=True)],
        "tiebreakers": [],
        "tiebreaker_picks": [],
    })
    row = _player_row(_status_for(db, TUESDAY_NOW))
    assert row["has_current_period_lock"] is True


def test_lock_on_other_week_with_no_upcoming_games_that_week_is_unsubmitted():
    db = FakeDB({
        "users": [FakeSnap(PLAYER_UID, _user(PLAYER_UID, "Player One"))],
        "games": [
            _game("game_past", THIS_WEEK_PAST),
            _game("game_upcoming", NEXT_WEEK_GAME),
        ],
        "picks": [_pick(f"{PLAYER_UID}_game_past", PLAYER_UID, "game_past", lock=True)],
        "tiebreakers": [],
        "tiebreaker_picks": [],
    })
    row = _player_row(_status_for(db, TUESDAY_NOW))
    assert row["has_current_period_lock"] is False


def test_lock_on_in_progress_game_same_week_as_upcoming_is_submitted():
    """Saturday now: Friday lock still counts because Sunday remains upcoming."""
    now = datetime(2026, 8, 29, 20, 0, tzinfo=timezone.utc)
    friday = datetime(2026, 8, 28, 23, 0, tzinfo=timezone.utc)
    sunday = datetime(2026, 8, 30, 20, 0, tzinfo=timezone.utc)
    db = FakeDB({
        "users": [FakeSnap(PLAYER_UID, _user(PLAYER_UID, "Player One"))],
        "games": [
            _game("game_fri", friday),
            _game("game_sun", sunday),
        ],
        "picks": [_pick(f"{PLAYER_UID}_game_fri", PLAYER_UID, "game_fri", lock=True)],
        "tiebreakers": [],
        "tiebreaker_picks": [],
    })
    row = _player_row(_status_for(db, now))
    assert row["has_current_period_lock"] is True


def test_mm_lock_on_tomorrow_while_now_is_previous_lock_day():
    """2 AM ET Mar 19 is still Mar 18 lock-day; tomorrow's game is the next lock-day."""
    now = datetime(2026, 3, 19, 6, 0, tzinfo=timezone.utc)
    tomorrow = datetime(2026, 3, 20, 0, 0, tzinfo=timezone.utc)
    db = FakeDB({
        "users": [FakeSnap(PLAYER_UID, _user(PLAYER_UID, "Player One"))],
        "games": [_game(GAME_ID, tomorrow)],
        "picks": [_pick(f"{PLAYER_UID}_{GAME_ID}", PLAYER_UID, GAME_ID, lock=True)],
        "tiebreakers": [],
        "tiebreaker_picks": [],
    })
    row = _player_row(_status_for(db, now, mode=SportMode.MARCH_MADNESS))
    assert row["has_current_period_lock"] is True


def test_no_upcoming_games_falls_back_to_now_week():
    db = FakeDB({
        "users": [FakeSnap(PLAYER_UID, _user(PLAYER_UID, "Player One"))],
        "games": [_game("game_past", THIS_WEEK_PAST)],
        "picks": [_pick(f"{PLAYER_UID}_game_past", PLAYER_UID, "game_past", lock=True)],
        "tiebreakers": [],
        "tiebreaker_picks": [],
    })
    row = _player_row(_status_for(db, TUESDAY_NOW))
    assert row["has_current_period_lock"] is True


def test_collapse_prefers_lock_true_over_later_unlocked_legacy():
    gid = GAME_ID
    snaps = [
        _pick(f"{PLAYER_UID}_{gid}", PLAYER_UID, gid, lock=True, picked_team="Home"),
        _pick("legacy_random_id", PLAYER_UID, gid, lock=False, picked_team="Away"),
    ]
    collapsed = _collapse_picks_by_game_id(snaps)
    assert collapsed[gid]["lock"] is True
    assert collapsed[gid]["id"] == f"{PLAYER_UID}_{gid}"


def test_collapse_prefers_deterministic_id_when_neither_locked():
    gid = GAME_ID
    snaps = [
        _pick("legacy_random_id", PLAYER_UID, gid, lock=False, picked_team="Away"),
        _pick(f"{PLAYER_UID}_{gid}", PLAYER_UID, gid, lock=False, picked_team="Home"),
    ]
    collapsed = _collapse_picks_by_game_id(snaps)
    assert collapsed[gid]["id"] == f"{PLAYER_UID}_{gid}"
    assert collapsed[gid]["picked_team"] == "Home"


def test_picks_data_and_user_all_picks_expose_lock_when_legacy_unlocked_duplicate():
    gid = GAME_ID
    # Unlocked legacy last in stream so last-write-wins would hide lock=true.
    picks = [
        _pick(f"{PLAYER_UID}_{gid}", PLAYER_UID, gid, lock=True, picked_team="Home"),
        _pick("legacy_random_id", PLAYER_UID, gid, lock=False, picked_team="Away"),
    ]
    db = FakeDB({
        "users": [FakeSnap(PLAYER_UID, _user(PLAYER_UID, "Player One"))],
        "games": [_game(gid, NEXT_WEEK_GAME)],
        "picks": picks,
        "tiebreakers": [],
        "tiebreaker_picks": [],
    })

    with patch("main.get_db", return_value=db), patch(
        "main.get_current_utc_time", return_value=TUESDAY_NOW
    ):
        picks_data = asyncio.run(get_picks_data(_player()))
        all_picks = asyncio.run(get_user_all_picks(PLAYER_UID, _admin()))

    assert len(picks_data["games"]) == 1
    assert picks_data["games"][0]["lock"] is True
    assert picks_data["games"][0]["picked_team"] == "Home"

    assert len(all_picks["game_picks"]) == 1
    assert all_picks["game_picks"][0]["lock"] is True
    assert all_picks["game_picks"][0]["picked_team"] == "Home"


OTHER_UID = "u_other"


def _live_duplicate_db():
    """Started live game: player has legacy unlocked + deterministic locked; other user has one pick."""
    gid = GAME_ID
    return FakeDB({
        "users": [
            FakeSnap(PLAYER_UID, _user(PLAYER_UID, "Player One")),
            FakeSnap(OTHER_UID, _user(OTHER_UID, "Player Two")),
        ],
        "games": [_game(gid, THIS_WEEK_PAST)],
        "picks": [
            _pick(f"{PLAYER_UID}_{gid}", PLAYER_UID, gid, lock=True, picked_team="Home"),
            _pick("legacy_random_id", PLAYER_UID, gid, lock=False, picked_team="Away"),
            _pick(f"{OTHER_UID}_{gid}", OTHER_UID, gid, lock=False, picked_team="Away"),
        ],
        "tiebreakers": [],
        "tiebreaker_picks": [],
    })


def test_live_counts_once_and_uses_locked_doc_when_duplicate_picks():
    db = _live_duplicate_db()
    with patch("main.get_current_utc_time", return_value=TUESDAY_NOW):
        live_games, _tbs = _compute_live_data(db)
    assert len(live_games) == 1
    row = live_games[0]
    assert row["total_picks"] == 2
    assert row["home_picks"] == 1
    assert row["away_picks"] == 1


def test_live_game_picks_names_use_locked_doc():
    db = _live_duplicate_db()
    with patch("main.get_db", return_value=db), patch(
        "main.get_current_utc_time", return_value=TUESDAY_NOW
    ):
        names = get_game_picks(GAME_ID)
    by_uid = {row["uid"]: row for row in names}
    assert set(by_uid) == {PLAYER_UID, OTHER_UID}
    assert by_uid[PLAYER_UID]["lock"] is True
    assert by_uid[PLAYER_UID]["picked_team"] == "Home"
    assert by_uid[OTHER_UID]["lock"] is False
    assert by_uid[OTHER_UID]["picked_team"] == "Away"


def test_live_tiebreaker_counts_and_names_collapse_duplicate_user_docs():
    tb_id = "tb1"
    started = datetime(2026, 8, 25, 18, 0, tzinfo=timezone.utc)
    db = FakeDB({
        "users": [FakeSnap(PLAYER_UID, _user(PLAYER_UID, "Player One"))],
        "games": [],
        "picks": [],
        "tiebreakers": [FakeSnap(tb_id, {
            "question": "Total points?",
            "start_time": started,
            "is_active": True,
            "answer": "",
        })],
        "tiebreaker_picks": [
            FakeSnap(f"{PLAYER_UID}_{tb_id}", {
                "user_id": PLAYER_UID,
                "tiebreaker_id": tb_id,
                "answer": "42",
            }),
            FakeSnap("legacy_tb_id", {
                "user_id": PLAYER_UID,
                "tiebreaker_id": tb_id,
                "answer": "7",
            }),
        ],
    })
    with patch("main.get_current_utc_time", return_value=TUESDAY_NOW):
        _games, live_tbs = _compute_live_data(db)
    assert len(live_tbs) == 1
    assert live_tbs[0]["total_picks"] == 1

    with patch("main.get_db", return_value=db), patch(
        "main.get_current_utc_time", return_value=TUESDAY_NOW
    ):
        names = get_tiebreaker_picks_detail(tb_id)
    assert len(names) == 1
    assert names[0]["uid"] == PLAYER_UID
    assert names[0]["answer"] == "42"
