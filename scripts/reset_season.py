#!/usr/bin/env python3
"""
Season reset script for Spread Pools.

Wipes Firestore collections for a clean start to a new season.
Requires explicit confirmation to prevent accidental data loss.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment before importing firebase_admin
load_dotenv()

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    print("Error: firebase-admin not installed. Run: pip install firebase-admin")
    sys.exit(1)

# Collections to wipe for a season reset
COLLECTIONS_TO_DELETE = [
    "users",
    "games",
    "picks",
    "tiebreakers",
    "tiebreaker_picks",
    "leaderboard",
    "_cache",
]


def init_firebase():
    """Initialize Firebase Admin SDK using environment credentials."""
    if firebase_admin._apps:
        return firestore.client()
    
    # Try GOOGLE_APPLICATION_CREDENTIALS path first
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        return firestore.client()
    
    # Try FIREBASE_SERVICE_ACCOUNT_JSON inline
    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if service_account_json:
        import json
        try:
            service_dict = json.loads(service_account_json)
            cred = credentials.Certificate(service_dict)
            firebase_admin.initialize_app(cred)
            return firestore.client()
        except json.JSONDecodeError:
            print("Error: FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON")
            sys.exit(1)
    
    print("Error: No Firebase credentials found.")
    print("Set GOOGLE_APPLICATION_CREDENTIALS or FIREBASE_SERVICE_ACCOUNT_JSON in .env")
    sys.exit(1)


def delete_collection(db, collection_name):
    """
    Delete all documents in a collection.
    
    Handles pagination for collections with >500 documents.
    """
    coll_ref = db.collection(collection_name)
    deleted = 0
    
    while True:
        # Firestore batch delete limit is 500
        docs = coll_ref.limit(500).stream()
        doc_list = list(docs)
        
        if not doc_list:
            break
        
        batch = db.batch()
        for doc in doc_list:
            batch.delete(doc.reference)
            deleted += 1
        
        batch.commit()
    
    return deleted


def main():
    league_id = os.getenv("LEAGUE_ID", "unknown")
    
    print("=" * 60)
    print("SPREAD POOLS SEASON RESET SCRIPT")
    print("=" * 60)
    print(f"\nCurrent LEAGUE_ID: {league_id}")
    print(f"\nThis will DELETE ALL DATA from the following collections:")
    for coll in COLLECTIONS_TO_DELETE:
        print(f"  - {coll}")
    print("\n⚠️  THIS ACTION IS IRREVERSIBLE ⚠️")
    print("\nBefore proceeding:")
    print("  1. Ensure you have a backup if needed")
    print("  2. Verify LEAGUE_ID matches the season you want to reset")
    print("  3. After reset, you must re-promote admin users with scripts/make_admin.py")
    print("\n" + "=" * 60)
    
    # Require exact confirmation
    confirmation = input(f"\nTo confirm, type exactly: RESET {league_id}\n> ")
    
    if confirmation != f"RESET {league_id}":
        print("\n❌ Confirmation did not match. Aborted.")
        sys.exit(0)
    
    print("\n🔥 Starting deletion...")
    
    try:
        db = init_firebase()
    except Exception as e:
        print(f"\n❌ Failed to initialize Firebase: {e}")
        sys.exit(1)
    
    total_deleted = 0
    
    for collection in COLLECTIONS_TO_DELETE:
        print(f"\nDeleting collection: {collection}...", end=" ", flush=True)
        try:
            count = delete_collection(db, collection)
            total_deleted += count
            print(f"✓ ({count} documents)")
        except Exception as e:
            print(f"✗ Failed: {e}")
    
    print("\n" + "=" * 60)
    print(f"✅ Season reset complete. Deleted {total_deleted} documents.")
    print("\nNext steps:")
    print("  1. Re-promote admin users: python scripts/make_admin.py <firebase-uid>")
    print("  2. Admins can now create games for the new season")
    print("=" * 60)


if __name__ == "__main__":
    main()
