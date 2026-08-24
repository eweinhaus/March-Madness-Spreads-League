"""
PRD-08 Tests: Lock Swap Integrity (Tip-Lock + Unlock-All).

Mocks the body of `_atomic_lock_swap_and_update` (via `.to_wrap`), not the
decorator alone. One smoke test keeps the @transactional assertion.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from main import SportMode, _atomic_lock_swap_and_update


# Same football week (Wed 2026-09-09 00:00 ET → Wed 2026-09-16 00:00 ET)
CURRENT_TIME = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
GAME_A_DATE = datetime(2026, 9, 10, 20, 0, 0, tzinfo=timezone.utc)
GAME_B_DATE = datetime(2026, 9, 12, 19, 0, 0, tzinfo=timezone.utc)
GAME_C_DATE = datetime(2026, 9, 15, 17, 0, 0, tzinfo=timezone.utc)


def _inner_lock_swap():
    """Call the transactional function body, not the decorator wrapper."""
    return _atomic_lock_swap_and_update.to_wrap


def _snap(doc_id, data, exists=True):
    snap = MagicMock()
    snap.id = doc_id
    snap.exists = exists
    snap.to_dict.return_value = dict(data)
    return snap


def _ref(kind, doc_id):
    ref = MagicMock()
    ref._kind = kind
    ref._id = doc_id
    return ref


def _build_db_and_txn(existing_locks, game_dates, target_pick_exists=False, target_pick_data=None):
    """
    existing_locks: list of (pick_id, {user_id, game_id, lock})
    game_dates: {game_id: datetime} for lock game reads
    """
    db = MagicMock()
    transaction = MagicMock()

    lock_snaps = [_snap(pid, data) for pid, data in existing_locks]

    picks_coll = MagicMock()
    query = MagicMock()
    query.stream.return_value = lock_snaps
    picks_coll.where.return_value.where.return_value = query

    def picks_document(doc_id):
        return _ref("pick", doc_id)

    picks_coll.document.side_effect = picks_document

    games_coll = MagicMock()

    def games_document(game_id):
        return _ref("game", game_id)

    games_coll.document.side_effect = games_document

    def collection(name):
        if name == "picks":
            return picks_coll
        if name == "games":
            return games_coll
        raise AssertionError(f"unexpected collection {name}")

    db.collection.side_effect = collection

    def txn_get(ref):
        kind = getattr(ref, "_kind", None)
        if kind == "game":
            game_id = ref._id
            if game_id in game_dates:
                return _snap(game_id, {"game_date": game_dates[game_id]})
            missing = MagicMock()
            missing.exists = False
            return missing
        if kind == "pick":
            if target_pick_exists:
                return _snap(ref._id, target_pick_data or {})
            return _snap(ref._id, {}, exists=False)
        raise AssertionError(f"unexpected get ref {ref}")

    transaction.get.side_effect = txn_get
    return db, transaction


def _write_ids(transaction):
    unlocked = []
    for args, _kwargs in transaction.update.call_args_list:
        ref, data = args[0], args[1]
        if data == {"lock": False}:
            unlocked.append(ref._id)
    target_updates = []
    for args, _kwargs in transaction.update.call_args_list:
        ref, data = args[0], args[1]
        if data.get("lock") is True:
            target_updates.append((ref._id, data))
    sets = []
    for args, _kwargs in transaction.set.call_args_list:
        ref, data = args[0], args[1]
        sets.append((ref._id, data))
    return unlocked, target_updates, sets


def _run(**kwargs):
    return _inner_lock_swap()(**kwargs)


class TestUnlockAllSamePeriodLocks:
    def test_single_same_week_lock_unlocked_and_target_set(self):
        """Existing lock A same week as B → A lock=False and B lock=True (set)."""
        db, transaction = _build_db_and_txn(
            existing_locks=[("pick_a_id", {"user_id": "user123", "game_id": "game_a", "lock": True})],
            game_dates={"game_a": GAME_A_DATE},
        )

        _run(
            transaction=transaction,
            db=db,
            user_id="user123",
            pick_id="user123_game_b",
            game_id="game_b",
            game_date=GAME_B_DATE,
            picked_team="Team B",
            mode=SportMode.FOOTBALL,
            current_time=CURRENT_TIME,
            points_awarded=0,
        )

        unlocked, target_updates, sets = _write_ids(transaction)
        assert unlocked == ["pick_a_id"]
        assert target_updates == []
        assert len(sets) == 1
        assert sets[0][0] == "user123_game_b"
        assert sets[0][1]["lock"] is True
        assert sets[0][1]["game_id"] == "game_b"
        assert sets[0][1]["picked_team"] == "Team B"

    def test_single_same_week_lock_unlocked_and_existing_target_updated(self):
        """Existing lock A same week as existing pick B → A unlocked, B updated lock=True."""
        db, transaction = _build_db_and_txn(
            existing_locks=[("pick_a_id", {"user_id": "user123", "game_id": "game_a", "lock": True})],
            game_dates={"game_a": GAME_A_DATE},
            target_pick_exists=True,
            target_pick_data={"user_id": "user123", "game_id": "game_b", "picked_team": "Old", "lock": False},
        )

        _run(
            transaction=transaction,
            db=db,
            user_id="user123",
            pick_id="user123_game_b",
            game_id="game_b",
            game_date=GAME_B_DATE,
            picked_team="Team B",
            mode=SportMode.FOOTBALL,
            current_time=CURRENT_TIME,
            points_awarded=0,
        )

        unlocked, target_updates, sets = _write_ids(transaction)
        assert unlocked == ["pick_a_id"]
        assert sets == []
        assert len(target_updates) == 1
        assert target_updates[0][0] == "user123_game_b"
        assert target_updates[0][1] == {"picked_team": "Team B", "lock": True}

    def test_multiple_same_week_locks_all_unlocked(self):
        """Locks A and C same week; lock B → both A and C unlocked, B locked."""
        db, transaction = _build_db_and_txn(
            existing_locks=[
                ("pick_a_id", {"user_id": "user123", "game_id": "game_a", "lock": True}),
                ("pick_c_id", {"user_id": "user123", "game_id": "game_c", "lock": True}),
            ],
            game_dates={"game_a": GAME_A_DATE, "game_c": GAME_C_DATE},
        )

        _run(
            transaction=transaction,
            db=db,
            user_id="user123",
            pick_id="user123_game_b",
            game_id="game_b",
            game_date=GAME_B_DATE,
            picked_team="Team B",
            mode=SportMode.FOOTBALL,
            current_time=CURRENT_TIME,
            points_awarded=0,
        )

        unlocked, target_updates, sets = _write_ids(transaction)
        assert unlocked == ["pick_a_id", "pick_c_id"]
        assert target_updates == []
        assert len(sets) == 1
        assert sets[0][0] == "user123_game_b"
        assert sets[0][1]["lock"] is True

    def test_skips_self_and_locks_missing_game_date(self):
        """Do not unlock the target itself; skip locks whose game_date is missing."""
        db, transaction = _build_db_and_txn(
            existing_locks=[
                ("user123_game_b", {"user_id": "user123", "game_id": "game_b", "lock": True}),
                ("pick_missing", {"user_id": "user123", "game_id": "game_missing", "lock": True}),
                ("pick_a_id", {"user_id": "user123", "game_id": "game_a", "lock": True}),
            ],
            game_dates={"game_a": GAME_A_DATE},
            target_pick_exists=True,
            target_pick_data={"user_id": "user123", "game_id": "game_b", "lock": True},
        )

        _run(
            transaction=transaction,
            db=db,
            user_id="user123",
            pick_id="user123_game_b",
            game_id="game_b",
            game_date=GAME_B_DATE,
            picked_team="Team B",
            mode=SportMode.FOOTBALL,
            current_time=CURRENT_TIME,
            points_awarded=0,
        )

        unlocked, target_updates, sets = _write_ids(transaction)
        assert unlocked == ["pick_a_id"]
        assert "user123_game_b" not in unlocked
        assert "pick_missing" not in unlocked
        assert sets == []
        assert len(target_updates) == 1
        assert target_updates[0][1]["lock"] is True


class TestTargetGameTipLocked:
    def test_target_tip_locked_raises_400_no_writes(self):
        """Target B tip-locked → no update/set; HTTPException 400."""
        db, transaction = _build_db_and_txn(
            existing_locks=[("pick_a_id", {"user_id": "user123", "game_id": "game_a", "lock": True})],
            game_dates={"game_a": GAME_A_DATE},
        )
        # Tip is 30 seconds after current_time → already within 1-minute lock window
        tip_locked_target = datetime(2026, 9, 10, 12, 0, 30, tzinfo=timezone.utc)

        with pytest.raises(HTTPException) as exc_info:
            _run(
                transaction=transaction,
                db=db,
                user_id="user123",
                pick_id="user123_game_b",
                game_id="game_b",
                game_date=tip_locked_target,
                picked_team="Team B",
                mode=SportMode.FOOTBALL,
                current_time=CURRENT_TIME,
                points_awarded=0,
            )

        assert exc_info.value.status_code == 400
        assert "Cannot lock this game" in exc_info.value.detail
        assert "picks lock 1 minute before" in exc_info.value.detail
        transaction.update.assert_not_called()
        transaction.set.assert_not_called()


class TestOtherLockTipLocked:
    def test_other_same_week_lock_tip_locked_raises_400_no_writes(self):
        """Other lock A tip-locked same week → no writes; 400."""
        db, transaction = _build_db_and_txn(
            existing_locks=[("pick_a_id", {"user_id": "user123", "game_id": "game_a", "lock": True})],
            game_dates={"game_a": GAME_A_DATE},
        )
        # Now is after A's tip-lock window; B is still unlocked
        now = datetime(2026, 9, 10, 20, 0, 0, tzinfo=timezone.utc)

        with pytest.raises(HTTPException) as exc_info:
            _run(
                transaction=transaction,
                db=db,
                user_id="user123",
                pick_id="user123_game_b",
                game_id="game_b",
                game_date=GAME_B_DATE,
                picked_team="Team B",
                mode=SportMode.FOOTBALL,
                current_time=now,
                points_awarded=0,
            )

        assert exc_info.value.status_code == 400
        assert "Cannot lock this game because you already have a lock" in exc_info.value.detail
        assert "whose picks have locked" in exc_info.value.detail
        transaction.update.assert_not_called()
        transaction.set.assert_not_called()


class TestNoExistingLocks:
    def test_no_existing_locks_sets_new_pick_at_deterministic_id(self):
        """No existing locks → set new pick lock=True at deterministic id."""
        db, transaction = _build_db_and_txn(existing_locks=[], game_dates={})

        _run(
            transaction=transaction,
            db=db,
            user_id="user123",
            pick_id="user123_game_b",
            game_id="game_b",
            game_date=GAME_B_DATE,
            picked_team="Team B",
            mode=SportMode.FOOTBALL,
            current_time=CURRENT_TIME,
            points_awarded=0,
        )

        unlocked, target_updates, sets = _write_ids(transaction)
        assert unlocked == []
        assert target_updates == []
        assert len(sets) == 1
        assert sets[0][0] == "user123_game_b"
        assert sets[0][1]["lock"] is True
        assert sets[0][1]["user_id"] == "user123"
        assert sets[0][1]["game_id"] == "game_b"


class TestTransactionalDecorator:
    def test_function_has_transactional_decorator(self):
        """Keep one decorator smoke assertion."""
        func = _atomic_lock_swap_and_update
        assert callable(func)
        assert hasattr(func, "to_wrap") or hasattr(func, "_to_wrap") or type(func).__name__ == "_Transactional"
        assert callable(_inner_lock_swap())
