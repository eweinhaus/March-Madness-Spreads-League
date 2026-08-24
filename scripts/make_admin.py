#!/usr/bin/env python3
"""
Set admin and/or hidden flags on a Firebase user in Firestore.

Usage:
    python scripts/make_admin.py --uid <firebase-uid> --admin
    python scripts/make_admin.py --name "Display Name" --admin --hidden
    python scripts/make_admin.py --uid <firebase-uid> --no-hidden
    python scripts/make_admin.py <firebase-uid>          # legacy: sets admin=True

Lookup is by --uid or --name (case-insensitive display_name). The user must have
signed in at least once (so their document exists in the 'users' collection).
Set GOOGLE_APPLICATION_CREDENTIALS or FIREBASE_SERVICE_ACCOUNT_JSON before running.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore


def _init():
    cred_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if cred_json:
        info = json.loads(cred_json)
        cred = credentials.Certificate(info)
    elif cred_path:
        cred = credentials.Certificate(cred_path)
    else:
        print("ERROR: Set GOOGLE_APPLICATION_CREDENTIALS or FIREBASE_SERVICE_ACCOUNT_JSON")
        sys.exit(1)

    firebase_admin.initialize_app(cred)
    return firestore.client()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Set admin and/or hidden flags on a Firestore user."
    )
    parser.add_argument(
        "uid_positional",
        nargs="?",
        help="Legacy: Firebase UID (implies --admin when no flags are given)",
    )
    parser.add_argument("--uid", dest="uid_flag", help="Firebase UID")
    parser.add_argument(
        "--name",
        help="Case-insensitive exact match on users.display_name",
    )
    parser.add_argument(
        "--admin",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Set or clear the admin flag",
    )
    parser.add_argument(
        "--hidden",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Set or clear the hidden flag",
    )
    args = parser.parse_args(argv)

    uid = args.uid_flag
    name = args.name
    positional = args.uid_positional

    if uid and name:
        parser.error("Use exactly one of --uid or --name")
    if uid and positional:
        parser.error("Pass UID via --uid or as a positional argument, not both")
    if name and positional:
        parser.error("Use --name or a positional UID, not both")
    if not uid and not name and not positional:
        parser.error("Provide --uid, --name, or a positional UID")

    admin = args.admin
    hidden = args.hidden
    if positional and not uid and not name:
        uid = positional
        if admin is None and hidden is None:
            admin = True

    if admin is None and hidden is None:
        parser.error("Provide at least one of --admin/--no-admin or --hidden/--no-hidden")

    return argparse.Namespace(uid=uid, name=name, admin=admin, hidden=hidden)


def find_users_by_display_name(db, name: str):
    """Return [(uid, user_dict), ...] with case-insensitive display_name match."""
    needle = name.strip().lower()
    matches = []
    for doc in db.collection("users").stream():
        u = doc.to_dict() or {}
        display_name = u.get("display_name") or ""
        if display_name.lower() == needle:
            matches.append((doc.id, u))
    return matches


def resolve_user(db, uid=None, name=None):
    """Return (uid, user_dict) or print an error and exit."""
    if name:
        matches = find_users_by_display_name(db, name)
        if not matches:
            print(f"ERROR: No user with display_name matching '{name}'.")
            print("The user must sign in at least once before they can be updated.")
            sys.exit(1)
        if len(matches) > 1:
            print(f"ERROR: Multiple users match '{name}'. Use --uid instead.")
            for match_uid, _u in matches:
                print(f"  {match_uid}")
            sys.exit(1)
        return matches[0]

    doc_ref = db.collection("users").document(uid)
    snap = doc_ref.get()
    if not snap.exists:
        print(f"ERROR: No user document found for UID '{uid}'.")
        print("The user must sign in at least once before they can be promoted.")
        sys.exit(1)
    return uid, (snap.to_dict() or {})


def invalidate_list_caches(db):
    """Drop leaderboard, stats, and live caches so lists rebuild without hidden users."""
    backend_dir = Path(__file__).resolve().parent.parent / "march_madness_backend"
    backend_path = str(backend_dir)
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    from main import invalidate_leaderboard_and_stats

    invalidate_leaderboard_and_stats(db)


def apply_flags(db, uid, admin=None, hidden=None):
    """Update the given flags, invalidate list caches, return the resulting user dict."""
    update = {}
    if admin is not None:
        update["admin"] = bool(admin)
    if hidden is not None:
        update["hidden"] = bool(hidden)
    db.collection("users").document(uid).update(update)
    invalidate_list_caches(db)
    snap = db.collection("users").document(uid).get()
    return snap.to_dict() or {}


def print_result(uid, user_data):
    display_name = user_data.get("display_name", uid)
    admin = bool(user_data.get("admin", False))
    hidden = bool(user_data.get("hidden", False))
    print(f"SUCCESS: {display_name} ({uid}) admin={admin} hidden={hidden}")


def main(argv=None):
    args = parse_args(argv)
    db = _init()
    uid, _existing = resolve_user(db, uid=args.uid, name=args.name)
    user_data = apply_flags(db, uid, admin=args.admin, hidden=args.hidden)
    print_result(uid, user_data)


if __name__ == "__main__":
    main()
