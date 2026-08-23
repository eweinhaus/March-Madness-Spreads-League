#!/usr/bin/env python3
"""
Season reset script for Spread Pools.

Wipes Firestore collections for a clean start to a new season.
Requires explicit confirmation to prevent accidental data loss.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment from both repo root and backend directory
repo_root = Path(__file__).parent.parent
backend_dir = repo_root / "march_madness_backend"

# Try backend .env first, then repo root
load_dotenv(backend_dir / ".env")
load_dotenv(repo_root / ".env")

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


def get_firebase_project_id() -> str:
    """
    Extract Firebase project ID from credentials.
    
    Returns:
        str: Firebase project ID
    
    Raises:
        SystemExit: If project ID cannot be determined
    """
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path and os.path.exists(cred_path):
        import json
        try:
            with open(cred_path, 'r') as f:
                cred_data = json.load(f)
                project_id = cred_data.get("project_id")
                if project_id:
                    return project_id
        except Exception as e:
            print(f"Error reading credentials file: {e}")
    
    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if service_account_json:
        import json
        try:
            service_dict = json.loads(service_account_json)
            project_id = service_dict.get("project_id")
            if project_id:
                return project_id
        except Exception as e:
            print(f"Error parsing FIREBASE_SERVICE_ACCOUNT_JSON: {e}")
    
    print("Error: Cannot determine Firebase project ID from credentials.")
    print("Refusing to run without knowing which Firebase project will be affected.")
    sys.exit(1)


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
    league_id = os.getenv("LEAGUE_ID", "").strip()
    
    if not league_id:
        print("=" * 60)
        print("ERROR: LEAGUE_ID environment variable is not set or is empty.")
        print("=" * 60)
        print("\nPlease set LEAGUE_ID in your .env file (repo root or march_madness_backend/.env)")
        print("Example: LEAGUE_ID=football_2026")
        print("\nRefusing to run without a valid LEAGUE_ID.")
        sys.exit(1)
    
    # Get and display Firebase project ID BEFORE confirmation
    firebase_project_id = get_firebase_project_id()
    
    print("=" * 60)
    print("SPREAD POOLS SEASON RESET SCRIPT")
    print("=" * 60)
    print(f"\n⚠️  Firebase Project: {firebase_project_id}")
    print(f"⚠️  League ID: {league_id}")
    print(f"\nThis will DELETE ALL DATA from the following collections:")
    for coll in COLLECTIONS_TO_DELETE:
        print(f"  - {coll}")
    print("\n⚠️  THIS ACTION IS IRREVERSIBLE ⚠️")
    print("\nBefore proceeding:")
    print("  1. Ensure you have a backup if needed")
    print("  2. Verify the Firebase project ID matches your intended target")
    print("  3. Verify LEAGUE_ID matches the season you want to reset")
    print("  4. After reset, you must re-promote admin users with scripts/make_admin.py")
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
