#!/usr/bin/env python3
"""
Promote a Firebase user to admin in Firestore.

Usage:
    python scripts/make_admin.py <firebase-uid>

The user must have signed in at least once (so their document exists in
the 'users' collection). Set GOOGLE_APPLICATION_CREDENTIALS or
FIREBASE_SERVICE_ACCOUNT_JSON before running.
"""

import sys
import os
import json

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


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <firebase-uid>")
        sys.exit(1)

    uid = sys.argv[1]
    db = _init()

    doc_ref = db.collection("users").document(uid)
    snap = doc_ref.get()

    if not snap.exists:
        print(f"ERROR: No user document found for UID '{uid}'.")
        print("The user must sign in at least once before they can be promoted.")
        sys.exit(1)

    doc_ref.update({"admin": True})
    user_data = doc_ref.get().to_dict()
    print(f"SUCCESS: {user_data.get('display_name', uid)} ({uid}) is now an admin.")


if __name__ == "__main__":
    main()
