import os
import json
import logging
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass

_app = None
_db = None


def _init_firebase():
    """Initialize Firebase Admin SDK using service account credentials."""
    global _app, _db

    if _app is not None:
        return

    import firebase_admin
    from firebase_admin import credentials, firestore

    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    cred_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

    if cred_json:
        info = json.loads(cred_json)
        cred = credentials.Certificate(info)
    elif cred_path:
        cred = credentials.Certificate(cred_path)
    else:
        raise RuntimeError(
            "Firebase credentials not configured. Set GOOGLE_APPLICATION_CREDENTIALS "
            "or FIREBASE_SERVICE_ACCOUNT_JSON."
        )

    _app = firebase_admin.initialize_app(cred)
    _db = firestore.client()
    logger.info("Firebase Admin SDK initialized successfully")


def get_db() -> Any:
    """Return the Firestore client, initializing on first call."""
    _init_firebase()
    return _db


def get_auth():
    """Return the firebase_admin.auth module (for verify_id_token etc.)."""
    _init_firebase()
    from firebase_admin import auth as firebase_auth

    return firebase_auth


_st = None


def server_timestamp():
    """Lazy-load Firestore SERVER_TIMESTAMP (avoids importing gRPC stack at module load)."""
    global _st
    if _st is None:
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP

        _st = SERVER_TIMESTAMP
    return _st


def check_firestore_health() -> bool:
    """Perform a cheap read to verify Firestore is reachable."""
    try:
        db = get_db()
        db.collection("_health").document("ping").get()
        return True
    except Exception as e:
        logger.error(f"Firestore health check failed: {e}")
        return False
