"""
PRD-10: admin flags + hidden users.

Hidden users keep make_picks True (can submit / stay admin) but are omitted
from leaderboard, stats, live lists/counts, admin user lists, and consensus.
By-uid GET routes 404 (not 403) when the target is not listed.
"""

import asyncio
import sys
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from auth import User
from main import (
    AUTO_HIDE_NEW_USERS_THROUGH,
    _compute_and_store_leaderboard_cache,
    _compute_live_data,
    _compute_player_stats_list,
    _consensus_counts_for_listed_users,
    _require_listed_user,
    get_current_admin_user,
    get_current_user,
    get_game_picks,
    get_player_detailed_stats,
    get_user_picks,
    get_user_picks_status,
    new_user_should_auto_hide,
    user_is_listed,
)


HIDDEN_UID = "u_hidden"
JARED_UID = "u_jared"
PLAYER_UID = "u_player"


def _user(uid, display_name, make_picks=True, hidden=None, admin=False, created_at=None):
    data = {
        "uid": uid,
        "display_name": display_name,
        "email": f"{uid}@example.com",
        "make_picks": make_picks,
        "admin": admin,
    }
    if hidden is not None:
        data["hidden"] = hidden
    if created_at is not None:
        data["created_at"] = created_at
    return data


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

    def set(self, data):
        self._snap._data = dict(data)
        self._snap.exists = True

    def update(self, data):
        self._snap._data.update(data)

    def delete(self):
        self._snap.exists = False
        self._snap._data = {}


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


def _standard_users():
    return [
        FakeSnap(HIDDEN_UID, _user(HIDDEN_UID, "Hidden Admin", hidden=True, admin=True)),
        FakeSnap(JARED_UID, _user(JARED_UID, "Visible Admin", hidden=False, admin=True)),
        FakeSnap(PLAYER_UID, _user(PLAYER_UID, "Player One")),
        FakeSnap("u_spectator", _user("u_spectator", "Spectator", make_picks=False)),
        FakeSnap("u_missing_hidden", _user("u_missing_hidden", "No Hidden Field")),
    ]


# ---------------------------------------------------------------------------
# user_is_listed table
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "u,expected",
        [
            ({"make_picks": True}, True),
            ({"uid": "u_player"}, True),
            ({"make_picks": True, "hidden": False}, True),
            ({"make_picks": True, "hidden": True}, False),
            ({"hidden": True}, False),
            ({"make_picks": False}, False),
            ({"make_picks": False, "hidden": False}, False),
            ({"make_picks": False, "hidden": True}, False),
            (None, False),
            ({}, False),
        ],
)
def test_user_is_listed_table(u, expected):
    assert user_is_listed(u) is expected


def test_user_is_listed_missing_hidden_is_listed():
    assert user_is_listed({"make_picks": True}) is True
    assert user_is_listed({"uid": PLAYER_UID}) is True


# ---------------------------------------------------------------------------
# Leaderboard / stats / admin lists
# ---------------------------------------------------------------------------

@patch("main.server_timestamp", return_value="ts")
def test_leaderboard_omits_hidden_includes_visible_admin(_ts):
    db = FakeDB({
        "users": _standard_users(),
        "games": [],
        "picks": [],
        "tiebreakers": [],
        "tiebreaker_picks": [],
        "_cache": [],
    })
    cached = _compute_and_store_leaderboard_cache(db)
    overall = cached["overall"]
    uids = {row["uid"] for row in overall}
    assert HIDDEN_UID not in uids
    assert JARED_UID in uids
    assert PLAYER_UID in uids
    assert "u_spectator" not in uids
    assert "u_missing_hidden" in uids


@patch("main.server_timestamp", return_value="ts")
def test_leaderboard_legacy_cutoff_unchanged(_ts):
    legacy = FakeSnap(
        "u_legacy",
        _user("u_legacy", "Legacy", created_at=datetime(2025, 5, 31, tzinfo=timezone.utc)),
    )
    listed = FakeSnap(
        PLAYER_UID,
        _user(PLAYER_UID, "Player One", created_at=datetime(2025, 6, 1, tzinfo=timezone.utc)),
    )
    db = FakeDB({
        "users": [legacy, listed],
        "games": [],
        "picks": [],
        "tiebreakers": [],
        "tiebreaker_picks": [],
        "_cache": [],
    })
    cached = _compute_and_store_leaderboard_cache(db)
    uids = {row["uid"] for row in cached["overall"]}
    assert "u_legacy" not in uids
    assert PLAYER_UID in uids


def test_stats_list_omits_hidden_includes_visible_admin():
    db = FakeDB({
        "users": _standard_users(),
        "games": [],
        "picks": [],
    })
    rows = _compute_player_stats_list(db)
    uids = {row["uid"] for row in rows}
    assert HIDDEN_UID not in uids
    assert JARED_UID in uids
    assert PLAYER_UID in uids
    assert "u_spectator" not in uids
    assert "u_missing_hidden" in uids


def test_admin_user_picks_status_omits_hidden_includes_visible_admin():
    db = FakeDB({
        "users": _standard_users(),
        "games": [],
        "picks": [],
        "tiebreakers": [],
        "tiebreaker_picks": [],
    })
    admin = User(
        uid="admin",
        email="admin@example.com",
        display_name="Caller",
        league_id="football_2026",
        make_picks=True,
        admin=True,
        hidden=True,
    )
    with patch("main.get_db", return_value=db):
        result = asyncio.run(get_user_picks_status(admin))
    uids = {row["uid"] for row in result}
    assert HIDDEN_UID not in uids
    assert JARED_UID in uids
    assert PLAYER_UID in uids
    assert "u_spectator" not in uids
    emails = {row["email"] for row in result}
    assert f"{HIDDEN_UID}@example.com" not in emails
    assert f"{JARED_UID}@example.com" in emails


# ---------------------------------------------------------------------------
# Live names + counts
# ---------------------------------------------------------------------------

def test_live_names_and_counts_omit_hidden():
    now = datetime.now(timezone.utc)
    past = now - timedelta(hours=2)
    game = FakeSnap("game1", {
        "home_team": "Home",
        "away_team": "Away",
        "spread": 3.5,
        "game_date": past,
        "winning_team": "",
    })
    picks = [
        FakeSnap("p1", {"user_id": PLAYER_UID, "game_id": "game1", "picked_team": "Home"}),
        FakeSnap("p2", {"user_id": HIDDEN_UID, "game_id": "game1", "picked_team": "Home"}),
        FakeSnap("p3", {"user_id": JARED_UID, "game_id": "game1", "picked_team": "Away"}),
    ]
    db = FakeDB({
        "users": _standard_users(),
        "games": [game],
        "picks": picks,
        "tiebreakers": [],
        "tiebreaker_picks": [],
    })
    live_games, _tbs = _compute_live_data(db)
    assert len(live_games) == 1
    row = live_games[0]
    assert row["total_picks"] == 2
    assert row["home_picks"] == 1
    assert row["away_picks"] == 1

    with patch("main.get_db", return_value=db), patch(
        "main.get_current_utc_time", return_value=now
    ):
        names = get_game_picks("game1")
    name_uids = {n["uid"] for n in names}
    assert HIDDEN_UID not in name_uids
    assert PLAYER_UID in name_uids
    assert JARED_UID in name_uids


# ---------------------------------------------------------------------------
# By-uid 404
# ---------------------------------------------------------------------------

def test_stats_and_user_picks_hidden_404():
    db = FakeDB({"users": _standard_users()})
    with patch("main.get_db", return_value=db):
        with pytest.raises(HTTPException) as stats_exc:
            get_player_detailed_stats(HIDDEN_UID)
        with pytest.raises(HTTPException) as picks_exc:
            get_user_picks(HIDDEN_UID)
    assert stats_exc.value.status_code == 404
    assert stats_exc.value.detail == "User not found"
    assert picks_exc.value.status_code == 404
    assert picks_exc.value.detail == "User not found"


def test_require_listed_user_spectator_and_missing():
    db = FakeDB({"users": _standard_users()})
    with pytest.raises(HTTPException) as spec:
        _require_listed_user(db, "u_spectator")
    assert spec.value.status_code == 404
    with pytest.raises(HTTPException) as missing:
        _require_listed_user(db, "does-not-exist")
    assert missing.value.status_code == 404
    assert _require_listed_user(db, JARED_UID)["uid"] == JARED_UID
    assert _require_listed_user(db, "u_missing_hidden")["uid"] == "u_missing_hidden"


# ---------------------------------------------------------------------------
# Consensus
# ---------------------------------------------------------------------------

def test_consensus_excludes_hidden_users():
    picks = [
        {"user_id": PLAYER_UID, "game_id": "g1", "picked_team": "Home"},
        {"user_id": JARED_UID, "game_id": "g1", "picked_team": "Home"},
        {"user_id": HIDDEN_UID, "game_id": "g1", "picked_team": "Home"},
        {"user_id": PLAYER_UID, "game_id": "g1", "picked_team": "Away"},
    ]
    listed = {PLAYER_UID, JARED_UID}
    counts = _consensus_counts_for_listed_users(picks, listed)
    assert counts[("g1", "Home")] == 2
    assert counts[("g1", "Away")] == 1
    assert HIDDEN_UID not in listed


# ---------------------------------------------------------------------------
# Hidden users can still pick and stay admin
# ---------------------------------------------------------------------------

def test_hidden_user_passes_submit_make_picks_check():
    current_user = User(
        uid=HIDDEN_UID,
        email="hidden@example.com",
        display_name="Hidden Admin",
        league_id="football_2026",
        make_picks=True,
        hidden=True,
        admin=True,
    )
    # submit_pick / tiebreaker_picks: if not current_user.make_picks: 403
    assert current_user.make_picks is True
    assert (not current_user.make_picks) is False


def test_hidden_admin_still_admin():
    user = User(
        uid=HIDDEN_UID,
        email="hidden@example.com",
        display_name="Hidden Admin",
        league_id="football_2026",
        make_picks=True,
        hidden=True,
        admin=True,
    )
    result = asyncio.run(get_current_admin_user(user))
    assert result.admin is True
    assert result.hidden is True


def test_non_admin_hidden_is_not_admin():
    user = User(
        uid=HIDDEN_UID,
        email="hidden@example.com",
        display_name="Hidden Admin",
        league_id="football_2026",
        make_picks=True,
        hidden=True,
        admin=False,
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_current_admin_user(user))
    assert exc.value.status_code == 403


def test_users_me_may_include_hidden():
    user = User(
        uid=HIDDEN_UID,
        email="hidden@example.com",
        display_name="Hidden Admin",
        league_id="football_2026",
        make_picks=True,
        hidden=True,
        admin=True,
    )
    payload = user.dict()
    assert payload["hidden"] is True
    assert payload["admin"] is True
    assert payload["make_picks"] is True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(scripts_dir))
import make_admin  # noqa: E402


def test_cli_parse_legacy_positional_sets_admin():
    args = make_admin.parse_args([HIDDEN_UID])
    assert args.uid == HIDDEN_UID
    assert args.name is None
    assert args.admin is True
    assert args.hidden is None


def test_cli_parse_requires_a_flag():
    with pytest.raises(SystemExit):
        make_admin.parse_args(["--uid", HIDDEN_UID])


def test_cli_parse_uid_and_name_conflict():
    with pytest.raises(SystemExit):
        make_admin.parse_args(["--uid", HIDDEN_UID, "--name", "Hidden Admin", "--admin"])


def test_cli_name_case_insensitive_updates_and_invalidates(capsys):
    users = [
        FakeSnap(HIDDEN_UID, _user(HIDDEN_UID, "Hidden Admin", admin=False)),
        FakeSnap(JARED_UID, _user(JARED_UID, "Visible Admin", admin=False)),
    ]
    db = FakeDB({"users": users})

    with patch.object(make_admin, "_init", return_value=db), patch.object(
        make_admin, "invalidate_list_caches"
    ) as inv:
        make_admin.main(["--name", "hidden admin", "--admin", "--hidden"])

    inv.assert_called_once_with(db)
    updated = users[0]._data
    assert updated["admin"] is True
    assert updated["hidden"] is True
    assert users[1]._data.get("admin") is False
    out = capsys.readouterr().out
    assert f"SUCCESS: Hidden Admin ({HIDDEN_UID}) admin=True hidden=True" in out
    assert "@example.com" not in out


def test_cli_name_zero_matches_exits():
    db = FakeDB({"users": [FakeSnap(PLAYER_UID, _user(PLAYER_UID, "Player One"))]})
    with pytest.raises(SystemExit) as exc:
        make_admin.resolve_user(db, name="Nobody")
    assert exc.value.code == 1


def test_cli_name_multiple_matches_prints_uids(capsys):
    db = FakeDB({
        "users": [
            FakeSnap("uid_a", _user("uid_a", "Same Name")),
            FakeSnap("uid_b", _user("uid_b", "same name")),
        ]
    })
    with pytest.raises(SystemExit) as exc:
        make_admin.resolve_user(db, name="Same Name")
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "uid_a" in out
    assert "uid_b" in out
    assert "Use --uid" in out


def test_cli_invalidate_reuses_leaderboard_stats_live_helpers():
    db = MagicMock()
    with patch("main.invalidate_leaderboard_and_stats") as inv:
        make_admin.invalidate_list_caches(db)
    inv.assert_called_once_with(db)


# ---------------------------------------------------------------------------
# PRD-13: auto-hide new users through 2026-12-31 ET
# ---------------------------------------------------------------------------

ET = ZoneInfo("America/New_York")
NEW_UID = "u_new_signup"


def _run_get_current_user(db, uid=NEW_UID, email="new@example.com", name="New User"):
    auth = MagicMock()
    auth.verify_id_token.return_value = {"uid": uid, "email": email, "name": name}
    with patch("main.get_auth", return_value=auth), patch(
        "main.get_db", return_value=db
    ), patch("main.invalidate_leaderboard_and_stats") as inv, patch(
        "main.server_timestamp", return_value="ts"
    ):
        user = asyncio.run(get_current_user(authorization="Bearer fake-token"))
    return user, inv


def test_auto_hide_constant_is_end_of_2026():
    assert AUTO_HIDE_NEW_USERS_THROUGH == date(2026, 12, 31)


def test_new_user_should_auto_hide_true_last_moment_of_window():
    now = datetime(2026, 12, 31, 23, 30, tzinfo=ET)
    assert new_user_should_auto_hide(now) is True
    now_eod = datetime(2026, 12, 31, 23, 59, 59, tzinfo=ET)
    assert new_user_should_auto_hide(now_eod) is True


def test_new_user_should_auto_hide_false_at_et_new_year():
    now = datetime(2027, 1, 1, 0, 0, tzinfo=ET)
    assert new_user_should_auto_hide(now) is False


def test_new_user_should_auto_hide_uses_et_date_not_utc():
    # 2027-01-01 00:30 UTC is still 2026-12-31 19:30 ET.
    still_in_window = datetime(2027, 1, 1, 0, 30, tzinfo=timezone.utc)
    assert new_user_should_auto_hide(still_in_window) is True
    # 2027-01-01 05:00 UTC is 2027-01-01 00:00 ET (EST).
    after_window = datetime(2027, 1, 1, 5, 0, tzinfo=timezone.utc)
    assert new_user_should_auto_hide(after_window) is False


def test_new_user_should_auto_hide_true_inside_window():
    now = datetime(2026, 9, 9, 12, 0, tzinfo=ET)
    assert new_user_should_auto_hide(now) is True


def test_create_user_auto_hides_when_helper_true():
    db = FakeDB({"users": []})
    with patch("main.new_user_should_auto_hide", return_value=True):
        user, inv = _run_get_current_user(db)

    stored = db.collection("users").document(NEW_UID).get().to_dict()
    assert stored["hidden"] is True
    assert stored["make_picks"] is True
    assert stored["admin"] is False
    assert user.hidden is True
    assert user.make_picks is True
    inv.assert_called_once()


def test_create_user_explicit_hidden_false_after_window():
    db = FakeDB({"users": []})
    with patch("main.new_user_should_auto_hide", return_value=False):
        user, inv = _run_get_current_user(db)

    stored = db.collection("users").document(NEW_UID).get().to_dict()
    assert "hidden" in stored
    assert stored["hidden"] is False
    assert stored["make_picks"] is True
    assert user.hidden is False
    inv.assert_called_once()


def test_existing_visible_user_login_does_not_touch_hidden():
    existing = _user(PLAYER_UID, "Player One", hidden=False)
    original = dict(existing)
    db = FakeDB({"users": [FakeSnap(PLAYER_UID, existing)]})
    user, inv = _run_get_current_user(
        db, uid=PLAYER_UID, email=f"{PLAYER_UID}@example.com", name="Player One"
    )
    stored = db.collection("users").document(PLAYER_UID).get().to_dict()
    assert stored["hidden"] is False
    assert stored == original
    assert user.hidden is False
    inv.assert_not_called()


def test_existing_hidden_user_login_stays_hidden():
    existing = _user(HIDDEN_UID, "Hidden Admin", hidden=True, admin=True)
    original = dict(existing)
    db = FakeDB({"users": [FakeSnap(HIDDEN_UID, existing)]})
    user, inv = _run_get_current_user(
        db, uid=HIDDEN_UID, email=f"{HIDDEN_UID}@example.com", name="Hidden Admin"
    )
    stored = db.collection("users").document(HIDDEN_UID).get().to_dict()
    assert stored["hidden"] is True
    assert stored == original
    assert user.hidden is True
    inv.assert_not_called()


def test_existing_user_missing_hidden_field_unchanged_on_login():
    existing = _user("u_missing_hidden", "No Hidden Field")
    assert "hidden" not in existing
    original = dict(existing)
    db = FakeDB({"users": [FakeSnap("u_missing_hidden", existing)]})
    user, inv = _run_get_current_user(
        db,
        uid="u_missing_hidden",
        email="u_missing_hidden@example.com",
        name="No Hidden Field",
    )
    stored = db.collection("users").document("u_missing_hidden").get().to_dict()
    assert "hidden" not in stored
    assert stored == original
    assert user.hidden is False
    inv.assert_not_called()
