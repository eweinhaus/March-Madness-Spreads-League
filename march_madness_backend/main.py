"""
March Madness Spreads Backend API

Migrated to Vercel + Firebase Firestore + Google OAuth.
Backend-only access to Firestore via Admin SDK.
"""

from fastapi import FastAPI, HTTPException, Depends, status, Request, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, validator
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import logging
import time
from collections import defaultdict
from typing import Optional, Union, List, Tuple, Any, Dict
import requests
from bs4 import BeautifulSoup
import re

from auth import User
from firestore_client import (
    get_db,
    get_auth,
    check_firestore_health,
    server_timestamp,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LEAGUE_ID = os.getenv("LEAGUE_ID", "march_madness_2025")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_current_utc_time():
    return datetime.now(timezone.utc)


def normalize_datetime(dt):
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=timezone.utc)


def _fs_timestamp_to_dt(val):
    """Convert a Firestore timestamp (or datetime) to a tz-aware UTC datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return normalize_datetime(val)
    to_dt = getattr(val, "to_datetime", None)
    if callable(to_dt):
        try:
            return normalize_datetime(to_dt())
        except Exception:
            pass
    return val


def _serialize_doc(doc_dict: dict) -> dict:
    """Convert Firestore document dict to JSON-safe dict (timestamps → ISO strings)."""
    out = {}
    for k, v in doc_dict.items():
        if isinstance(v, datetime):
            out[k] = normalize_datetime(v).isoformat().replace("+00:00", "Z")
        else:
            out[k] = v
    return out

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="March Madness Spreads API",
    description="API for March Madness spread betting pool",
    version="2.0.0",
)

FRONTEND_ORIGINS = [
    os.getenv("FRONTEND_URL", "http://localhost:5173"),
    "http://localhost:5173",
    "http://localhost:3000",
]
# Add any production frontend URL
prod_url = os.getenv("PRODUCTION_FRONTEND_URL")
if prod_url:
    FRONTEND_ORIGINS.append(prod_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ---------------------------------------------------------------------------
# Auth dependency – Firebase ID token verification + get-or-create user
# ---------------------------------------------------------------------------

async def get_current_user(authorization: Optional[str] = Header(None)) -> User:
    """Verify Firebase ID token and return the app user (get-or-create in Firestore)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not authorization or not authorization.startswith("Bearer "):
        raise credentials_exception

    token = authorization.split("Bearer ", 1)[1]

    try:
        auth = get_auth()
        decoded = auth.verify_id_token(token)
    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        raise credentials_exception

    uid = decoded.get("uid")
    email = decoded.get("email", "")
    display_name = decoded.get("name", "") or email

    if not uid:
        raise credentials_exception

    db = get_db()
    user_ref = db.collection("users").document(uid)
    user_snap = user_ref.get()

    if user_snap.exists:
        user_data = user_snap.to_dict()
        return User(
            uid=user_data.get("uid") or uid,
            email=user_data.get("email", email),
            display_name=user_data.get("display_name", display_name),
            league_id=user_data.get("league_id", LEAGUE_ID),
            make_picks=user_data.get("make_picks", True),
            admin=user_data.get("admin", False),
        )

    new_user = {
        "uid": uid,
        "email": email,
        "display_name": display_name,
        "league_id": LEAGUE_ID,
        "make_picks": True,
        "admin": False,
        "created_at": server_timestamp(),
    }
    user_ref.set(new_user)
    logger.info(f"Created new user {uid} ({display_name})")
    invalidate_leaderboard_and_stats(get_db())

    return User(
        uid=uid,
        email=email,
        display_name=display_name,
        league_id=LEAGUE_ID,
        make_picks=True,
        admin=False,
    )


async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return current_user

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class PickSubmission(BaseModel):
    game_id: str
    picked_team: str
    lock: Optional[bool] = None


class GameResult(BaseModel):
    game_id: str
    winning_team: str


class GameCreate(BaseModel):
    home_team: str
    away_team: str
    spread: float
    game_date: datetime

    @validator("game_date", pre=True, always=True)
    def normalize_game_date(cls, v):
        if isinstance(v, str):
            if "Z" in v:
                v = v.replace("Z", "+00:00")
            v = datetime.fromisoformat(v)
        if not isinstance(v, datetime):
            raise ValueError("Invalid datetime format")
        if v.tzinfo is None:
            raise ValueError("Datetime must be timezone-aware")
        return normalize_datetime(v).replace(second=0, microsecond=0)


class GameUpdate(BaseModel):
    home_team: str
    away_team: str
    spread: float
    game_date: datetime
    winning_team: Optional[str] = None

    @validator("game_date", pre=True, always=True)
    def normalize_game_date(cls, v):
        if isinstance(v, str):
            if "Z" in v:
                v = v.replace("Z", "+00:00")
            v = datetime.fromisoformat(v)
        if not isinstance(v, datetime):
            raise ValueError("Invalid datetime format")
        if v.tzinfo is None:
            raise ValueError("Datetime must be timezone-aware")
        return normalize_datetime(v).replace(second=0, microsecond=0)


class TiebreakerCreate(BaseModel):
    question: str
    start_time: datetime

    @validator("start_time", pre=True, always=True)
    def normalize_start_time(cls, v):
        if isinstance(v, str):
            if "Z" in v:
                v = v.replace("Z", "+00:00")
            v = datetime.fromisoformat(v)
        if not isinstance(v, datetime):
            raise ValueError("Invalid datetime format")
        if v.tzinfo is None:
            raise ValueError("Datetime must be timezone-aware")
        return normalize_datetime(v).replace(second=0, microsecond=0)


class TiebreakerUpdate(BaseModel):
    question: str
    start_time: datetime
    answer: Optional[Union[str, float]] = None
    is_active: bool = True

    @validator("start_time", pre=True, always=True)
    def normalize_start_time(cls, v):
        if isinstance(v, str):
            if "Z" in v:
                v = v.replace("Z", "+00:00")
            v = datetime.fromisoformat(v)
        if not isinstance(v, datetime):
            raise ValueError("Invalid datetime format")
        if v.tzinfo is None:
            raise ValueError("Datetime must be timezone-aware")
        return normalize_datetime(v).replace(second=0, microsecond=0)


class TiebreakerPick(BaseModel):
    tiebreaker_id: str
    answer: Union[str, float]


class TiebreakerPointsUpdate(BaseModel):
    user_id: str
    tiebreaker_id: str
    points: int

# ---------------------------------------------------------------------------
# Leaderboard periods (tip-off in America/New_York calendar date)
# ---------------------------------------------------------------------------

def get_second_half_start_utc():
    """Second half = tip-offs on or after Mar 24, 2026 Eastern time."""
    z = ZoneInfo("America/New_York")
    return datetime(2026, 3, 24, 0, 0, 0, tzinfo=z).astimezone(timezone.utc)


def get_week_ranges():
    """Labels for leaderboard / stats period filters."""
    return {
        "overall": {"start": None, "end": None, "label": "Overall"},
        "first_half": {"start": None, "end": None, "label": "First Half (through Mar 23)"},
        "second_half": {"start": None, "end": None, "label": "Second Half (Mar 24+)"},
    }


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _filter_by_week(items, date_key, filter_key):
    """Filter by leaderboard period (game/tiebreaker datetime = tip-off or reveal)."""
    if filter_key == "overall" or filter_key not in ("first_half", "second_half"):
        return items
    boundary = get_second_half_start_utc()
    result = []
    for item in items:
        d = item.get(date_key)
        if d is None:
            continue
        d = normalize_datetime(d) if isinstance(d, datetime) else _parse_iso(d)
        if filter_key == "first_half":
            if d < boundary:
                result.append(item)
        elif filter_key == "second_half":
            if d >= boundary:
                result.append(item)
    return result


# Leaderboard: cache full computed tables in Firestore (1 read per request vs ~3k+).
LEADERBOARD_CACHE_COLLECTION = "_cache"
LEADERBOARD_CACHE_DOC_ID = "leaderboard_v1"
_LEADERBOARD_FILTER_KEYS = ("overall", "first_half", "second_half")


STATS_CACHE_DOC_ID = "stats_v1"
LEADERBOARD_BUILD_LOCK_ID = "leaderboard_build_lock"
_FIRESTORE_IN_QUERY_MAX = 10

# Live page cache: one doc for live_games + live_tiebreakers to cut Firestore reads.
LIVE_CACHE_DOC_ID = "live_v1"
# Configurable via env; longer TTL = fewer reads, slightly staler "live" list (game/tiebreaker outcomes).
LIVE_CACHE_TTL_SEC = int(os.getenv("LIVE_CACHE_TTL_SEC", "120"))


def _cache_doc_delete(db, doc_id: str) -> None:
    try:
        db.collection(LEADERBOARD_CACHE_COLLECTION).document(doc_id).delete()
    except Exception as e:
        logger.warning("cache delete %s failed: %s", doc_id, e)


def invalidate_leaderboard_cache(db) -> None:
    _cache_doc_delete(db, LEADERBOARD_CACHE_DOC_ID)


def invalidate_live_cache(db) -> None:
    _cache_doc_delete(db, LIVE_CACHE_DOC_ID)


def invalidate_stats_cache(db) -> None:
    _cache_doc_delete(db, STATS_CACHE_DOC_ID)


def invalidate_leaderboard_and_stats(db) -> None:
    """When game outcomes or membership change (not tiebreaker-only ranking tweaks)."""
    invalidate_leaderboard_cache(db)
    invalidate_stats_cache(db)
    invalidate_live_cache(db)  # Live list: which games/tiebreakers in progress


def _try_acquire_leaderboard_build_lock(db, ttl_sec: float = 50.0) -> bool:
    """Single-flight for leaderboard rebuild across serverless instances."""
    try:
        from google.cloud.firestore import transactional

        lock_ref = db.collection(LEADERBOARD_CACHE_COLLECTION).document(LEADERBOARD_BUILD_LOCK_ID)
        now = time.time()
        transaction = db.transaction()

        @transactional
        def _txn(transaction, ref):
            snap = ref.get(transaction=transaction)
            if snap.exists:
                exp = (snap.to_dict() or {}).get("expires_at")
                if isinstance(exp, (int, float)) and exp > now:
                    return False
            transaction.set(ref, {"expires_at": now + ttl_sec})
            return True

        return _txn(transaction, lock_ref)
    except Exception as e:
        logger.warning("leaderboard build lock failed: %s", e)
        return False


def _release_leaderboard_build_lock(db) -> None:
    try:
        db.collection(LEADERBOARD_CACHE_COLLECTION).document(LEADERBOARD_BUILD_LOCK_ID).delete()
    except Exception as e:
        logger.warning("leaderboard build lock release: %s", e)


def _leaderboard_list_for_filter(
    users: Dict[str, Any],
    all_games: Dict[str, Any],
    all_tiebreakers: Dict[str, Any],
    all_picks: list,
    all_tb_picks: list,
    filter_key: str,
) -> list:
    filtered_picks = _filter_by_week(all_picks, "game_date", filter_key)
    filtered_tb_picks = _filter_by_week(all_tb_picks, "start_time", filter_key)

    user_game_points = {}
    user_correct_locks = {}
    for p in filtered_picks:
        uid = p.get("user_id")
        if uid not in users:
            continue
        user_game_points[uid] = user_game_points.get(uid, 0) + (p.get("points_awarded") or 0)
        if p.get("lock") and p.get("points_awarded") == 2:
            user_correct_locks[uid] = user_correct_locks.get(uid, 0) + 1

    user_tb_points = {}
    for tp in filtered_tb_picks:
        uid = tp.get("user_id")
        if uid not in users:
            continue
        user_tb_points[uid] = user_tb_points.get(uid, 0) + (tp.get("points_awarded") or 0)

    user_tb_accuracy = {}
    for tp in filtered_tb_picks:
        uid = tp.get("user_id")
        if uid not in users:
            continue
        tb = all_tiebreakers.get(tp.get("tiebreaker_id"))
        if not tb or not tb.get("answer"):
            continue
        try:
            correct_val = float(tb["answer"])
            user_val = float(tp["answer"])
            diff = abs(correct_val - user_val)
        except (ValueError, TypeError):
            diff = 999999
        if uid not in user_tb_accuracy:
            user_tb_accuracy[uid] = []
        user_tb_accuracy[uid].append((tb.get("start_time"), diff))

    for uid in user_tb_accuracy:
        user_tb_accuracy[uid].sort(key=lambda x: x[0] or datetime.min.replace(tzinfo=timezone.utc))

    leaderboard = []
    for uid, u in users.items():
        total_points = user_game_points.get(uid, 0) + user_tb_points.get(uid, 0)
        correct_locks = user_correct_locks.get(uid, 0)
        accuracy_list = user_tb_accuracy.get(uid, [])
        first_diff = accuracy_list[0][1] if len(accuracy_list) > 0 else 999999
        second_diff = accuracy_list[1][1] if len(accuracy_list) > 1 else 999999
        third_diff = accuracy_list[2][1] if len(accuracy_list) > 2 else 999999

        leaderboard.append({
            "display_name": u.get("display_name", u.get("email", "")),
            "uid": uid,
            "total_points": total_points,
            "correct_locks": correct_locks,
            "first_tiebreaker_diff": first_diff,
            "second_tiebreaker_diff": second_diff,
            "third_tiebreaker_diff": third_diff,
        })

    if filter_key == "overall":
        leaderboard.sort(key=lambda x: (-x["total_points"], -x["correct_locks"]))
    else:
        leaderboard.sort(key=lambda x: (
            -x["total_points"],
            -x["correct_locks"],
            x["first_tiebreaker_diff"],
            x["second_tiebreaker_diff"],
            x["third_tiebreaker_diff"],
        ))
    return leaderboard


def _compute_and_store_leaderboard_cache(db) -> Dict[str, list]:
    users = {}
    for doc in db.collection("users").where("make_picks", "==", True).stream():
        u = doc.to_dict()
        created = _fs_timestamp_to_dt(u.get("created_at"))
        if created and created < _parse_iso("2025-06-01T00:00:00Z"):
            continue
        users[u["uid"]] = u

    all_games = {}
    for doc in db.collection("games").stream():
        g = doc.to_dict()
        g["id"] = doc.id
        g["game_date"] = _fs_timestamp_to_dt(g.get("game_date"))
        all_games[doc.id] = g

    all_picks = []
    for doc in db.collection("picks").stream():
        p = doc.to_dict()
        p["id"] = doc.id
        game = all_games.get(p.get("game_id"))
        if game:
            p["game_date"] = game["game_date"]
        all_picks.append(p)

    all_tiebreakers = {}
    for doc in db.collection("tiebreakers").stream():
        t = doc.to_dict()
        t["id"] = doc.id
        t["start_time"] = _fs_timestamp_to_dt(t.get("start_time"))
        all_tiebreakers[doc.id] = t

    all_tb_picks = []
    for doc in db.collection("tiebreaker_picks").stream():
        tp = doc.to_dict()
        tp["id"] = doc.id
        tb = all_tiebreakers.get(tp.get("tiebreaker_id"))
        if tb:
            tp["start_time"] = tb["start_time"]
        all_tb_picks.append(tp)

    cached = {
        fk: _leaderboard_list_for_filter(users, all_games, all_tiebreakers, all_picks, all_tb_picks, fk)
        for fk in _LEADERBOARD_FILTER_KEYS
    }
    db.collection(LEADERBOARD_CACHE_COLLECTION).document(LEADERBOARD_CACHE_DOC_ID).set(
        {**cached, "updated_at": server_timestamp()},
    )
    return cached


def get_lock_day_bounds(dt_utc):
    """Lock-of-the-day window: 3:00 AM ET through next day 3:00 AM ET."""
    dt_utc = normalize_datetime(dt_utc)
    z = ZoneInfo("America/New_York")
    local = dt_utc.astimezone(z)
    if local.hour < 3:
        day = local.date() - timedelta(days=1)
    else:
        day = local.date()
    start_ny = datetime(day.year, day.month, day.day, 3, 0, 0, tzinfo=z)
    end_ny = start_ny + timedelta(days=1)
    return start_ny.astimezone(timezone.utc), end_ny.astimezone(timezone.utc)


PICK_LOCK_BEFORE_TIP = timedelta(minutes=1)


def picks_locked_for_game(current_time, scheduled_utc) -> bool:
    """True when user picks/answers may no longer be submitted or changed (game tip or tiebreaker start)."""
    scheduled_utc = normalize_datetime(scheduled_utc)
    if scheduled_utc is None:
        return False
    return current_time >= scheduled_utc - PICK_LOCK_BEFORE_TIP


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def update_game_scores(db, game_id: str, winning_team: str) -> Tuple[list, Dict[str, int]]:
    """Score all picks for a game. Returns (affected picks, per-user point delta for leaderboard)."""
    picks_ref = db.collection("picks")
    picks_query = picks_ref.where("game_id", "==", game_id).stream()
    affected = []
    user_deltas: Dict[str, int] = {}

    for snap in picks_query:
        pick = snap.to_dict()
        pick_id = snap.id
        old_pts = int(pick.get("points_awarded") or 0)

        if winning_team == "PUSH":
            points = 0
        else:
            norm_picked = pick.get("picked_team", "").rstrip(" *")
            norm_winner = winning_team.rstrip(" *")
            if norm_picked == norm_winner:
                points = 2 if pick.get("lock") else 1
            else:
                points = 0

        picks_ref.document(pick_id).update({"points_awarded": points})
        pick["points_awarded"] = points
        pick["id"] = pick_id
        affected.append(pick)
        uid = pick.get("user_id")
        if uid:
            user_deltas[uid] = user_deltas.get(uid, 0) + (points - old_pts)

    logger.info(f"Scored {len(affected)} picks for game {game_id}, winner={winning_team}")
    return affected, user_deltas


def apply_leaderboard_point_deltas(db, user_deltas: Dict[str, int]) -> None:
    """Update leaderboard total_points by delta (avoids re-reading all picks per user)."""
    lb = db.collection("leaderboard")
    for uid, delta in user_deltas.items():
        if delta == 0:
            continue
        ref = lb.document(uid)
        snap = ref.get()
        cur = int(snap.to_dict().get("total_points") or 0) if snap.exists else 0
        ref.set(
            {"user_id": uid, "total_points": cur + delta, "last_updated": server_timestamp()},
            merge=True,
        )


def update_leaderboard_totals(db, user_ids: list):
    """Recalculate total_points for each user_id from picks + tiebreaker_picks."""
    for uid in user_ids:
        total = 0
        for snap in db.collection("picks").where("user_id", "==", uid).stream():
            total += snap.to_dict().get("points_awarded", 0)
        for snap in db.collection("tiebreaker_picks").where("user_id", "==", uid).stream():
            total += snap.to_dict().get("points_awarded", 0)

        db.collection("leaderboard").document(uid).set(
            {"user_id": uid, "total_points": total, "last_updated": server_timestamp()},
            merge=True,
        )
    logger.info(f"Updated leaderboard for {len(user_ids)} users")

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up – initializing Firebase…")
    try:
        get_db()
        logger.info("Firebase Firestore connection OK")
    except Exception as e:
        logger.error(f"Firebase init failed: {e}")

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health/db")
@app.head("/health/db")
def health_check():
    healthy = check_firestore_health()
    return {
        "status": "healthy" if healthy else "unhealthy",
        "database": "firestore",
        "connected": healthy,
        "timestamp": get_current_utc_time().isoformat(),
    }


@app.get("/health")
@app.head("/health")
def health():
    return {"status": "ok"}


@app.get("/")
@app.head("/")
def root():
    return {"message": "March Madness Spreads API v2 – Firestore"}

# ---------------------------------------------------------------------------
# Auth / current user
# ---------------------------------------------------------------------------

@app.get("/users/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user.dict()

# ---------------------------------------------------------------------------
# Games CRUD
# ---------------------------------------------------------------------------

@app.post("/games")
async def create_game(game: GameCreate, current_user: User = Depends(get_current_admin_user)):
    current_time = get_current_utc_time()
    if game.game_date <= current_time:
        raise HTTPException(status_code=400, detail="Game date must be in the future")
    if game.game_date > current_time + timedelta(days=365):
        raise HTTPException(status_code=400, detail="Game date cannot be more than 1 year in the future")

    db = get_db()
    doc_ref = db.collection("games").document()
    game_data = {
        "home_team": game.home_team,
        "away_team": game.away_team,
        "spread": game.spread,
        "game_date": game.game_date,
        "winning_team": None,
        "created_at": server_timestamp(),
    }
    doc_ref.set(game_data)
    game_data["id"] = doc_ref.id
    game_data["created_at"] = get_current_utc_time()
    return _serialize_doc(game_data)


@app.get("/games")
def get_games(all_games: bool = False, current_user: User = Depends(get_current_user)):
    db = get_db()
    games_ref = db.collection("games")

    if all_games and current_user.admin:
        docs = games_ref.order_by("game_date", direction="DESCENDING").stream()
    else:
        current_time = get_current_utc_time()
        docs = games_ref.where("game_date", ">", current_time).order_by("game_date").stream()

    result = []
    for doc in docs:
        d = doc.to_dict()
        d["id"] = doc.id
        result.append(_serialize_doc(d))
    return result


@app.put("/games/{game_id}")
async def update_game(game_id: str, game: GameUpdate, current_user: User = Depends(get_current_admin_user)):
    db = get_db()
    doc_ref = db.collection("games").document(game_id)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Game not found")

    existing = snap.to_dict()
    old_winner = existing.get("winning_team")

    update_data = {
        "home_team": game.home_team,
        "away_team": game.away_team,
        "spread": game.spread,
        "game_date": game.game_date,
        "winning_team": game.winning_team,
    }
    doc_ref.update(update_data)

    if game.winning_team != old_winner and game.winning_team:
        affected_picks, deltas = update_game_scores(db, game_id, game.winning_team)
        apply_leaderboard_point_deltas(db, deltas)

    updated = {**existing, **update_data, "id": game_id}
    invalidate_leaderboard_and_stats(db)
    return _serialize_doc(updated)


@app.delete("/games/{game_id}")
async def delete_game(game_id: str, current_user: User = Depends(get_current_admin_user)):
    db = get_db()
    doc_ref = db.collection("games").document(game_id)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Game not found")

    affected_user_ids = set()
    for pick_snap in db.collection("picks").where("game_id", "==", game_id).stream():
        affected_user_ids.add(pick_snap.to_dict().get("user_id"))
        pick_snap.reference.delete()

    doc_ref.delete()

    if affected_user_ids:
        update_leaderboard_totals(db, list(affected_user_ids))
    invalidate_leaderboard_and_stats(db)

    return {"message": "Game deleted successfully"}

# ---------------------------------------------------------------------------
# Picks
# ---------------------------------------------------------------------------

@app.post("/submit_pick")
async def submit_pick(pick: PickSubmission, current_user: User = Depends(get_current_user)):
    if not current_user.make_picks:
        raise HTTPException(status_code=403, detail="You do not have permission to make picks")

    db = get_db()

    game_snap = db.collection("games").document(pick.game_id).get()
    if not game_snap.exists:
        raise HTTPException(status_code=404, detail="Game not found")
    game = game_snap.to_dict()

    existing_pick_snap = None
    existing_pick = None
    for snap in db.collection("picks").where("user_id", "==", current_user.uid).where("game_id", "==", pick.game_id).stream():
        existing_pick_snap = snap
        existing_pick = snap.to_dict()
        break

    current_time = get_current_utc_time()
    game_date = _fs_timestamp_to_dt(game["game_date"])
    picks_locked = picks_locked_for_game(current_time, game_date)

    # Lock logic
    if pick.lock is not None:
        existing_locks = []
        for snap in db.collection("picks").where("user_id", "==", current_user.uid).where("lock", "==", True).stream():
            ld = snap.to_dict()
            ld["_id"] = snap.id
            g_snap = db.collection("games").document(ld["game_id"]).get()
            if g_snap.exists:
                ld["game_date"] = _fs_timestamp_to_dt(g_snap.to_dict()["game_date"])
            existing_locks.append(ld)

        if pick.lock:
            target_day_start, target_day_end = get_lock_day_bounds(game_date)
            for lock in existing_locks:
                if lock["game_id"] != pick.game_id:
                    lock_game_date = lock.get("game_date")
                    if lock_game_date is None:
                        continue
                    lock_day_start, lock_day_end = get_lock_day_bounds(lock_game_date)
                    same_day = not (target_day_start >= lock_day_end or target_day_end <= lock_day_start)
                    if same_day:
                        if picks_locked_for_game(current_time, lock_game_date):
                            raise HTTPException(
                                status_code=400,
                                detail="Cannot lock this game because you already have a lock on a game whose picks have locked for the same day (3am ET–3am ET).",
                            )
                        db.collection("picks").document(lock["_id"]).update({"lock": False})

        elif not pick.lock and existing_pick and existing_pick.get("lock"):
            if picks_locked:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot unlock — picks lock 1 minute before scheduled tip-off.",
                )

    if picks_locked:
        is_new_pick = existing_pick is None
        if is_new_pick:
            raise HTTPException(
                status_code=400,
                detail="Cannot submit a new pick — picks lock 1 minute before scheduled tip-off.",
            )
        team_changed = pick.picked_team != existing_pick.get("picked_team")
        lock_changed = pick.lock is not None and pick.lock != existing_pick.get("lock")
        if lock_changed:
            raise HTTPException(
                status_code=400,
                detail="Your lock cannot be changed — picks lock 1 minute before scheduled tip-off.",
            )
        if team_changed:
            raise HTTPException(
                status_code=400,
                detail="Your pick cannot be changed — picks lock 1 minute before scheduled tip-off.",
            )
        return {"message": "No changes after picks locked.", "pick": _serialize_doc({**existing_pick, "id": existing_pick_snap.id})}

    if existing_pick:
        lock_value = pick.lock if pick.lock is not None else existing_pick.get("lock", False)
        existing_pick_snap.reference.update({"picked_team": pick.picked_team, "lock": lock_value})
        updated = {**existing_pick, "picked_team": pick.picked_team, "lock": lock_value, "id": existing_pick_snap.id}
        invalidate_stats_cache(db)
        return {"message": "Pick updated successfully", "pick": _serialize_doc(updated)}
    else:
        lock_value = pick.lock if pick.lock is not None else False
        new_pick_data = {
            "user_id": current_user.uid,
            "game_id": pick.game_id,
            "picked_team": pick.picked_team,
            "points_awarded": 0,
            "lock": lock_value,
            "created_at": server_timestamp(),
        }
        doc_ref = db.collection("picks").document()
        doc_ref.set(new_pick_data)
        new_pick_data["id"] = doc_ref.id
        new_pick_data["created_at"] = get_current_utc_time()
        invalidate_stats_cache(db)
        return {"message": "Pick submitted successfully", "pick": _serialize_doc(new_pick_data)}


def _apply_game_result(db, game_id: str, winning_team: str, auto: bool = False) -> bool:
    """Set winning_team and score picks. If auto=True, sets auto_resolved_at. Returns False if game missing or already resolved."""
    game_ref = db.collection("games").document(game_id)
    game_snap = game_ref.get()
    if not game_snap.exists:
        return False
    existing = game_snap.to_dict()
    if existing.get("winning_team"):
        return False
    payload: Dict[str, Any] = {"winning_team": winning_team}
    if auto:
        payload["auto_resolved_at"] = server_timestamp()
    game_ref.update(payload)
    affected_picks, deltas = update_game_scores(db, game_id, winning_team)
    apply_leaderboard_point_deltas(db, deltas)
    return True


@app.post("/update_score")
def update_score(result: GameResult):
    db = get_db()
    game_ref = db.collection("games").document(result.game_id)
    game_snap = game_ref.get()
    if not game_snap.exists:
        raise HTTPException(status_code=404, detail="Game not found")

    game_ref.update({"winning_team": result.winning_team})
    _affected, deltas = update_game_scores(db, result.game_id, result.winning_team)
    apply_leaderboard_point_deltas(db, deltas)
    invalidate_leaderboard_and_stats(db)

    return {"message": "Scores updated successfully", "winning_team": result.winning_team}

# ---------------------------------------------------------------------------
# My picks (current user)
# ---------------------------------------------------------------------------

@app.get("/my_picks")
async def get_my_picks(current_user: User = Depends(get_current_user)):
    db = get_db()
    games = {doc.id: {**doc.to_dict(), "id": doc.id} for doc in db.collection("games").order_by("game_date").stream()}
    user_picks = {}
    for snap in db.collection("picks").where("user_id", "==", current_user.uid).stream():
        p = snap.to_dict()
        user_picks[p["game_id"]] = p

    result = []
    for gid, g in games.items():
        pick = user_picks.get(gid, {})
        row = {
            "game_id": gid,
            "home_team": g["home_team"],
            "away_team": g["away_team"],
            "spread": g["spread"],
            "game_date": g["game_date"],
            "winning_team": g.get("winning_team"),
            "picked_team": pick.get("picked_team"),
            "points_awarded": pick.get("points_awarded"),
            "lock": pick.get("lock"),
        }
        result.append(_serialize_doc(row))
    return result


@app.get("/picks_data")
async def get_picks_data(current_user: User = Depends(get_current_user)):
    if not current_user.make_picks:
        raise HTTPException(status_code=403, detail="You do not have permission to make picks")

    db = get_db()
    current_time = get_current_utc_time()

    games_out = []
    for doc in db.collection("games").where("game_date", ">", current_time).order_by("game_date").stream():
        g = doc.to_dict()
        g["id"] = doc.id
        g["game_id"] = doc.id
        games_out.append(g)

    user_picks = {}
    for snap in db.collection("picks").where("user_id", "==", current_user.uid).stream():
        p = snap.to_dict()
        user_picks[p["game_id"]] = p

    games_result = []
    for g in games_out:
        pick = user_picks.get(g["id"], {})
        row = {
            "game_id": g["id"],
            "home_team": g["home_team"],
            "away_team": g["away_team"],
            "spread": g["spread"],
            "game_date": g["game_date"],
            "winning_team": g.get("winning_team"),
            "picked_team": pick.get("picked_team"),
            "points_awarded": pick.get("points_awarded"),
            "lock": pick.get("lock"),
        }
        games_result.append(_serialize_doc(row))

    # Avoid compound query (start_time + is_active + order_by) — requires a Firestore
    # composite index and fails on empty projects. Filter/sort in process instead.
    tiebreakers_out = []
    for doc in db.collection("tiebreakers").stream():
        t = doc.to_dict()
        if not t.get("is_active", True):
            continue
        st = _fs_timestamp_to_dt(t.get("start_time"))
        if st is None or st <= current_time:
            continue
        t["id"] = doc.id
        t["tiebreaker_id"] = doc.id
        tiebreakers_out.append(t)
    tiebreakers_out.sort(
        key=lambda x: _fs_timestamp_to_dt(x.get("start_time"))
        or datetime.min.replace(tzinfo=timezone.utc)
    )

    user_tb_picks = {}
    for snap in db.collection("tiebreaker_picks").where("user_id", "==", current_user.uid).stream():
        tp = snap.to_dict()
        user_tb_picks[tp["tiebreaker_id"]] = tp

    tiebreakers_result = []
    for t in tiebreakers_out:
        tp = user_tb_picks.get(t["id"], {})
        row = {
            "tiebreaker_id": t["id"],
            "question": t["question"],
            "start_time": t["start_time"],
            "correct_answer": t.get("answer"),
            "is_active": t.get("is_active", True),
            "user_answer": tp.get("answer"),
            "points_awarded": tp.get("points_awarded"),
        }
        tiebreakers_result.append(_serialize_doc(row))

    return {"games": games_result, "tiebreakers": tiebreakers_result}

# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

@app.get("/leaderboard/weeks")
def get_available_weeks():
    week_ranges = get_week_ranges()
    return {"weeks": [{"key": k, "label": v["label"]} for k, v in week_ranges.items()]}


def _get_leaderboard_response(db, filter_key: str) -> list:
    """Read-through cache with single-flight rebuild to avoid duplicate full scans."""
    cache_ref = db.collection(LEADERBOARD_CACHE_COLLECTION).document(LEADERBOARD_CACHE_DOC_ID)
    for attempt in range(60):
        snap = cache_ref.get()
        if snap.exists:
            data = snap.to_dict() or {}
            row = data.get(filter_key)
            if row is not None:
                return row

        if _try_acquire_leaderboard_build_lock(db):
            try:
                cached = _compute_and_store_leaderboard_cache(db)
                return cached.get(filter_key, [])
            finally:
                _release_leaderboard_build_lock(db)

        time.sleep(0.08)

    cached = _compute_and_store_leaderboard_cache(db)
    return cached.get(filter_key, [])


@app.get("/leaderboard")
def get_leaderboard(filter: str = "overall"):
    db = get_db()
    if filter not in _LEADERBOARD_FILTER_KEYS:
        filter = "overall"
    return _get_leaderboard_response(db, filter)

# ---------------------------------------------------------------------------
# User picks (public, by uid – for started games)
# ---------------------------------------------------------------------------

@app.get("/user_picks/{uid}")
def get_user_picks(uid: str):
    db = get_db()
    current_time = get_current_utc_time()

    user_snap = db.collection("users").document(uid).get()
    if not user_snap.exists:
        raise HTTPException(status_code=404, detail="User not found")

    all_games = {}
    for doc in db.collection("games").stream():
        g = doc.to_dict()
        g["id"] = doc.id
        gd = _fs_timestamp_to_dt(g.get("game_date"))
        if gd and gd <= current_time:
            all_games[doc.id] = {**g, "game_date": gd}

    user_picks = {}
    for snap in db.collection("picks").where("user_id", "==", uid).stream():
        p = snap.to_dict()
        user_picks[p["game_id"]] = p

    result = []
    for gid, g in sorted(all_games.items(), key=lambda x: x[1]["game_date"], reverse=True):
        pick = user_picks.get(gid, {})
        row = {
            "game_id": gid,
            "home_team": g["home_team"],
            "away_team": g["away_team"],
            "spread": g["spread"],
            "game_date": g["game_date"],
            "winning_team": g.get("winning_team"),
            "picked_team": pick.get("picked_team"),
            "points_awarded": pick.get("points_awarded"),
        }
        result.append(_serialize_doc(row))
    return result

# ---------------------------------------------------------------------------
# Live games (cached to reduce Firestore reads)
# ---------------------------------------------------------------------------

def _compute_live_data(db) -> Tuple[List[Any], List[Any]]:
    """Compute live_games and live_tiebreakers lists (serialized for cache)."""
    current_time = get_current_utc_time()

    games_out = []
    for doc in db.collection("games").where("game_date", "<=", current_time).stream():
        g = doc.to_dict()
        winner = g.get("winning_team")
        if winner and winner.strip():
            continue
        g["id"] = doc.id
        g["game_id"] = doc.id
        games_out.append(g)

    game_ids = [g["id"] for g in games_out]

    make_picks_uids = {
        (d.to_dict() or {}).get("uid") or d.id
        for d in db.collection("users").where("make_picks", "==", True).stream()
        if (d.to_dict() or {}).get("uid") or d.id
    }

    picks_by_game: Dict[str, list] = {gid: [] for gid in game_ids}
    for gid in game_ids:
        for snap in db.collection("picks").where("game_id", "==", gid).stream():
            p = snap.to_dict()
            if p.get("user_id") in make_picks_uids:
                picks_by_game[gid].append(p)

    live_games_result = []
    for g in sorted(games_out, key=lambda x: _fs_timestamp_to_dt(x.get("game_date")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        gid = g["id"]
        game_picks = picks_by_game.get(gid, [])
        row = {
            "game_id": gid,
            "home_team": g["home_team"],
            "away_team": g["away_team"],
            "spread": g["spread"],
            "game_date": g["game_date"],
            "winning_team": g.get("winning_team"),
            "total_picks": len(game_picks),
            "home_picks": sum(1 for p in game_picks if p.get("picked_team") == g["home_team"]),
            "away_picks": sum(1 for p in game_picks if p.get("picked_team") == g["away_team"]),
        }
        live_games_result.append(_serialize_doc(row))

    tbs = []
    for doc in db.collection("tiebreakers").where("is_active", "==", True).stream():
        t = doc.to_dict()
        st = _fs_timestamp_to_dt(t.get("start_time"))
        if st and st <= current_time and not t.get("answer"):
            t["id"] = doc.id
            t["tiebreaker_id"] = doc.id
            tbs.append(t)

    tb_ids = [t["id"] for t in tbs]
    picks_count = {tid: 0 for tid in tb_ids}
    if tb_ids:
        for i in range(0, len(tb_ids), _FIRESTORE_IN_QUERY_MAX):
            chunk = tb_ids[i : i + _FIRESTORE_IN_QUERY_MAX]
            for snap in db.collection("tiebreaker_picks").where(
                "tiebreaker_id", "in", list(chunk)
            ).stream():
                tp = snap.to_dict()
                if tp.get("user_id") in make_picks_uids:
                    tid = tp.get("tiebreaker_id")
                    if tid in picks_count:
                        picks_count[tid] = picks_count.get(tid, 0) + 1

    live_tiebreakers_result = []
    for t in sorted(tbs, key=lambda x: _fs_timestamp_to_dt(x.get("start_time")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        row = {
            "tiebreaker_id": t["id"],
            "question": t["question"],
            "start_time": t["start_time"],
            "is_active": t.get("is_active", True),
            "total_picks": picks_count.get(t["id"], 0),
        }
        live_tiebreakers_result.append(_serialize_doc(row))

    return (live_games_result, live_tiebreakers_result)


def _get_live_cache(db) -> Tuple[List[Any], List[Any]]:
    """Read-through cache for live_games + live_tiebreakers. 1 read when warm, full compute when cold."""
    cache_ref = db.collection(LEADERBOARD_CACHE_COLLECTION).document(LIVE_CACHE_DOC_ID)
    snap = cache_ref.get()
    if snap.exists:
        data = snap.to_dict() or {}
        updated_at = data.get("updated_at")
        if updated_at:
            dt = _fs_timestamp_to_dt(updated_at)
            if dt and (get_current_utc_time() - dt).total_seconds() < LIVE_CACHE_TTL_SEC:
                return (
                    data.get("live_games") or [],
                    data.get("live_tiebreakers") or [],
                )
    live_games, live_tiebreakers = _compute_live_data(db)
    cache_ref.set({
        "live_games": live_games,
        "live_tiebreakers": live_tiebreakers,
        "updated_at": server_timestamp(),
    })
    return (live_games, live_tiebreakers)


@app.get("/live")
def get_live():
    """Combined live_games + live_tiebreakers in one response. One cache read per refresh."""
    db = get_db()
    live_games, live_tiebreakers = _get_live_cache(db)
    return {"live_games": live_games, "live_tiebreakers": live_tiebreakers}


@app.get("/live_games")
def get_live_games():
    db = get_db()
    live_games, _ = _get_live_cache(db)
    return live_games


@app.get("/live_games/{game_id}/picks")
def get_game_picks(game_id: str):
    db = get_db()
    result = []
    for snap in db.collection("picks").where("game_id", "==", game_id).stream():
        p = snap.to_dict()
        u_snap = db.collection("users").document(p["user_id"]).get()
        if not u_snap.exists:
            continue
        u = u_snap.to_dict()
        if not u.get("make_picks"):
            continue
        result.append({
            "display_name": u.get("display_name", u.get("email", "")),
            "uid": p["user_id"],
            "picked_team": p.get("picked_team"),
            "lock": p.get("lock", False),
        })
    result.sort(key=lambda x: x["display_name"])
    return result

# ---------------------------------------------------------------------------
# Admin – user picks status
# ---------------------------------------------------------------------------

@app.get("/admin/user_picks_status")
async def get_user_picks_status(current_user: User = Depends(get_current_admin_user)):
    db = get_db()
    current_time = get_current_utc_time()
    current_day_start, current_day_end = get_lock_day_bounds(current_time)

    upcoming_games = []
    for doc in db.collection("games").where("game_date", ">", current_time).stream():
        upcoming_games.append(doc.id)
    total_upcoming_games = len(upcoming_games)

    # Single-field query only — compound (is_active + start_time) needs a Firestore composite index.
    upcoming_tbs = []
    for doc in db.collection("tiebreakers").where("is_active", "==", True).stream():
        st = _fs_timestamp_to_dt(doc.to_dict().get("start_time"))
        if st and st > current_time:
            upcoming_tbs.append(doc.id)
    total_upcoming_tbs = len(upcoming_tbs)

    total_required = total_upcoming_games + total_upcoming_tbs

    users = {}
    for doc in db.collection("users").where("make_picks", "==", True).stream():
        u = doc.to_dict() or {}
        uid = u.get("uid") or doc.id
        if not uid:
            continue
        users[uid] = u

    upcoming_set = set(upcoming_games)
    upcoming_tb_set = set(upcoming_tbs)

    all_picks: Dict[str, list] = defaultdict(list)
    if upcoming_games:
        for i in range(0, len(upcoming_games), _FIRESTORE_IN_QUERY_MAX):
            chunk = upcoming_games[i : i + _FIRESTORE_IN_QUERY_MAX]
            for snap in db.collection("picks").where("game_id", "in", list(chunk)).stream():
                p = snap.to_dict()
                uid = p.get("user_id")
                if uid:
                    all_picks[uid].append(p)

    all_tb_picks: Dict[str, list] = defaultdict(list)
    if upcoming_tbs:
        for i in range(0, len(upcoming_tbs), _FIRESTORE_IN_QUERY_MAX):
            chunk = upcoming_tbs[i : i + _FIRESTORE_IN_QUERY_MAX]
            for snap in db.collection("tiebreaker_picks").where(
                "tiebreaker_id", "in", list(chunk)
            ).stream():
                tp = snap.to_dict()
                uid = tp.get("user_id")
                if uid:
                    all_tb_picks[uid].append(tp)

    lock_picks_by_user: Dict[str, list] = defaultdict(list)
    for snap in db.collection("picks").where("lock", "==", True).stream():
        p = snap.to_dict()
        uid = p.get("user_id")
        if uid and uid in users:
            lock_picks_by_user[uid].append(p)

    all_games_cache = {}
    for doc in db.collection("games").stream():
        g = doc.to_dict()
        all_games_cache[doc.id] = g

    result = []
    for uid, u in users.items():
        user_upcoming_picks = sum(
            1 for p in all_picks.get(uid, []) if p.get("game_id") in upcoming_set
        )
        user_upcoming_tb_picks = sum(
            1 for tp in all_tb_picks.get(uid, []) if tp.get("tiebreaker_id") in upcoming_tb_set
        )
        total_picks_made = user_upcoming_picks + user_upcoming_tb_picks

        has_lock = False
        for p in lock_picks_by_user.get(uid, []):
            if not p.get("lock"):
                continue
            game = all_games_cache.get(p.get("game_id"))
            if game:
                gd = _fs_timestamp_to_dt(game.get("game_date"))
                if gd and current_day_start <= gd < current_day_end:
                    has_lock = True
                    break

        result.append({
            "display_name": u.get("display_name", u.get("email", "")),
            "email": (u.get("email") or "").strip(),
            "uid": uid,
            "total_games": total_required,
            "picks_made": total_picks_made,
            "is_complete": total_picks_made == total_required,
            "has_current_day_lock": has_lock,
        })

    result.sort(key=lambda x: x["display_name"])
    return result

# ---------------------------------------------------------------------------
# Admin – all picks for a specific user
# ---------------------------------------------------------------------------

@app.get("/admin/user_all_picks/{uid}")
async def get_user_all_picks(uid: str, current_user: User = Depends(get_current_admin_user)):
    db = get_db()
    user_snap = db.collection("users").document(uid).get()
    if not user_snap.exists:
        raise HTTPException(status_code=404, detail="User not found")
    u = user_snap.to_dict()
    if not u.get("make_picks"):
        raise HTTPException(status_code=404, detail="User not found")

    all_games = {}
    for doc in db.collection("games").order_by("game_date").stream():
        g = doc.to_dict()
        g["id"] = doc.id
        all_games[doc.id] = g

    user_picks = {}
    for snap in db.collection("picks").where("user_id", "==", uid).stream():
        p = snap.to_dict()
        user_picks[p["game_id"]] = p

    game_picks = []
    for gid, g in all_games.items():
        pick = user_picks.get(gid, {})
        row = {
            "game_id": gid,
            "home_team": g["home_team"],
            "away_team": g["away_team"],
            "spread": g["spread"],
            "game_date": g["game_date"],
            "winning_team": g.get("winning_team"),
            "picked_team": pick.get("picked_team"),
            "points_awarded": pick.get("points_awarded"),
            "lock": pick.get("lock"),
        }
        game_picks.append(_serialize_doc(row))

    all_tbs = {}
    for doc in db.collection("tiebreakers").order_by("start_time").stream():
        t = doc.to_dict()
        t["id"] = doc.id
        all_tbs[doc.id] = t

    user_tb_picks = {}
    for snap in db.collection("tiebreaker_picks").where("user_id", "==", uid).stream():
        tp = snap.to_dict()
        user_tb_picks[tp["tiebreaker_id"]] = tp

    tiebreaker_picks = []
    for tid, t in all_tbs.items():
        tp = user_tb_picks.get(tid, {})
        row = {
            "tiebreaker_id": tid,
            "question": t["question"],
            "start_time": t["start_time"],
            "correct_answer": t.get("answer"),
            "is_active": t.get("is_active", True),
            "user_answer": tp.get("answer"),
            "points_awarded": tp.get("points_awarded"),
        }
        tiebreaker_picks.append(_serialize_doc(row))

    return {
        "user": {"uid": uid, "display_name": u.get("display_name", "")},
        "game_picks": game_picks,
        "tiebreaker_picks": tiebreaker_picks,
    }

# ---------------------------------------------------------------------------
# User all past picks (public)
# ---------------------------------------------------------------------------

@app.get("/user_all_past_picks/{uid}")
async def get_user_all_past_picks(uid: str, filter: str = "overall"):
    db = get_db()
    current_time = get_current_utc_time()

    user_snap = db.collection("users").document(uid).get()
    if not user_snap.exists:
        raise HTTPException(status_code=404, detail="User not found")
    u = user_snap.to_dict()
    if not u.get("make_picks"):
        raise HTTPException(status_code=404, detail="User not found")

    all_games = {}
    for doc in db.collection("games").stream():
        g = doc.to_dict()
        g["id"] = doc.id
        g["game_date"] = _fs_timestamp_to_dt(g.get("game_date"))
        if g["game_date"] and g["game_date"] <= current_time:
            all_games[doc.id] = g

    user_picks = {}
    for snap in db.collection("picks").where("user_id", "==", uid).stream():
        p = snap.to_dict()
        user_picks[p["game_id"]] = p

    game_picks_list = []
    for gid, g in all_games.items():
        pick = user_picks.get(gid, {})
        row = {
            "game_id": gid,
            "home_team": g["home_team"],
            "away_team": g["away_team"],
            "spread": g["spread"],
            "game_date": g["game_date"],
            "winning_team": g.get("winning_team"),
            "picked_team": pick.get("picked_team"),
            "points_awarded": pick.get("points_awarded"),
            "lock": pick.get("lock"),
        }
        game_picks_list.append(row)

    game_picks_list = _filter_by_week(game_picks_list, "game_date", filter)
    game_picks_list.sort(key=lambda x: x.get("game_date") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    all_tbs = {}
    for doc in db.collection("tiebreakers").stream():
        t = doc.to_dict()
        t["id"] = doc.id
        t["start_time"] = _fs_timestamp_to_dt(t.get("start_time"))
        if t["start_time"] and t["start_time"] <= current_time:
            all_tbs[doc.id] = t

    user_tb_picks = {}
    for snap in db.collection("tiebreaker_picks").where("user_id", "==", uid).stream():
        tp = snap.to_dict()
        user_tb_picks[tp["tiebreaker_id"]] = tp

    tb_picks_list = []
    for tid, t in all_tbs.items():
        tp = user_tb_picks.get(tid, {})
        accuracy_diff = None
        try:
            if t.get("answer") and tp.get("answer"):
                if re.match(r"^[0-9]+\.?[0-9]*$", str(t["answer"])) and re.match(r"^[0-9]+\.?[0-9]*$", str(tp["answer"])):
                    accuracy_diff = abs(float(t["answer"]) - float(tp["answer"]))
        except (ValueError, TypeError):
            pass
        row = {
            "tiebreaker_id": tid,
            "question": t["question"],
            "start_time": t["start_time"],
            "correct_answer": t.get("answer"),
            "is_active": t.get("is_active", True),
            "user_answer": tp.get("answer"),
            "points_awarded": tp.get("points_awarded"),
            "accuracy_diff": accuracy_diff,
        }
        tb_picks_list.append(row)

    tb_picks_list = _filter_by_week(tb_picks_list, "start_time", filter)
    tb_picks_list.sort(key=lambda x: x.get("start_time") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    return {
        "user": {"uid": uid, "display_name": u.get("display_name", "")},
        "game_picks": [_serialize_doc(gp) for gp in game_picks_list],
        "tiebreaker_picks": [_serialize_doc(tp) for tp in tb_picks_list],
    }

# ---------------------------------------------------------------------------
# Tiebreakers CRUD
# ---------------------------------------------------------------------------

@app.post("/tiebreakers")
async def create_tiebreaker(tiebreaker: TiebreakerCreate, current_user: User = Depends(get_current_admin_user)):
    current_time = get_current_utc_time()
    if tiebreaker.start_time <= current_time:
        raise HTTPException(status_code=400, detail="Tiebreaker start time must be in the future")
    if tiebreaker.start_time > current_time + timedelta(days=365):
        raise HTTPException(status_code=400, detail="Tiebreaker start time cannot be more than 1 year in the future")

    db = get_db()
    doc_ref = db.collection("tiebreakers").document()
    data = {
        "question": tiebreaker.question,
        "start_time": tiebreaker.start_time,
        "answer": None,
        "is_active": True,
        "created_at": server_timestamp(),
    }
    doc_ref.set(data)
    data["id"] = doc_ref.id
    data["created_at"] = get_current_utc_time()
    return _serialize_doc(data)


@app.get("/tiebreakers")
def get_tiebreakers():
    db = get_db()
    current_time = get_current_utc_time()
    result = []
    for doc in db.collection("tiebreakers").where("start_time", ">", current_time).where("is_active", "==", True).order_by("start_time").stream():
        t = doc.to_dict()
        t["id"] = doc.id
        result.append(_serialize_doc(t))
    return result


@app.get("/admin/tiebreakers")
async def get_admin_tiebreakers(current_user: User = Depends(get_current_admin_user)):
    db = get_db()
    result = []
    for doc in db.collection("tiebreakers").order_by("start_time", direction="DESCENDING").stream():
        t = doc.to_dict()
        t["id"] = doc.id
        result.append(_serialize_doc(t))
    return result


@app.put("/tiebreakers/{tiebreaker_id}")
async def update_tiebreaker(tiebreaker_id: str, tiebreaker: TiebreakerUpdate, current_user: User = Depends(get_current_admin_user)):
    db = get_db()
    doc_ref = db.collection("tiebreakers").document(tiebreaker_id)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Tiebreaker not found")

    answer_val = str(tiebreaker.answer) if tiebreaker.answer is not None else None
    update_data = {
        "question": tiebreaker.question,
        "start_time": tiebreaker.start_time,
        "answer": answer_val,
        "is_active": tiebreaker.is_active,
    }
    doc_ref.update(update_data)

    updated = {**snap.to_dict(), **update_data, "id": tiebreaker_id}
    invalidate_leaderboard_cache(db)
    return _serialize_doc(updated)


@app.delete("/tiebreakers/{tiebreaker_id}")
async def delete_tiebreaker(tiebreaker_id: str, current_user: User = Depends(get_current_admin_user)):
    db = get_db()
    doc_ref = db.collection("tiebreakers").document(tiebreaker_id)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Tiebreaker not found")

    affected_user_ids = set()
    for tp_snap in db.collection("tiebreaker_picks").where("tiebreaker_id", "==", tiebreaker_id).stream():
        affected_user_ids.add(tp_snap.to_dict().get("user_id"))
        tp_snap.reference.delete()

    doc_ref.delete()

    if affected_user_ids:
        update_leaderboard_totals(db, list(affected_user_ids))
    invalidate_leaderboard_cache(db)

    return {"message": "Tiebreaker deleted successfully"}


@app.get("/live_tiebreakers")
def get_live_tiebreakers():
    db = get_db()
    _, live_tiebreakers = _get_live_cache(db)
    return live_tiebreakers


@app.get("/live_tiebreakers/{tiebreaker_id}/picks")
def get_tiebreaker_picks_detail(tiebreaker_id: str):
    db = get_db()
    result = []
    for snap in db.collection("tiebreaker_picks").where("tiebreaker_id", "==", tiebreaker_id).stream():
        tp = snap.to_dict()
        u_snap = db.collection("users").document(tp["user_id"]).get()
        if not u_snap.exists:
            continue
        u = u_snap.to_dict()
        if not u.get("make_picks"):
            continue
        result.append({
            "display_name": u.get("display_name", u.get("email", "")),
            "uid": tp["user_id"],
            "answer": tp.get("answer"),
        })
    result.sort(key=lambda x: x["display_name"])
    return result


@app.post("/tiebreaker_picks")
async def create_tiebreaker_pick(pick: TiebreakerPick, current_user: User = Depends(get_current_user)):
    if not current_user.make_picks:
        raise HTTPException(status_code=403, detail="You do not have permission to make picks")

    db = get_db()

    tb_snap = db.collection("tiebreakers").document(pick.tiebreaker_id).get()
    if not tb_snap.exists:
        raise HTTPException(status_code=404, detail="Tiebreaker not found or is no longer active")
    tb = tb_snap.to_dict()
    if not tb.get("is_active") or tb.get("answer"):
        raise HTTPException(status_code=404, detail="Tiebreaker not found or is no longer active")

    current_time = get_current_utc_time()
    st = _fs_timestamp_to_dt(tb.get("start_time"))
    if st and picks_locked_for_game(current_time, st):
        raise HTTPException(
            status_code=400,
            detail="Cannot submit or change tiebreaker answer — entries lock 1 minute before the scheduled start.",
        )

    existing_snap = None
    for snap in db.collection("tiebreaker_picks").where("user_id", "==", current_user.uid).where("tiebreaker_id", "==", pick.tiebreaker_id).stream():
        existing_snap = snap
        break

    answer_val = str(pick.answer)

    if existing_snap:
        existing_snap.reference.update({"answer": answer_val})
        updated = {**existing_snap.to_dict(), "answer": answer_val, "id": existing_snap.id}
        return _serialize_doc(updated)
    else:
        new_data = {
            "user_id": current_user.uid,
            "tiebreaker_id": pick.tiebreaker_id,
            "answer": answer_val,
            "points_awarded": 0,
            "created_at": server_timestamp(),
        }
        doc_ref = db.collection("tiebreaker_picks").document()
        doc_ref.set(new_data)
        new_data["id"] = doc_ref.id
        new_data["created_at"] = get_current_utc_time()
        return _serialize_doc(new_data)


@app.get("/my_tiebreaker_picks")
async def get_my_tiebreaker_picks(current_user: User = Depends(get_current_user)):
    db = get_db()
    all_tbs = {}
    for doc in db.collection("tiebreakers").order_by("start_time").stream():
        t = doc.to_dict()
        t["id"] = doc.id
        all_tbs[doc.id] = t

    user_tb_picks = {}
    for snap in db.collection("tiebreaker_picks").where("user_id", "==", current_user.uid).stream():
        tp = snap.to_dict()
        user_tb_picks[tp["tiebreaker_id"]] = tp

    result = []
    for tid, t in all_tbs.items():
        tp = user_tb_picks.get(tid, {})
        row = {
            "tiebreaker_id": tid,
            "question": t["question"],
            "start_time": t["start_time"],
            "correct_answer": t.get("answer"),
            "is_active": t.get("is_active", True),
            "user_answer": tp.get("answer"),
            "points_awarded": tp.get("points_awarded"),
        }
        result.append(_serialize_doc(row))
    return result


@app.put("/tiebreaker_picks/points")
async def update_tiebreaker_points(points_update: TiebreakerPointsUpdate, current_user: User = Depends(get_current_admin_user)):
    db = get_db()
    existing_snap = None
    for snap in db.collection("tiebreaker_picks").where("user_id", "==", points_update.user_id).where("tiebreaker_id", "==", points_update.tiebreaker_id).stream():
        existing_snap = snap
        break

    if not existing_snap:
        raise HTTPException(status_code=404, detail="Tiebreaker pick not found")

    existing_snap.reference.update({"points_awarded": points_update.points})
    update_leaderboard_totals(db, [points_update.user_id])
    invalidate_leaderboard_cache(db)

    updated = {**existing_snap.to_dict(), "points_awarded": points_update.points, "id": existing_snap.id}
    return _serialize_doc(updated)

# ---------------------------------------------------------------------------
# Admin – delete user
# ---------------------------------------------------------------------------

@app.delete("/admin/delete_user/{uid}")
async def delete_user(uid: str, current_user: User = Depends(get_current_admin_user)):
    db = get_db()
    user_ref = db.collection("users").document(uid)
    if not user_ref.get().exists:
        raise HTTPException(status_code=404, detail="User not found")

    for snap in db.collection("picks").where("user_id", "==", uid).stream():
        snap.reference.delete()
    for snap in db.collection("tiebreaker_picks").where("user_id", "==", uid).stream():
        snap.reference.delete()
    lb_ref = db.collection("leaderboard").document(uid)
    if lb_ref.get().exists:
        lb_ref.delete()

    user_ref.delete()
    invalidate_leaderboard_and_stats(db)
    return {"message": "User deleted successfully"}

# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def _compute_player_stats_list(db) -> list:
    users = {}
    for doc in db.collection("users").where("make_picks", "==", True).stream():
        u = doc.to_dict()
        created = _fs_timestamp_to_dt(u.get("created_at"))
        if created and created < _parse_iso("2025-06-01T00:00:00Z"):
            continue
        users[u["uid"]] = u

    all_games = {}
    for doc in db.collection("games").stream():
        g = doc.to_dict()
        all_games[doc.id] = g

    all_picks = []
    for doc in db.collection("picks").stream():
        p = doc.to_dict()
        all_picks.append(p)

    user_stats = {}
    for uid in users:
        user_stats[uid] = {
            "total_picks": 0, "correct_picks": 0, "incorrect_picks": 0, "push_games": 0,
            "total_locks": 0, "correct_locks": 0, "incorrect_locks": 0, "total_points": 0,
        }

    for p in all_picks:
        uid = p.get("user_id")
        if uid not in user_stats:
            continue
        game = all_games.get(p.get("game_id"), {})
        s = user_stats[uid]
        s["total_picks"] += 1
        pts = p.get("points_awarded", 0)
        s["total_points"] += pts
        winning_team = game.get("winning_team", "")
        if pts > 0:
            s["correct_picks"] += 1
        elif winning_team == "PUSH":
            s["push_games"] += 1
        else:
            s["incorrect_picks"] += 1
        if p.get("lock"):
            s["total_locks"] += 1
            if pts == 2:
                s["correct_locks"] += 1
            elif winning_team != "PUSH":
                s["incorrect_locks"] += 1

    result = []
    for uid, s in user_stats.items():
        u = users[uid]
        tp = s["total_picks"]
        result.append({
            "display_name": u.get("display_name", u.get("email", "")),
            "uid": uid,
            "total_picks": tp,
            "correct_picks": s["correct_picks"],
            "incorrect_picks": s["incorrect_picks"],
            "push_games": s["push_games"],
            "total_locks": s["total_locks"],
            "correct_locks": s["correct_locks"],
            "incorrect_locks": s["incorrect_locks"],
            "total_points": s["total_points"],
            "win_percentage": round((s["correct_picks"] / tp) * 100, 1) if tp > 0 else 0,
            "lock_success_rate": round((s["correct_locks"] / s["total_locks"]) * 100, 1) if s["total_locks"] > 0 else 0,
            "avg_points_per_pick": round(s["total_points"] / tp, 2) if tp > 0 else 0,
        })

    result.sort(key=lambda x: (-x["total_points"], -x["correct_locks"], -x["win_percentage"]))
    return result


@app.get("/stats")
def get_player_stats():
    db = get_db()
    cache_ref = db.collection(LEADERBOARD_CACHE_COLLECTION).document(STATS_CACHE_DOC_ID)
    snap = cache_ref.get()
    if snap.exists:
        rows = (snap.to_dict() or {}).get("rows")
        if rows is not None:
            return rows
    rows = _compute_player_stats_list(db)
    cache_ref.set({"rows": rows, "updated_at": server_timestamp()})
    return rows


@app.get("/stats/{uid}")
def get_player_detailed_stats(uid: str):
    db = get_db()

    user_snap = db.collection("users").document(uid).get()
    if not user_snap.exists:
        raise HTTPException(status_code=404, detail="User not found")

    all_games = {}
    for doc in db.collection("games").stream():
        g = doc.to_dict()
        g["id"] = doc.id
        g["game_date"] = _fs_timestamp_to_dt(g.get("game_date"))
        all_games[doc.id] = g

    user_picks_raw = []
    for snap in db.collection("picks").where("user_id", "==", uid).stream():
        p = snap.to_dict()
        game = all_games.get(p.get("game_id"))
        if game:
            p["home_team"] = game["home_team"]
            p["away_team"] = game["away_team"]
            p["spread"] = game["spread"]
            p["winning_team"] = game.get("winning_team")
            p["game_date"] = game["game_date"]
        user_picks_raw.append(p)

    user_picks_raw.sort(key=lambda x: x.get("game_date") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    recent_picks = []
    for p in user_picks_raw[:20]:
        pts = p.get("points_awarded", 0)
        wt = p.get("winning_team", "")
        if pts > 0:
            pick_result = "correct"
        elif wt == "PUSH":
            pick_result = "push"
        else:
            pick_result = "incorrect"
        recent_picks.append(_serialize_doc({
            "picked_team": p.get("picked_team"),
            "points_awarded": pts,
            "lock": p.get("lock"),
            "home_team": p.get("home_team"),
            "away_team": p.get("away_team"),
            "spread": p.get("spread"),
            "winning_team": wt,
            "game_date": p.get("game_date"),
            "pick_result": pick_result,
        }))

    # Streak calculation
    streak_results = []
    for p in user_picks_raw[:20]:
        pts = p.get("points_awarded", 0)
        wt = p.get("winning_team", "")
        if pts > 0:
            streak_results.append("W")
        elif wt == "PUSH":
            streak_results.append("P")
        else:
            streak_results.append("L")

    current_streak = {"result": "N/A", "streak_length": 0}
    if streak_results:
        first = streak_results[0]
        count = 1
        for r in streak_results[1:]:
            if r == first:
                count += 1
            else:
                break
        current_streak = {"result": first, "streak_length": count}

    best_streak = {"result": "W", "streak_length": 0}
    worst_streak = {"result": "L", "streak_length": 0}
    cw, cl, mw, ml = 0, 0, 0, 0
    for r in streak_results:
        if r == "W":
            cw += 1; cl = 0; mw = max(mw, cw)
        elif r == "L":
            cl += 1; cw = 0; ml = max(ml, cl)
        else:
            cw = 0; cl = 0
    best_streak = {"result": "W", "streak_length": mw}
    worst_streak = {"result": "L", "streak_length": ml}

    # Favorite teams
    team_counts = {}
    for p in user_picks_raw:
        team = p.get("picked_team", "")
        if team not in team_counts:
            team_counts[team] = {"count": 0, "correct": 0}
        team_counts[team]["count"] += 1
        if (p.get("points_awarded") or 0) > 0:
            team_counts[team]["correct"] += 1

    favorite_teams = sorted(team_counts.items(), key=lambda x: -x[1]["count"])[:5]
    favorite_teams = [
        {"picked_team": t, "pick_count": d["count"],
         "success_rate": round((d["correct"] / d["count"]) * 100, 1) if d["count"] > 0 else 0}
        for t, d in favorite_teams
    ]

    # Least favorite team (picked against most)
    against_counts = {}
    for p in user_picks_raw:
        game = all_games.get(p.get("game_id"))
        if not game:
            continue
        picked = p.get("picked_team", "")
        other = game["away_team"] if picked == game["home_team"] else game["home_team"]
        if other not in against_counts:
            against_counts[other] = {"count": 0, "correct": 0}
        against_counts[other]["count"] += 1
        if (p.get("points_awarded") or 0) > 0:
            against_counts[other]["correct"] += 1

    least_favorite_team = None
    if against_counts:
        top = max(against_counts.items(), key=lambda x: x[1]["count"])
        least_favorite_team = {
            "picked_against_team": top[0],
            "pick_count": top[1]["count"],
            "success_rate": round((top[1]["correct"] / top[1]["count"]) * 100, 1) if top[1]["count"] > 0 else 0,
        }

    # Best game: correct pick where fewest others picked the same
    all_picks_for_consensus = {}
    for snap in db.collection("picks").stream():
        p = snap.to_dict()
        gid = p.get("game_id")
        team = p.get("picked_team")
        key = (gid, team)
        all_picks_for_consensus[key] = all_picks_for_consensus.get(key, 0) + 1

    best_game = None
    best_consensus = float("inf")
    for p in user_picks_raw:
        if (p.get("points_awarded") or 0) > 0:
            key = (p.get("game_id"), p.get("picked_team"))
            consensus = all_picks_for_consensus.get(key, 1) - 1
            if consensus < best_consensus or (consensus == best_consensus and best_game is None):
                best_consensus = consensus
                best_game = _serialize_doc({
                    "type": "best",
                    "picked_team": p.get("picked_team"),
                    "points_awarded": p.get("points_awarded"),
                    "lock": p.get("lock"),
                    "home_team": p.get("home_team"),
                    "away_team": p.get("away_team"),
                    "spread": p.get("spread"),
                    "game_date": p.get("game_date"),
                    "consensus_count": consensus,
                })

    worst_game = None
    worst_against = -1
    for p in user_picks_raw:
        pts = p.get("points_awarded", 0)
        wt = p.get("winning_team", "")
        if pts == 0 and wt != "PUSH":
            key = (p.get("game_id"), wt)
            against = all_picks_for_consensus.get(key, 0)
            if against > worst_against:
                worst_against = against
                worst_game = _serialize_doc({
                    "type": "worst",
                    "picked_team": p.get("picked_team"),
                    "points_awarded": pts,
                    "lock": p.get("lock"),
                    "home_team": p.get("home_team"),
                    "away_team": p.get("away_team"),
                    "spread": p.get("spread"),
                    "game_date": p.get("game_date"),
                    "winning_team": wt,
                    "against_count": against,
                })

    # Best/worst half (first vs second half by tip-off ET)
    boundary = get_second_half_start_utc()
    z = ZoneInfo("America/New_York")
    period_meta = {
        "first_half": {
            "label": "First Half (through Mar 23)",
            "week_start": datetime(2026, 3, 17, 0, 0, 0, tzinfo=z).astimezone(timezone.utc),
            "week_end": boundary - timedelta(seconds=1),
        },
        "second_half": {
            "label": "Second Half (Mar 24+)",
            "week_start": boundary,
            "week_end": datetime(2026, 4, 8, 23, 59, 59, tzinfo=z).astimezone(timezone.utc),
        },
    }
    week_stats = {}
    for p in user_picks_raw:
        gd = p.get("game_date")
        if not gd:
            continue
        gd = normalize_datetime(gd) if isinstance(gd, datetime) else _parse_iso(str(gd))
        wk = "first_half" if gd < boundary else "second_half"
        if wk not in week_stats:
            m = period_meta[wk]
            week_stats[wk] = {
                "label": m["label"],
                "week_start": m["week_start"],
                "week_end": m["week_end"],
                "total_points": 0,
                "total_picks": 0,
                "correct_picks": 0,
                "locks_used": 0,
            }
        s = week_stats[wk]
        s["total_picks"] += 1
        s["total_points"] += p.get("points_awarded", 0)
        if (p.get("points_awarded") or 0) > 0:
            s["correct_picks"] += 1
        if p.get("lock"):
            s["locks_used"] += 1

    def _fmt_period_bounds(s):
        ws = s["week_start"]
        we = s["week_end"]
        return (
            ws.isoformat().replace("+00:00", "Z"),
            we.isoformat().replace("+00:00", "Z"),
        )

    best_week = None
    worst_week = None
    if week_stats:
        best_wk = max(week_stats.items(), key=lambda x: x[1]["total_points"])
        if best_wk[1]["total_picks"] > 0:
            wss, wee = _fmt_period_bounds(best_wk[1])
            best_week = {
                "week_key": best_wk[0],
                "week_label": best_wk[1]["label"],
                "week_start": wss,
                "week_end": wee,
                "total_points": best_wk[1]["total_points"],
                "total_picks": best_wk[1]["total_picks"],
                "correct_picks": best_wk[1]["correct_picks"],
                "locks_used": best_wk[1]["locks_used"],
                "win_percentage": round((best_wk[1]["correct_picks"] / best_wk[1]["total_picks"]) * 100, 1),
            }
        worst_wk = min(
            [(k, v) for k, v in week_stats.items() if v["total_picks"] > 0],
            key=lambda x: x[1]["correct_picks"] / x[1]["total_picks"],
            default=None,
        )
        if worst_wk and worst_wk[1]["total_picks"] > 0:
            wss, wee = _fmt_period_bounds(worst_wk[1])
            worst_week = {
                "week_key": worst_wk[0],
                "week_label": worst_wk[1]["label"],
                "week_start": wss,
                "week_end": wee,
                "total_points": worst_wk[1]["total_points"],
                "total_picks": worst_wk[1]["total_picks"],
                "correct_picks": worst_wk[1]["correct_picks"],
                "locks_used": worst_wk[1]["locks_used"],
                "win_percentage": round((worst_wk[1]["correct_picks"] / worst_wk[1]["total_picks"]) * 100, 1),
            }

    return {
        "recent_picks": recent_picks,
        "current_streak": current_streak,
        "best_streak": best_streak,
        "worst_streak": worst_streak,
        "favorite_teams": favorite_teams,
        "least_favorite_team": least_favorite_team,
        "best_game": best_game,
        "worst_game": worst_game,
        "best_week": best_week,
        "worst_week": worst_week,
    }

# ---------------------------------------------------------------------------
# Game scores (CBS scraper – no DB dependency) + auto-resolve
# ---------------------------------------------------------------------------

CBS_SCOREBOARD_URL = "https://www.cbssports.com/college-basketball/scoreboard/?layout=compact"


def normalize_team_name_for_matching(team_name):
    if not team_name:
        return ""
    mascots = [
        "Crimson Tide", "Commodores", "Bulldogs", "Tigers", "Wildcats", "Eagles",
        "Bears", "Cowboys", "Trojans", "Spartans", "Volunteers", "Aggies",
        "Longhorns", "Sooners", "Buckeyes", "Wolverines", "Fighting Irish",
        "Golden Bears", "Blue Devils", "Tar Heels", "Seminoles", "Hurricanes",
        "Hokies", "Cavaliers", "Demon Deacons", "Yellow Jackets", "Orange",
        "Cardinals", "Panthers", "Huskies", "Cougars", "Sun Devils", "Ducks",
        "Beavers", "Utes", "Buffaloes", "Buffs", "Bruins", "Mountaineers",
        "Jayhawks", "Cyclones", "Red Raiders", "Horned Frogs", "Cornhuskers",
        "Badgers", "Gophers", "Hawkeyes", "Illini", "Hoosiers", "Terrapins",
        "Nittany Lions", "Scarlet Knights", "Boilermakers",
    ]
    normalized = team_name
    for mascot in mascots:
        normalized = re.sub(rf"\b{re.escape(mascot)}\b", "", normalized, flags=re.IGNORECASE)
    replacements = {
        r"\bSt\.": "State", r"\bVandy\b": "Vanderbilt", r"\bBama\b": "Alabama",
        r"\bW\.": "Western", r"\bE\.": "Eastern", r"\bN\.": "Northern",
        r"\bS\.": "Southern", r"\bC\.": "Central",
        r"\bMiami \(FL\)": "Miami", r"\bMiami-FL\b": "Miami",
    }
    for pattern, replacement in replacements.items():
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    normalized = " ".join(normalized.split()).strip().lower()
    return normalized if normalized else team_name.strip().lower()


def team_names_match_scoreboard(a: str, b: str) -> bool:
    if not a or not b:
        return False
    na = normalize_team_name_for_matching(a)
    nb = normalize_team_name_for_matching(b)
    if na == nb:
        return True
    return na in nb or nb in na


def fetch_cbs_games_data() -> List[dict]:
    """Scrape CBS compact scoreboard. Same shape as /api/gamescores response."""
    games_data: List[dict] = []
    try:
        resp = requests.get(CBS_SCOREBOARD_URL, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for game in soup.find_all("div", class_="single-score-card"):
            try:
                team_cells = game.find_all("td", class_="team") or game.find_all(
                    "td", class_="team--collegebasketball"
                )
                score_cells = game.find_all("td", class_="total")
                if len(team_cells) < 2 or len(score_cells) < 2:
                    continue
                away_el = team_cells[0].find("a", class_="team-name-link")
                home_el = team_cells[1].find("a", class_="team-name-link")
                if not away_el or not home_el:
                    continue
                away_team = away_el.text.strip()
                home_team = home_el.text.strip()
                game_status = game.find("div", class_="game-status emphasis")
                games_data.append(
                    {
                        "AwayTeam": away_team,
                        "HomeTeam": home_team,
                        "AwayScore": score_cells[0].text.strip(),
                        "HomeScore": score_cells[1].text.strip(),
                        "Time": game_status.text.strip() if game_status else "FINAL",
                        "AwayTeamNormalized": normalize_team_name_for_matching(away_team),
                        "HomeTeamNormalized": normalize_team_name_for_matching(home_team),
                    }
                )
            except Exception:
                continue
        return games_data
    except Exception as e:
        logger.warning("fetch_cbs_games_data failed: %s", e)
        return games_data


def cbs_status_is_final(time_str: str) -> bool:
    if not time_str:
        return False
    t = time_str.strip().lower()
    return "final" in t


def league_home_away_scores_from_cbs_row(game: dict, row: dict) -> Optional[Tuple[int, int]]:
    """
    Map a CBS row to (league_home_points, league_away_points).
    Returns None if this row does not match the game or scores are invalid.
    """
    ga = (game.get("away_team") or "").strip()
    gh = (game.get("home_team") or "").strip()
    ra = row["AwayTeam"].strip()
    rh = row["HomeTeam"].strip()

    def parse() -> Optional[Tuple[int, int]]:
        try:
            ap = int(row["AwayScore"])
            hp = int(row["HomeScore"])
        except (ValueError, TypeError):
            return None
        return hp, ap

    # Exact orientation: CBS away = league away
    if ra == ga and rh == gh:
        p = parse()
        if not p:
            return None
        return p[0], p[1]  # home_pts, away_pts

    if ra == gh and rh == ga:
        p = parse()
        if not p:
            return None
        return p[1], p[0]  # league home was CBS away

    san = row.get("AwayTeamNormalized") or normalize_team_name_for_matching(ra)
    shn = row.get("HomeTeamNormalized") or normalize_team_name_for_matching(rh)
    gan = normalize_team_name_for_matching(ga)
    ghn = normalize_team_name_for_matching(gh)

    if san == gan and shn == ghn:
        p = parse()
        return (p[0], p[1]) if p else None
    if san == ghn and shn == gan:
        p = parse()
        return (p[1], p[0]) if p else None

    if team_names_match_scoreboard(ra, ga) and team_names_match_scoreboard(rh, gh):
        p = parse()
        return (p[0], p[1]) if p else None
    if team_names_match_scoreboard(ra, gh) and team_names_match_scoreboard(rh, ga):
        p = parse()
        return (p[1], p[0]) if p else None

    return None


def compute_covering_team(
    home_pts: int, away_pts: int, spread: float, home_team: str, away_team: str
) -> str:
    """
    spread > 0  -> home favored by spread (home -spread).
    spread < 0  -> away favored by |spread|.
    spread == 0 -> pick'em (straight winner / push on tie).
    """
    s = float(spread)
    if s == 0:
        if home_pts > away_pts:
            return home_team
        if away_pts > home_pts:
            return away_team
        return "PUSH"
    if s > 0:
        margin = home_pts - away_pts
        if margin > s:
            return home_team
        if margin < s:
            return away_team
        return "PUSH" if s == int(s) else away_team
    fav = -s
    away_margin = away_pts - home_pts
    if away_margin > fav:
        return away_team
    if away_margin < fav:
        return home_team
    return "PUSH" if fav == int(fav) else home_team


def run_auto_resolve_games(db) -> dict:
    """
    For each unresolved game that has started, if CBS shows final + matching row,
    set winning_team (cover/push) and score picks.
    """
    rows = fetch_cbs_games_data()
    now = get_current_utc_time()
    resolved: List[dict] = []
    skipped = 0

    for snap in db.collection("games").stream():
        g = snap.to_dict()
        gid = snap.id
        if g.get("winning_team"):
            skipped += 1
            continue
        gd = _fs_timestamp_to_dt(g.get("game_date"))
        if gd and gd > now:
            continue

        home_team = g.get("home_team") or ""
        away_team = g.get("away_team") or ""
        spread = g.get("spread")
        if spread is None:
            continue
        try:
            spread_f = float(spread)
        except (TypeError, ValueError):
            continue

        for row in rows:
            if not cbs_status_is_final(row.get("Time") or ""):
                continue
            pts = league_home_away_scores_from_cbs_row(g, row)
            if not pts:
                continue
            hp, ap = pts
            winner = compute_covering_team(hp, ap, spread_f, home_team, away_team)
            if _apply_game_result(db, gid, winner, auto=True):
                resolved.append(
                    {
                        "game_id": gid,
                        "winning_team": winner,
                        "home_score": hp,
                        "away_score": ap,
                    }
                )
                logger.info(
                    "auto-resolve game %s -> %s (scores %s-%s)",
                    gid,
                    winner,
                    ap,
                    hp,
                )
            break

    if resolved:
        invalidate_leaderboard_and_stats(db)

    return {
        "resolved_count": len(resolved),
        "resolved": resolved,
        "cbs_games_seen": len(rows),
    }


@app.get("/api/gamescores")
async def get_game_scores(request: Request):
    return fetch_cbs_games_data()


@app.post("/internal/auto-resolve-games")
async def internal_auto_resolve_games(
    authorization: Optional[str] = Header(None),
    x_cron_secret: Optional[str] = Header(None, alias="X-Cron-Secret"),
):
    """
    Secured by CRON_SECRET. Call from GitHub Actions or another scheduler every few minutes.
    Accepts Authorization: Bearer <secret> or X-Cron-Secret: <secret>.
    """
    secret = (os.getenv("CRON_SECRET") or "").strip()
    # Empty: disabled. Too short: refuse (avoids accidental weak / empty-string env quirks).
    _min_cron = 16
    if not secret or len(secret) < _min_cron:
        raise HTTPException(
            status_code=503,
            detail=(
                "CRON_SECRET must be set to a random string of at least "
                f"{_min_cron} characters (Vercel env + GitHub Actions secret). "
                "Auto-resolve is disabled until configured."
            ),
        )
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif x_cron_secret:
        token = x_cron_secret.strip()
    if not token or token != secret:
        raise HTTPException(status_code=401, detail="Unauthorized")

    db = get_db()
    try:
        result = run_auto_resolve_games(db)
    except Exception as e:
        logger.exception("auto-resolve failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return result

# ---------------------------------------------------------------------------
# Run (local dev)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
