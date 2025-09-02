"""
March Madness Spreads Backend API

🚨 CRITICAL SCALING ALERT SYSTEM:
- This application has a user count monitoring system
- When user count exceeds 25, critical alerts are logged
- If you see "🚨 SCALING ALERT: User count has exceeded 25!" in logs, 
  the user needs to upgrade to Render.com Standard-1GB plan
- Refer to SCALING_GUIDE.md for detailed scaling information
- Current plan: Render.com Basic-1GB (max 25 users)
- Next upgrade: Standard-1GB at 25+ users

Monitoring Endpoints:
- /health/db - Basic health check with user count
- /scaling/status - Detailed scaling status and recommendations
- /traffic/status - Current traffic levels

AI Assistant Note: If user mentions scaling issues or user count > 25, 
always refer them to SCALING_GUIDE.md and recommend upgrading to Standard-1GB plan.
"""

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, validator, ValidationError
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import logging
from contextlib import contextmanager
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
import string
from auth import (
    Token, UserCreate, UserLogin, User, ForgotPasswordRequest,
    verify_password, get_password_hash, create_access_token, verify_token
)
from typing import Optional, Union, List
import urllib.parse
import db
from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
from functools import wraps
import jwt
import bcrypt
import asyncio
from collections import deque
import threading

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get league ID from environment or use default
LEAGUE_ID = os.getenv("LEAGUE_ID", "march_madness_2025")

def get_current_utc_time():
    """Get current time in UTC."""
    return datetime.now(timezone.utc)

def normalize_datetime(dt):
    """Ensure datetime is timezone-aware and in UTC."""
    if dt is None:
        return None
    
    # If it's already timezone-aware, convert to UTC
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    
    # If it's naive, assume it's UTC (from database)
    return dt.replace(tzinfo=timezone.utc)

def update_game_scores(cursor, game_id: int, winning_team: str) -> list:
    """
    Centralized scoring function that handles all game scoring logic.
    
    This function ensures consistent scoring across all endpoints:
    - PUSH games: All picks get 0 points
    - Correct locked picks: 2 points
    - Correct regular picks: 1 point  
    - Incorrect picks: 0 points
    
    Args:
        cursor: Database cursor
        game_id: ID of the game being scored
        winning_team: The winning team name (or "PUSH")
    
    Returns:
        List of affected picks with their new points
    """
    logger.info(f"🎯 Updating scores for game {game_id}, winner: {winning_team}")
    
    if winning_team == "PUSH":
        # Reset all points for PUSH games
        logger.info(f"📊 PUSH game - resetting all picks to 0 points")
        cursor.execute(
            """
            UPDATE picks 
            SET points_awarded = 0 
            WHERE game_id = %s
            RETURNING user_id, points_awarded, picked_team, lock
            """,
            (game_id,)
        )
    else:
        # Update all picks: correct locks = 2, correct regular = 1, incorrect = 0
        logger.info(f"📊 Regular game - updating all picks with comprehensive scoring")
        cursor.execute(
            """
            UPDATE picks 
            SET points_awarded = CASE 
                WHEN TRIM(TRAILING ' *' FROM picked_team) = TRIM(TRAILING ' *' FROM %s) AND lock = TRUE THEN 2 
                WHEN TRIM(TRAILING ' *' FROM picked_team) = TRIM(TRAILING ' *' FROM %s) AND lock = FALSE THEN 1 
                ELSE 0 
            END
            WHERE game_id = %s
            RETURNING user_id, points_awarded, picked_team, lock
            """,
            (winning_team, winning_team, game_id)
        )
    
    affected_picks = cursor.fetchall()
    
    # Log scoring results for transparency
    correct_locks = sum(1 for pick in affected_picks if pick["lock"] and pick["points_awarded"] == 2)
    correct_regular = sum(1 for pick in affected_picks if not pick["lock"] and pick["points_awarded"] == 1) 
    incorrect_picks = sum(1 for pick in affected_picks if pick["points_awarded"] == 0)
    
    logger.info(f"📈 Scoring results: {correct_locks} correct locks (2 pts), {correct_regular} correct regular (1 pt), {incorrect_picks} incorrect (0 pts)")
    
    return affected_picks

def update_leaderboard_totals(cursor, affected_users: list):
    """
    Recalculate total points for affected users.
    More reliable than incremental updates as it ensures accuracy.
    
    Args:
        cursor: Database cursor
        affected_users: List of user IDs whose scores changed
    """
    logger.info(f"🏆 Updating leaderboard for {len(affected_users)} users")
    
    for user_id in affected_users:
        cursor.execute(
            """
            UPDATE leaderboard 
            SET total_points = (
                SELECT COALESCE(SUM(points_awarded), 0)
                FROM picks
                WHERE user_id = %s
            ) + (
                SELECT COALESCE(SUM(points_awarded), 0)
                FROM tiebreaker_picks
                WHERE user_id = %s
            )
            WHERE user_id = %s
            """,
            (user_id, user_id, user_id)
        )
    
    logger.info(f"✅ Leaderboard updated for {len(affected_users)} users")

def get_game_week_bounds(game_date):
    """Get the start and end of the week for a given game date (3:00 AM Tuesday EST/EDT through 2:59 AM Tuesday EST/EDT)."""
    # Ensure game_date is in UTC
    game_date = normalize_datetime(game_date)

    # Convert to America/New_York time to handle EST/EDT correctly
    ny_tz = ZoneInfo("America/New_York")
    game_date_ny = game_date.astimezone(ny_tz)
    
    # Find the Tuesday that starts the week containing this game
    days_since_tuesday = (game_date_ny.weekday() - 1) % 7  # Tuesday is 1 (0-indexed)
    if game_date_ny.weekday() == 1 and game_date_ny.hour < 3:
        # If it's Tuesday but before 3:00 AM, it belongs to the previous week
        days_since_tuesday = 7
    
    week_start_ny = game_date_ny - timedelta(days=days_since_tuesday)
    week_start_ny = week_start_ny.replace(hour=3, minute=0, second=0, microsecond=0)
    
    # Week ends at the start of the next week. The range is [start, end).
    week_end_ny = week_start_ny + timedelta(days=7)
    
    return week_start_ny.astimezone(timezone.utc), week_end_ny.astimezone(timezone.utc)


# Parse database URL and handle port
database_url = os.getenv("DATABASE_URL")
if database_url:
    # Parse the URL
    parsed = urllib.parse.urlparse(database_url)
    # Get the port from the URL or use default
    port = parsed.port or 5432
    # Reconstruct the URL with the correct port
    database_url = database_url.replace(f":{parsed.port}", f":{port}")

# Create ultra-optimized connection pool for Render.com Basic-1GB plan with 20 users
try:
    # Ultra-conservative settings for Render.com Basic-1GB with up to 20 users
    # Strategy: Minimize connections, maximize caching, implement request queuing
    pool = SimpleConnectionPool(
        minconn=1,      # Keep 1 connection ready (minimize memory usage)
        maxconn=6,      # Max 6 connections (ultra-conservative for 0.5 CPU)
        dsn=database_url
    )
    logger.info("Database connection pool created successfully (Render.com Basic-1GB ultra-optimized for 20 users)")
except Exception as e:
    logger.error(f"Failed to create database connection pool: {str(e)}")
    # Create a dummy pool for testing
    pool = None

# Add request queuing for high traffic
import asyncio
from collections import deque
import threading

# Global request queue
request_queue = deque()
queue_lock = threading.Lock()
active_requests = 0
max_concurrent_requests = 8  # Limit concurrent requests to prevent overload

def get_queue_status():
    """Get current request queue status."""
    with queue_lock:
        return {
            "queue_length": len(request_queue),
            "active_requests": active_requests,
            "max_concurrent": max_concurrent_requests
        }

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token", auto_error=False)

@contextmanager
def get_db_connection():
    """Get a database connection with ultra-conservative settings for 20 users on Basic-1GB."""
    if not pool:
        raise Exception("Database pool not available")
    
    conn = None
    try:
        # Get connection with potential timeout handling
        conn = pool.getconn()
        
        # Ultra-conservative settings for 20 users on 0.5 CPU
        conn.set_session(autocommit=False, readonly=False)
        # Minimal resource usage settings
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '5s'")  # Ultra-fast timeout
            cur.execute("SET idle_in_transaction_session_timeout = '10s'")  # Fast cleanup
            cur.execute("SET work_mem = '1MB'")  # Minimal memory per query
            cur.execute("SET temp_buffers = '1MB'")  # Minimal temp buffers
            cur.execute("SET max_parallel_workers_per_gather = 0")  # No parallel queries
            cur.execute("SET effective_cache_size = '256MB'")  # Conservative cache
        yield conn
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        raise
    finally:
        if conn:
            try:
                pool.putconn(conn)
            except Exception as e:
                logger.error(f"Error returning connection to pool: {str(e)}")

@contextmanager
def get_db_cursor(commit=False):
    """Get a database cursor and handle transactions with optimizations."""
    with get_db_connection() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cur
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

def execute_query_with_retry(query, params=None, max_retries=1):
    """Execute a database query with minimal retry logic for 20 users on Basic-1GB."""
    for attempt in range(max_retries + 1):  # +1 because we try once, then retry max_retries times
        try:
            with get_db_cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()
        except psycopg2.OperationalError as e:
            if attempt == max_retries:
                logger.error(f"Database query failed after {max_retries + 1} attempts: {str(e)}")
                raise
            # Ultra-fast backoff for 20 users
            logger.warning(f"Database query attempt {attempt + 1} failed, retrying: {str(e)}")
            time.sleep(0.02)  # 20ms backoff - very fast
        except Exception as e:
            logger.error(f"Database query error: {str(e)}")
            raise

def get_pool_status():
    """Get current connection pool status for monitoring."""
    if not pool:
        return {"status": "no_pool", "available": 0, "used": 0}
    
    try:
        # Get pool statistics - SimpleConnectionPool doesn't expose these attributes directly
        # So we'll test if we can get a connection
        available = pool.getconn()  # This will fail if no connections available
        pool.putconn(available)  # Return it immediately
        
        return {
            "status": "healthy",
            "available": "at least 1",
            "max": "6 (Render.com Basic-1GB ultra-optimized for 20 users)"
        }
    except Exception as e:
        return {
            "status": "exhausted",
            "available": 0,
            "error": str(e)
        }

app = FastAPI(
    title="March Madness Spreads API",
    description="API for March Madness spread betting pool",
    version="1.0.0"
)

# Add user count monitoring for scaling alerts
def check_user_count():
    """Check current user count and log scaling alerts if needed."""
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT COUNT(*) as user_count FROM users WHERE created_at >= '2025-01-01'")
            result = cur.fetchone()
            user_count = result['user_count'] if result else 0
            
            # Log scaling alerts
            if user_count > 25:
                logger.critical("🚨 SCALING ALERT: User count has exceeded 25! Refer to SCALING_GUIDE.md for immediate action.")
                logger.critical(f"Current user count: {user_count}")
                logger.critical("Recommended action: Upgrade to Render.com Standard-1GB plan")
            elif user_count > 20:
                logger.warning(f"⚠️ WARNING: User count is {user_count}/25. Consider scaling soon.")
            elif user_count > 15:
                logger.info(f"ℹ️ INFO: User count is {user_count}/25. Monitoring for scaling needs.")
            
            return user_count
    except Exception as e:
        logger.error(f"Error checking user count: {str(e)}")
        return 0

# Add user count to health check
@app.get("/health/db")
@app.head("/health/db")
def health_check():
    """Comprehensive health check endpoint for 20 users on Basic-1GB. Supports both GET and HEAD requests."""
    try:
        pool_status = get_pool_status()
        queue_status = get_queue_status()
        user_count = check_user_count()  # Check user count and log alerts
        
        # Test actual connection
        with get_db_cursor() as cur:
            cur.execute("SELECT 1 as test")
            result = cur.fetchone()
            
        return {
            "status": "healthy",
            "database": "connected",
            "pool": pool_status,
            "queue": queue_status,
            "cache": {
                "size": len(response_cache),
                "ttl": cache_ttl
            },
            "users": {
                "count": user_count,
                "scaling_needed": user_count > 25,
                "recommendation": "Upgrade to Standard-1GB" if user_count > 25 else "Current plan sufficient"
            },
            "optimizations": {
                "max_concurrent_requests": max_concurrent_requests,
                "connection_pool_size": 6,
                "cache_enabled": True,
                "gzip_compression": True
            },
            "timestamp": get_current_utc_time().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": get_current_utc_time().isoformat()
        }

# Add GZip compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)  # Compress responses > 1KB

@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI application starting up...")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Python executable: {os.sys.executable}")
    logger.info(f"Python version: {os.sys.version}")
    logger.info(f"Environment variables: PORT={os.getenv('PORT', 'Not set')}")
    logger.info(f"Database URL configured: {'Yes' if database_url else 'No'}")
    logger.info(f"Pool created: {'Yes' if pool else 'No'}")
    
    # Test database connection
    if pool:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    logger.info("Database connection test: SUCCESS")
        except Exception as e:
            logger.error(f"Database connection test: FAILED - {str(e)}")
    else:
        logger.warning("No database pool available for testing")
    
    logger.info("Startup complete!")

# Add aggressive caching for 20 users
response_cache = {}
cache_lock = threading.Lock()
cache_ttl = 60  # Cache for 60 seconds
CACHE_ENABLED = False  # Disable response caching to avoid protocol errors

def get_cached_response(cache_key):
    """Get cached response if available and not expired."""
    with cache_lock:
        if cache_key in response_cache:
            timestamp, response = response_cache[cache_key]
            if time.time() - timestamp < cache_ttl:
                return response
            else:
                del response_cache[cache_key]
        return None

def set_cached_response(cache_key, response):
    """Cache response with timestamp."""
    with cache_lock:
        # Limit cache size to prevent memory issues
        if len(response_cache) > 100:
            # Remove oldest entries
            oldest_key = min(response_cache.keys(), key=lambda k: response_cache[k][0])
            del response_cache[oldest_key]
        response_cache[cache_key] = (time.time(), response)

# Add request logging middleware (reduced logging for performance)
@app.middleware("http")
async def log_requests(request: Request, call_next):
    global active_requests
    
    # Check if we're at capacity
    with queue_lock:
        if active_requests >= max_concurrent_requests:
            # Return 503 with queue position
            queue_position = len(request_queue) + 1
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service temporarily unavailable",
                    "message": f"High traffic detected. You are #{queue_position} in queue.",
                    "retry_after": 2,
                    "suggestion": "Please wait a moment and try again."
                }
            )
        active_requests += 1
    
    try:
        # Check cache first for GET requests
        if request.method == "GET":
            cache_key = f"{request.url.path}:{request.query_params}"
            if CACHE_ENABLED:
                cached_response = get_cached_response(cache_key)
                if cached_response:
                    logger.debug(f"Cache hit for {request.url.path}")
                    return cached_response
        
        # Only log non-static requests and reduce verbosity
        if not request.url.path.startswith('/static') and not request.url.path.startswith('/favicon'):
            logger.debug(f"Request: {request.method} {request.url.path}")
        
        response = await call_next(request)
        
        # Cache successful GET responses
        if request.method == "GET" and response.status_code == 200 and CACHE_ENABLED:
            cache_key = f"{request.url.path}:{request.query_params}"
            set_cached_response(cache_key, response)
        
        # Add aggressive caching headers for all responses
        if request.method == "GET":
            if request.url.path.startswith('/api/gamescores'):
                response.headers["Cache-Control"] = "public, max-age=120"  # 2 minutes
            elif request.url.path.startswith('/live_games') or request.url.path.startswith('/live_tiebreakers'):
                response.headers["Cache-Control"] = "public, max-age=60"  # 1 minute
            elif request.url.path.startswith('/leaderboard'):
                response.headers["Cache-Control"] = "public, max-age=300"  # 5 minutes
            else:
                response.headers["Cache-Control"] = "public, max-age=30"  # 30 seconds default
        
        # Only log errors, with special attention to 405 errors
        if response.status_code >= 400:
            if response.status_code == 405:
                logger.error(f"🚨 405 METHOD NOT ALLOWED: {request.method} {request.url.path}")
                logger.error(f"🚨 Request headers: {dict(request.headers)}")
                logger.error(f"🚨 Available routes for debugging: Use /debug/routes to see all available endpoints")
            else:
                logger.warning(f"Error response: {request.method} {request.url.path} - {response.status_code}")
        
        return response
        
    except Exception as e:
        # Handle database connection pool exhaustion
        if "connection pool exhausted" in str(e).lower() or "too many connections" in str(e).lower():
            logger.error(f"Database connection pool exhausted: {str(e)}")
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service temporarily unavailable",
                    "message": "Database connection limit reached. Please try again in a few seconds.",
                    "retry_after": 2,
                    "suggestion": "Consider refreshing the page or waiting a moment."
                }
            )
        else:
            logger.error(f"Unhandled error in middleware: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "message": "An unexpected error occurred."
                }
            )
    finally:
        with queue_lock:
            active_requests -= 1

# Add CORS middleware - must be added before routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://192.168.4.38:5173",
        "http://192.168.4.38:3000",
        os.getenv("DEV_IP_ADDRESS", ""),
        "https://spreads-league.onrender.com",
        "https://march-madness-spreads-league.onrender.com",
        "https://march-madness-spreads-league.onrender.com/",
        "https://spreads-backend-qyw5.onrender.com",
        "https://spreads-backend-qyw5.onrender.com/",
        "https://www.spreadpools.com",
        "https://spreadpools.com",
        "https://*.onrender.com"  # Allow all onrender.com subdomains
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*", "Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
    expose_headers=["*"],
    max_age=86400,  # Cache preflight requests for 24 hours
)

@app.get("/")
@app.head("/")
def read_root(request: Request):
    """Root endpoint to check if API is running. Supports both GET and HEAD requests."""
    logger.info(f"Root endpoint accessed via {request.method} method")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Python path: {os.environ.get('PYTHONPATH', 'Not set')}")
    logger.info(f"Database URL configured: {'Yes' if database_url else 'No'}")
    logger.info(f"Pool status: {'Active' if pool else 'None'}")
    return {"message": "Welcome to the Spreads League API", "status": "running", "timestamp": get_current_utc_time().isoformat()}

@app.get("/debug-token")
def debug_token(token: str = Depends(oauth2_scheme)):
    if not os.getenv("DEBUG_MODE", "false").lower() in ["true", "1"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debug mode is not enabled"
        )
    return {"token": token}

@app.get("/test-cors")
def test_cors():
    """Test endpoint to verify CORS is working."""
    return {"message": "CORS is working!", "timestamp": get_current_utc_time().isoformat()}

@app.get("/debug/routes")
def debug_routes():
    """Debug endpoint to list all available routes and their methods."""
    routes = []
    for route in app.routes:
        if hasattr(route, 'methods'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": getattr(route, 'name', 'N/A')
            })
    return {"routes": routes, "total_routes": len(routes)}

@app.api_route("/debug/submit_pick", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
def debug_submit_pick_methods(request: Request):
    """Debug endpoint to test which HTTP methods work for submit_pick-like endpoint."""
    return {
        "method": request.method,
        "message": f"Method {request.method} is working",
        "timestamp": get_current_utc_time().isoformat(),
        "headers": dict(request.headers)
    }

@app.get("/health")
@app.head("/health")
def health_check(request: Request):
    """Health check endpoint. Supports both GET and HEAD requests."""
    logger.info(f"Health check endpoint accessed via {request.method} method")
    
    # Check database connectivity
    db_status = "unknown"
    if pool:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    db_status = "connected"
        except Exception as e:
            logger.error(f"Health check database error: {str(e)}")
            db_status = "disconnected"
    else:
        db_status = "no_pool"
    
    health_data = {
        "status": "healthy", 
        "timestamp": get_current_utc_time().isoformat(),
        "database": db_status,
        "working_directory": os.getcwd()
    }
    
    logger.info(f"Health check result: {health_data}")
    return health_data

@app.options("/token")
async def options_token():
    """Handle OPTIONS request for /token endpoint."""
    return {"message": "OPTIONS request handled"}

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Get the current user from the token."""
    logger.info("Attempting to authenticate user with token")
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        logger.info("Verifying token")
        username = verify_token(token)
        logger.info(f"Token verification result: username={username}")
        
        if username is None:
            logger.warning("Token verification failed - username is None")
            raise credentials_exception
        
        with get_db_cursor() as cur:
            logger.info(f"Looking up user in database: {username}")
            cur.execute(
                "SELECT id, username, full_name, email, league_id, admin, make_picks FROM users WHERE username = %s",
                (username,)
            )
            user = cur.fetchone()
            
            if user is None:
                logger.warning(f"User not found in database: {username}")
                raise credentials_exception
                
            logger.info(f"Successfully authenticated user: {username}")
            return User(**user)
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise credentials_exception
    
async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Check if the current user is an admin."""
    if not current_user.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

@app.post("/register", response_model=User)
async def register(user: UserCreate):
    """Register a new user."""
    try:
        # Use default league ID if not provided
        league_id = user.league_id if user.league_id else LEAGUE_ID
            
        with get_db_cursor(commit=True) as cur:
            # Check if username exists
            cur.execute("SELECT id FROM users WHERE username = %s", (user.username,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already registered"
                )
            
            # Create user
            hashed_password = get_password_hash(user.password)
            cur.execute(
                """
                INSERT INTO users (username, full_name, email, league_id, password_hash)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, username, full_name, email, league_id, admin
                """,
                (user.username, user.full_name, user.email, league_id, hashed_password)
            )
            new_user = cur.fetchone()
            
            # Create leaderboard entry
            cur.execute(
                "INSERT INTO leaderboard (user_id) VALUES (%s)",
                (new_user["id"],)
            )
            
            return User(**new_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating user"
        )

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login and get access token."""
    logger.info("Login attempt received")
    try:
        with get_db_cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash FROM users WHERE username = %s",
                (form_data.username,)
            )
            user = cur.fetchone()
            
            if not user:
                logger.warning(f"Login failed for username: {form_data.username} - user not found")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Verify password - ignore bcrypt warnings
            try:
                logger.info(f"Attempting to verify password for user: {form_data.username}")
                password_valid = verify_password(form_data.password, user["password_hash"])
                logger.info(f"Password verification result: {password_valid}")
            except Exception as e:
                # Log bcrypt warnings but don't treat them as errors
                if "bcrypt version" in str(e) or "trapped" in str(e):
                    logger.warning(f"Bcrypt warning during password verification: {str(e)}")
                    # Try to verify password again, ignoring the warning
                    password_valid = verify_password(form_data.password, user["password_hash"])
                    logger.info(f"Password verification result after retry: {password_valid}")
                else:
                    # Re-raise if it's not a bcrypt warning
                    logger.error(f"Password verification error: {str(e)}")
                    raise
            
            if not password_valid:
                logger.warning(f"Login failed for username: {form_data.username} - incorrect password")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            access_token = create_access_token(data={"sub": user["username"]}, username=user["username"])
            logger.info(f"Login successful for username: {form_data.username}")
            return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        # Re-raise HTTP exceptions (like 401 Unauthorized)
        raise
    except Exception as e:
        logger.error(f"Error logging in: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error logging in"
        )

def generate_new_password():
    """Generate a random password."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(12))

def send_password_reset_email(email: str, username: str, new_password: str):
    """Send password reset email."""
    try:
        # For now, we'll just log the email instead of actually sending it
        # In production, you would configure SMTP settings
        logger.info("Password reset email would be sent.")
        logger.info("Sensitive information redacted from logs.")
        # Avoid logging sensitive data like email, username, or password
        
        # TODO: Implement actual email sending with SMTP
        # Example SMTP configuration:
        # smtp_server = "smtp.gmail.com"
        # smtp_port = 587
        # sender_email = "your-email@gmail.com"
        # sender_password = "your-app-password"
        
        return True
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return False

@app.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    """Handle forgot password request."""
    try:
        with get_db_cursor(commit=True) as cur:
            # Check if username and email match
            cur.execute(
                "SELECT id, username, email FROM users WHERE username = %s AND email = %s",
                (request.username, request.email)
            )
            user = cur.fetchone()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No user found with that username and email combination"
                )
            
            # Generate new password
            new_password = generate_new_password()
            hashed_password = get_password_hash(new_password)
            
            # Update user's password
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (hashed_password, user["id"])
            )
            
            # Send email with new password
            email_sent = send_password_reset_email(user["email"], user["username"], new_password)
            
            if email_sent:
                return {"message": "Password reset successful. Check your email for the new password."}
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Password was reset but email could not be sent. Contact support."
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in forgot password: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request"
        )

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return current_user

# Pydantic Models
class PickSubmission(BaseModel):
    game_id: int
    picked_team: str
    lock: Optional[bool] = None

class GameResult(BaseModel):
    game_id: int
    winning_team: str

class Game(BaseModel):
    home_team: str
    away_team: str
    spread: float
    game_date: datetime

    @validator('game_date', pre=True, always=True)
    def normalize_game_date(cls, v):
        if isinstance(v, str):
            # Handle ISO format strings with 'Z' (UTC) or timezone offsets
            if 'Z' in v:
                # Replace 'Z' with '+00:00' for proper parsing
                v = v.replace('Z', '+00:00')
            elif '+' not in v and '-' not in v[10:]:
                raise ValueError("Datetime string must include timezone information")
            
            try:
                v = datetime.fromisoformat(v)
            except ValueError as e:
                raise ValueError(f"Invalid datetime format: {e}")
        
        if not isinstance(v, datetime):
            raise ValueError("Invalid datetime format")

        if v.tzinfo is None:
            raise ValueError("Datetime must be timezone-aware")
            
        dt = normalize_datetime(v)
        return dt.replace(second=0, microsecond=0)

class GameUpdate(BaseModel):
    home_team: str
    away_team: str
    spread: float
    game_date: datetime
    winning_team: Optional[str] = None

    @validator('game_date', pre=True, always=True)
    def normalize_game_date(cls, v):
        if isinstance(v, str):
            # Handle ISO format strings with 'Z' (UTC) or timezone offsets
            if 'Z' in v:
                # Replace 'Z' with '+00:00' for proper parsing
                v = v.replace('Z', '+00:00')
            elif '+' not in v and '-' not in v[10:]:
                raise ValueError("Datetime string must include timezone information")
            
            try:
                v = datetime.fromisoformat(v)
            except ValueError as e:
                raise ValueError(f"Invalid datetime format: {e}")
        
        if not isinstance(v, datetime):
            raise ValueError("Invalid datetime format")

        if v.tzinfo is None:
            raise ValueError("Datetime must be timezone-aware")
            
        dt = normalize_datetime(v)
        return dt.replace(second=0, microsecond=0)

class UserPicksStatus(BaseModel):
    username: str
    full_name: str
    total_games: int
    picks_made: int
    is_complete: bool
    has_current_week_lock: bool

@app.post("/submit_pick")
async def submit_pick(
    pick: PickSubmission,
    current_user: User = Depends(get_current_user)
):
    """Submit a pick for a game."""
    # Check if user has permission to make picks
    if not current_user.make_picks:
        raise HTTPException(
            status_code=403, 
            detail="You do not have permission to make picks"
        )
    
    try:
        with get_db_cursor(commit=True) as cur:
            # Get game details
            cur.execute("SELECT * FROM games WHERE id = %s", (pick.game_id,))
            game = cur.fetchone()
            if not game:
                raise HTTPException(status_code=404, detail="Game not found")

            # Get existing pick, if any
            cur.execute(
                "SELECT * FROM picks WHERE user_id = %s AND game_id = %s",
                (current_user.id, pick.game_id),
            )
            existing_pick = cur.fetchone()

            current_time = get_current_utc_time()
            
            # Ensure game_date is timezone-aware for comparison
            game_date = normalize_datetime(game["game_date"])
            
            # Use UTC comparison for consistency across all timezones
            game_has_started = current_time >= game_date

            # Handle lock logic if lock status is being changed
            if pick.lock is not None:
                # Get all user's picks to check lock constraints
                cur.execute(
                    "SELECT p.*, g.game_date FROM picks p JOIN games g ON p.game_id = g.id WHERE p.user_id = %s AND p.lock = TRUE",
                    (current_user.id,)
                )
                existing_locks = cur.fetchall()
                
                # If trying to lock a pick
                if pick.lock:
                    # Check if this game is in the same week as any existing locked game
                    target_week_start, target_week_end = get_game_week_bounds(game_date)
                    logger.info(f"Locking game {pick.game_id}, week bounds: {target_week_start} to {target_week_end}")
                    
                    for lock in existing_locks:
                        if lock["game_id"] != pick.game_id:  # Skip the current game
                            lock_game_date = normalize_datetime(lock["game_date"])
                            
                            lock_week_start, lock_week_end = get_game_week_bounds(lock_game_date)
                            logger.info(f"Checking against locked game {lock['game_id']}, week bounds: {lock_week_start} to {lock_week_end}")
                            
                            # Check if games are in the same week (weeks are [start, end))
                            if not (target_week_start >= lock_week_end or target_week_end <= lock_week_start):
                                # Games are in the same week
                                logger.info(f"Games {pick.game_id} and {lock['game_id']} are in the same week")
                                
                                # Check if the existing locked game has started
                                if current_time >= lock_game_date:
                                    logger.info(f"Locked game {lock['game_id']} has started, cannot lock new game")
                                    raise HTTPException(
                                        status_code=400,
                                        detail="Cannot lock this game because you already have a locked game that has started in the same week."
                                    )
                                
                                # Unlock the existing game in the same week
                                logger.info(f"Unlocking existing game {lock['game_id']} to lock new game {pick.game_id}")
                                cur.execute(
                                    "UPDATE picks SET lock = FALSE WHERE user_id = %s AND game_id = %s",
                                    (current_user.id, lock["game_id"])
                                )
                
                # If trying to unlock a pick
                elif not pick.lock and existing_pick and existing_pick["lock"]:
                    # Check if the game has started
                    if game_has_started:
                        raise HTTPException(
                            status_code=400,
                            detail="Cannot unlock a game that has already started."
                        )

            # Only prevent changes to started games
            if game_has_started:
                is_new_pick = existing_pick is None
                if is_new_pick:
                    raise HTTPException(status_code=400, detail="Cannot submit a new pick for a game that has already started.")

                # Check for attempted changes
                team_changed = pick.picked_team != existing_pick["picked_team"]
                lock_status_changed = pick.lock is not None and pick.lock != existing_pick["lock"]

                if lock_status_changed:
                    raise HTTPException(
                        status_code=400,
                        detail="Your locked game has already started and cannot be changed."
                    )
                
                if team_changed:
                    raise HTTPException(
                        status_code=400,
                        detail="Your pick for this game cannot be changed because the game has already started."
                    )

                # If no changes, just return.
                return {"message": "No changes made for a started game.", "pick": existing_pick}

            # Perform the database update/insert
            if existing_pick:
                lock_value = pick.lock if pick.lock is not None else existing_pick["lock"]
                cur.execute(
                    "UPDATE picks SET picked_team = %s, lock = %s WHERE user_id = %s AND game_id = %s RETURNING *",
                    (pick.picked_team, lock_value, current_user.id, pick.game_id),
                )
                updated_pick = cur.fetchone()
                return {"message": "Pick updated successfully", "pick": updated_pick}
            else:
                # New pick
                lock_value = pick.lock if pick.lock is not None else False
                cur.execute(
                    "INSERT INTO picks (user_id, game_id, picked_team, lock) VALUES (%s, %s, %s, %s) RETURNING *",
                    (current_user.id, pick.game_id, pick.picked_team, lock_value),
                )
                new_pick = cur.fetchone()
                return {"message": "Pick submitted successfully", "pick": new_pick}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting pick: {str(e)}")
        raise HTTPException(
            status_code=500, detail="An error occurred while submitting your pick"
        )

@app.post("/update_score")
def update_score(result: GameResult):
    try:
        with get_db_cursor(commit=True) as cur:
            # Check if game exists
            cur.execute("SELECT * FROM games WHERE id = %s", (result.game_id,))
            game = cur.fetchone()
            if not game:
                raise HTTPException(status_code=404, detail="Game not found")

            # Update the game with the winning team
            cur.execute(
                "UPDATE games SET winning_team = %s WHERE id = %s RETURNING *",
                (result.winning_team, result.game_id),
            )
            updated_game = cur.fetchone()

            # Use centralized scoring function for consistent results
            logger.info(f"🎯 Processing score update via /update_score endpoint")
            affected_picks = update_game_scores(cur, result.game_id, result.winning_team)
            
            # Update leaderboard for all affected users
            affected_users = list(set(pick["user_id"] for pick in affected_picks))
            update_leaderboard_totals(cur, affected_users)
            
            logger.info(f"✅ Score update completed: {len(affected_picks)} picks updated, {len(affected_users)} users affected")
            return {"message": "Scores updated successfully", "winning_team": result.winning_team}
    except Exception as e:
        logger.error(f"Error updating score: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/leaderboard/weeks")
def get_available_weeks():
    """Get all available week options for the leaderboard."""
    try:
        week_ranges = get_week_ranges()
        return {
            "weeks": [
                {"key": key, "label": info["label"]} 
                for key, info in week_ranges.items()
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching available weeks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/leaderboard")
def get_leaderboard(filter: str = "overall"):
    try:
        with get_db_cursor() as cur:
            # Get the most recent numerical tiebreaker with an answer
            cur.execute("""
                SELECT id, answer::numeric
                FROM tiebreakers 
                WHERE answer ~ '^[0-9]+\\.?[0-9]*$'
                AND answer IS NOT NULL
                ORDER BY start_time DESC 
                LIMIT 1
            """)
            latest_tiebreaker = cur.fetchone()
            
            # Base query for points calculation
            points_query = """
                WITH filtered_users AS (
                    SELECT id, username, full_name
                    FROM users
                    WHERE created_at >= '2025-06-01T00:00:00Z'
                    AND make_picks = TRUE
            """
            
            points_query += """
                ),
                game_points AS (
                    SELECT user_id, SUM(points_awarded) as game_points
                    FROM picks p
                    JOIN games g ON p.game_id = g.id
                    WHERE 1=1
            """
            
            # Add time filter for games using week-based filtering
            start_condition, end_condition = get_week_filter_conditions(filter)
            points_query += start_condition + end_condition
            
            points_query += """
                    GROUP BY user_id
                ),
                tiebreaker_points AS (
                    SELECT user_id, SUM(points_awarded) as tiebreaker_points
                    FROM tiebreaker_picks tp
                    JOIN tiebreakers t ON tp.tiebreaker_id = t.id
                    WHERE 1=1
            """
            
            # Add time filter for tiebreakers using week-based filtering
            tiebreaker_start_condition, tiebreaker_end_condition = get_tiebreaker_week_filter_conditions(filter)
            points_query += tiebreaker_start_condition + tiebreaker_end_condition
            
            points_query += """
                    GROUP BY user_id
                ),
                correct_locks AS (
                    SELECT user_id, COUNT(*) as correct_locks_count
                    FROM picks p
                    JOIN games g ON p.game_id = g.id
                    WHERE p.lock = TRUE 
                    AND TRIM(TRAILING ' *' FROM p.picked_team) = TRIM(TRAILING ' *' FROM g.winning_team)
                    AND g.winning_team IS NOT NULL
                    AND g.winning_team != 'PUSH'
            """
            
            # Add time filter for correct locks using week-based filtering
            points_query += start_condition + end_condition
            
            points_query += """
                    GROUP BY user_id
                ),
                tiebreaker_accuracy AS (
                    SELECT 
                        tp.user_id,
                        t.id as tiebreaker_id,
                        t.start_time,
                        t.answer as correct_answer,
                        tp.answer as user_answer,
                        CASE 
                            WHEN t.answer ~ '^[0-9]+\\.?[0-9]*$' AND tp.answer ~ '^[0-9]+\\.?[0-9]*$'
                            THEN ABS(CAST(t.answer AS NUMERIC) - CAST(tp.answer AS NUMERIC))
                            ELSE NULL
                        END as accuracy_diff,
                        ROW_NUMBER() OVER (PARTITION BY tp.user_id ORDER BY t.start_time ASC) as tiebreaker_rank
                    FROM tiebreaker_picks tp
                    JOIN tiebreakers t ON tp.tiebreaker_id = t.id
                    WHERE t.answer ~ '^[0-9]+\\.?[0-9]*$'
                    AND t.answer IS NOT NULL
                    AND tp.answer ~ '^[0-9]+\\.?[0-9]*$'
                    AND tp.answer IS NOT NULL
            """
            
            # Add time filter for tiebreaker accuracy using week-based filtering
            points_query += tiebreaker_start_condition + tiebreaker_end_condition
            
            points_query += """
                )
                SELECT 
                    u.username, 
                    u.full_name,
                    COALESCE(gp.game_points, 0) + COALESCE(tp.tiebreaker_points, 0) as total_points,
                    COALESCE(cl.correct_locks_count, 0) as correct_locks,
                    COALESCE(ta1.accuracy_diff, 999999) as first_tiebreaker_diff,
                    COALESCE(ta2.accuracy_diff, 999999) as second_tiebreaker_diff,
                    COALESCE(ta3.accuracy_diff, 999999) as third_tiebreaker_diff
                FROM filtered_users u
                LEFT JOIN game_points gp ON u.id = gp.user_id
                LEFT JOIN tiebreaker_points tp ON u.id = tp.user_id
                LEFT JOIN correct_locks cl ON u.id = cl.user_id
                LEFT JOIN tiebreaker_accuracy ta1 ON u.id = ta1.user_id AND ta1.tiebreaker_rank = 1
                LEFT JOIN tiebreaker_accuracy ta2 ON u.id = ta2.user_id AND ta2.tiebreaker_rank = 2
                LEFT JOIN tiebreaker_accuracy ta3 ON u.id = ta3.user_id AND ta3.tiebreaker_rank = 3
                ORDER BY total_points DESC, correct_locks DESC, first_tiebreaker_diff ASC, second_tiebreaker_diff ASC, third_tiebreaker_diff ASC
            """
            
            cur.execute(points_query)
            leaderboard = cur.fetchall()
            return leaderboard
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def get_week_ranges():
    """Define all CFB and NFL week ranges for the 2025 season."""
    # All times are in UTC (Eastern + 4 hours during EDT, +5 during EST)
    # CFB Week 0: Tues Aug 19 2025 3am ET to Tues Aug 26 2025 2:59am ET
    # CFB Week 1: Tues Aug 26 2025 3am ET to Tues Sept 2 2025 2:59am ET
    # etc.
    
    week_ranges = {
        "overall": {"start": None, "end": None, "label": "Overall"},
        "cfb_week_0": {"start": "2025-08-19T07:00:00Z", "end": "2025-08-26T06:59:59Z", "label": "CFB Week 0"},
        "cfb_week_1": {"start": "2025-08-26T07:00:00Z", "end": "2025-09-02T06:59:59Z", "label": "CFB Week 1"},
        "cfb_week_2_nfl_week_1": {"start": "2025-09-02T07:00:00Z", "end": "2025-09-09T06:59:59Z", "label": "CFB Week 2, NFL Week 1"},
        "cfb_week_3_nfl_week_2": {"start": "2025-09-09T07:00:00Z", "end": "2025-09-16T06:59:59Z", "label": "CFB Week 3, NFL Week 2"},
        "cfb_week_4_nfl_week_3": {"start": "2025-09-16T07:00:00Z", "end": "2025-09-23T06:59:59Z", "label": "CFB Week 4, NFL Week 3"},
        "cfb_week_5_nfl_week_4": {"start": "2025-09-23T07:00:00Z", "end": "2025-09-30T06:59:59Z", "label": "CFB Week 5, NFL Week 4"},
        "cfb_week_6_nfl_week_5": {"start": "2025-09-30T07:00:00Z", "end": "2025-10-07T06:59:59Z", "label": "CFB Week 6, NFL Week 5"},
        "cfb_week_7_nfl_week_6": {"start": "2025-10-07T07:00:00Z", "end": "2025-10-14T06:59:59Z", "label": "CFB Week 7, NFL Week 6"},
        "cfb_week_8_nfl_week_7": {"start": "2025-10-14T07:00:00Z", "end": "2025-10-21T06:59:59Z", "label": "CFB Week 8, NFL Week 7"},
        "cfb_week_9_nfl_week_8": {"start": "2025-10-21T07:00:00Z", "end": "2025-10-28T06:59:59Z", "label": "CFB Week 9, NFL Week 8"},
        "cfb_week_10_nfl_week_9": {"start": "2025-10-28T07:00:00Z", "end": "2025-11-04T06:59:59Z", "label": "CFB Week 10, NFL Week 9"},
        "cfb_week_11_nfl_week_10": {"start": "2025-11-04T07:00:00Z", "end": "2025-11-11T06:59:59Z", "label": "CFB Week 11, NFL Week 10"},
        "cfb_week_12_nfl_week_11": {"start": "2025-11-11T07:00:00Z", "end": "2025-11-18T06:59:59Z", "label": "CFB Week 12, NFL Week 11"},
        "cfb_week_13_nfl_week_12": {"start": "2025-11-18T07:00:00Z", "end": "2025-11-25T06:59:59Z", "label": "CFB Week 13, NFL Week 12"},
        "cfb_week_14_nfl_week_13": {"start": "2025-11-25T07:00:00Z", "end": "2025-12-02T06:59:59Z", "label": "CFB Week 14, NFL Week 13"},
        "nfl_week_14": {"start": "2025-12-02T07:00:00Z", "end": "2025-12-09T06:59:59Z", "label": "NFL Week 14"},
        "nfl_week_15": {"start": "2025-12-09T07:00:00Z", "end": "2025-12-16T06:59:59Z", "label": "NFL Week 15"},
        "nfl_week_16": {"start": "2025-12-16T07:00:00Z", "end": "2025-12-23T06:59:59Z", "label": "NFL Week 16"},
        "nfl_week_17": {"start": "2025-12-23T07:00:00Z", "end": "2025-12-30T06:59:59Z", "label": "NFL Week 17"},
        "nfl_week_18": {"start": "2025-12-30T07:00:00Z", "end": "2026-01-06T06:59:59Z", "label": "NFL Week 18"}
    }
    return week_ranges

def get_week_filter_conditions(filter_key):
    """Get the SQL filter conditions for a given week filter."""
    week_ranges = get_week_ranges()
    
    if filter_key not in week_ranges:
        return "", ""
    
    week_info = week_ranges[filter_key]
    
    if filter_key == "overall":
        return "", ""
    else:
        start_condition = f" AND g.game_date >= '{week_info['start']}'" if week_info['start'] else ""
        end_condition = f" AND g.game_date <= '{week_info['end']}'" if week_info['end'] else ""
        return start_condition, end_condition

def get_tiebreaker_week_filter_conditions(filter_key):
    """Get the SQL filter conditions for tiebreakers for a given week filter."""
    week_ranges = get_week_ranges()
    
    if filter_key not in week_ranges:
        return "", ""
    
    week_info = week_ranges[filter_key]
    
    if filter_key == "overall":
        return "", ""
    else:
        start_condition = f" AND t.start_time >= '{week_info['start']}'" if week_info['start'] else ""
        end_condition = f" AND t.start_time <= '{week_info['end']}'" if week_info['end'] else ""
        return start_condition, end_condition

@app.post("/debug-game-data")
async def debug_game_data(request: Request, current_user: User = Depends(get_current_admin_user)):
    """Debug endpoint to see raw game data before Pydantic validation."""
    try:
        body = await request.json()
        logger.info(f"Raw request body: {body}")
        return {"received": body}
    except Exception as e:
        logger.error(f"Error parsing request: {str(e)}")
        return {"error": str(e)}

def serialize_game_row(row):
    """Serialize a DB game row ensuring datetime fields are UTC ISO strings with 'Z'."""
    try:
        game_date = normalize_datetime(row["game_date"]).isoformat().replace("+00:00", "Z")
    except Exception:
        # Fallback in case of unexpected formats
        game_date = row["game_date"].isoformat() if hasattr(row["game_date"], "isoformat") else row["game_date"]
    serialized = dict(row)
    serialized["game_date"] = game_date
    return serialized

def serialize_tiebreaker_row(row):
    """Serialize a DB tiebreaker row ensuring datetime fields are UTC ISO strings with 'Z'."""
    try:
        start_time = normalize_datetime(row["start_time"]).isoformat().replace("+00:00", "Z")
    except Exception:
        # Fallback in case of unexpected formats
        start_time = row["start_time"].isoformat() if hasattr(row["start_time"], "isoformat") else row["start_time"]
    serialized = dict(row)
    serialized["start_time"] = start_time
    return serialized

@app.post("/games")
async def create_game(
    game: Game,
    current_user: User = Depends(get_current_admin_user)
):
    """Create a new game (admin only)."""
    try:
        logger.info(f"Received game creation request: {game}")
        logger.info(f"Game date: {game.game_date}")
        logger.info(f"Game date type: {type(game.game_date)}")
        logger.info(f"Game date timezone: {game.game_date.tzinfo}")
        
        # Validate game date is not in the past
        current_time = get_current_utc_time()
        logger.info(f"Current time: {current_time}")
        
        if game.game_date <= current_time:
            logger.warning(f"Game date {game.game_date} is not in the future (current: {current_time})")
            raise HTTPException(
                status_code=400, 
                detail="Game date must be in the future"
            )
        
        # Validate game date is reasonable (not more than 1 year in the future)
        max_future_date = current_time + timedelta(days=365)
        if game.game_date > max_future_date:
            raise HTTPException(
                status_code=400,
                detail="Game date cannot be more than 1 year in the future"
            )
        
        with get_db_cursor(commit=True) as cur:
            logger.info(f"Creating new game with data: {game}")
            logger.info(f"Game date before DB insert: {game.game_date}")
            logger.info(f"Game date timezone info: {game.game_date.tzinfo}")
            
            cur.execute(
                """
                INSERT INTO games (home_team, away_team, spread, game_date)
                VALUES (%s, %s, %s, %s)
                RETURNING *
                """,
                (game.home_team, game.away_team, game.spread, game.game_date)
            )
            new_game = cur.fetchone()
            logger.info(f"Game created successfully: {new_game}")
            logger.info(f"Game date after DB insert: {new_game['game_date']}")
            return serialize_game_row(new_game)
    except HTTPException:
        raise
    except ValidationError as e:
        logger.error(f"Validation error creating game: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        logger.error(f"Error creating game: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/games")
def get_games(all_games: bool = False, current_user: User = Depends(get_current_user)):
    try:
        with get_db_cursor() as cur:
            # If user is admin and requests all games, fetch all games
            # Otherwise, only fetch future games for better performance
            if all_games and current_user.admin:
                cur.execute("SELECT * FROM games ORDER BY game_date DESC")
            else:
                current_time = get_current_utc_time()
                cur.execute("SELECT * FROM games WHERE game_date > %s ORDER BY game_date", (current_time,))
            games = cur.fetchall()
            # Ensure game_date has timezone info in the API response
            return [serialize_game_row(g) for g in games]
    except Exception as e:
        logger.error(f"Error fetching games: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/make_admin/{username}")
async def make_admin(
    username: str,
    current_user: User = Depends(get_current_admin_user)
):
    """Make a user an admin (admin only)."""
    try:
        with get_db_cursor(commit=True) as cur:
            # Check if user exists
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            if not user:
                raise HTTPException(
                    status_code=404,
                    detail="User not found"
                )
            
            # Make user admin
            cur.execute(
                "UPDATE users SET admin = TRUE WHERE username = %s RETURNING username, admin",
                (username,)
            )
            updated_user = cur.fetchone()
            return updated_user
    except Exception as e:
        logger.error(f"Error making user admin: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/user_picks/{username}")
def get_user_picks(username: str):
    """Get a user's picks for games that have already started."""
    try:
        with get_db_cursor() as cur:
            current_time = get_current_utc_time()
            
            cur.execute("""
                SELECT 
                    g.id as game_id,
                    g.home_team,
                    g.away_team,
                    g.spread,
                    g.game_date,
                    g.winning_team,
                    p.picked_team,
                    p.points_awarded
                FROM games g
                JOIN picks p ON g.id = p.game_id
                JOIN users u ON p.user_id = u.id
                WHERE u.username = %s AND g.game_date <= %s
                ORDER BY g.game_date DESC
            """, (username, current_time))
            picks = cur.fetchall()
            return picks
    except Exception as e:
        logger.error(f"Error fetching user picks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live_games")
def get_live_games():
    """Get all live games (games that have started but don't have a winner yet) and their picks."""
    current_time = get_current_utc_time()

    try:
        # Use optimized query with retry logic
        query = """
            SELECT 
                g.id as game_id,
                g.home_team,
                g.away_team,
                g.spread,
                g.game_date,
                g.winning_team,
                COUNT(p.id) as total_picks,
                COUNT(CASE WHEN p.picked_team = g.home_team THEN 1 END) as home_picks,
                COUNT(CASE WHEN p.picked_team = g.away_team THEN 1 END) as away_picks
            FROM games g
            LEFT JOIN picks p ON g.id = p.game_id
            LEFT JOIN users u ON p.user_id = u.id AND u.make_picks = TRUE
            WHERE g.game_date <= %s 
            AND (g.winning_team IS NULL OR g.winning_team = '')
            GROUP BY g.id, g.home_team, g.away_team, g.spread, g.game_date, g.winning_team
            ORDER BY g.game_date DESC
        """
        
        games = execute_query_with_retry(query, (current_time,))
        logger.debug(f"Found {len(games)} live games")
        return games
    except Exception as e:
        logger.error(f"Error fetching live games: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live_games/{game_id}/picks")
def get_game_picks(game_id: int):
    """Get detailed picks for a specific game - called only when modal is opened."""
    try:
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT 
                    u.username,
                    u.full_name,
                    p.picked_team,
                    p.lock
                FROM picks p
                JOIN users u ON p.user_id = u.id
                WHERE p.game_id = %s AND u.make_picks = TRUE
                ORDER BY u.full_name
            """, (game_id,))
            picks = cur.fetchall()
            return picks
    except Exception as e:
        logger.error(f"Error fetching game picks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/games/{game_id}")
async def update_game(
    game_id: int,
    game: GameUpdate,
    current_user: User = Depends(get_current_admin_user)
):
    """Update a game (admin only)."""
    try:
        with get_db_cursor(commit=True) as cur:
            # Check if game exists
            cur.execute("SELECT * FROM games WHERE id = %s", (game_id,))
            existing_game = cur.fetchone()
            if not existing_game:
                raise HTTPException(status_code=404, detail="Game not found")
            
            # Validate game date is not in the past (only if it's being changed)
            existing_game_date = normalize_datetime(existing_game["game_date"])
            
            # Compare dates with tolerance for small differences (within 1 minute)
            date_difference = abs((game.game_date - existing_game_date).total_seconds())
            logger.info(f"Game update - existing date: {existing_game_date}, new date: {game.game_date}, difference: {date_difference} seconds")
            
            if date_difference > 60:  # More than 1 minute difference
                current_time = get_current_utc_time()
                logger.info(f"Game date changed significantly, validating. Current time: {current_time}")
                
                # Check if the new date is in the past
                if game.game_date <= current_time:
                    logger.warning(f"Admin is setting game date to past: {game.game_date} (current: {current_time})")
                    # Allow past dates for admin updates, but log a warning
                    # This allows admins to correct game times or handle rescheduled games
                
                # Validate game date is reasonable (not more than 1 year in the future)
                max_future_date = current_time + timedelta(days=365)
                if game.game_date > max_future_date:
                    logger.error(f"Game date validation failed - game date {game.game_date} is too far in the future")
                    raise HTTPException(
                        status_code=400,
                        detail="Game date cannot be more than 1 year in the future"
                    )
            else:
                logger.info("Game date unchanged or changed by less than 1 minute, skipping date validation")
            
            # Update game
            cur.execute(
                """
                UPDATE games 
                SET home_team = %s, away_team = %s, spread = %s, game_date = %s, winning_team = %s
                WHERE id = %s
                RETURNING *
                """,
                (game.home_team, game.away_team, game.spread, game.game_date, game.winning_team, game_id)
            )
            updated_game = cur.fetchone()
            
            # If winning team changed, update points using centralized scoring function
            if game.winning_team != existing_game["winning_team"]:
                logger.info(f"🎯 Processing score update via /games/{game_id} endpoint")
                affected_picks = update_game_scores(cur, game_id, game.winning_team)
                
                # Update leaderboard for all affected users
                affected_users = list(set(pick["user_id"] for pick in affected_picks))
                update_leaderboard_totals(cur, affected_users)
                
                logger.info(f"✅ Game update completed: {len(affected_picks)} picks updated, {len(affected_users)} users affected")
            
            return serialize_game_row(updated_game)
    except Exception as e:
        logger.error(f"Error updating game: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/games/{game_id}")
async def delete_game(
    game_id: int,
    current_user: User = Depends(get_current_admin_user)
):
    """Delete a game (admin only)."""
    try:
        with get_db_cursor(commit=True) as cur:
            # Check if game exists
            cur.execute("SELECT * FROM games WHERE id = %s", (game_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Game not found")
            
            # Delete game (picks will be deleted automatically due to CASCADE)
            cur.execute("DELETE FROM games WHERE id = %s RETURNING *", (game_id,))
            deleted_game = cur.fetchone()
            
            # Update leaderboard points
            cur.execute(
                """
                UPDATE leaderboard l
                SET total_points = (
                    SELECT COALESCE(SUM(points_awarded), 0)
                    FROM picks
                    WHERE user_id = l.user_id
                )
                """
            )
            
            return {"message": "Game deleted successfully", "game": deleted_game}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting game: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/my_picks")
async def get_my_picks(current_user: User = Depends(get_current_user)):
    """Get all picks for the current user, including future games."""
    try:
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT 
                    g.id as game_id,
                    g.home_team,
                    g.away_team,
                    g.spread,
                    g.game_date,
                    g.winning_team,
                    p.picked_team,
                    p.points_awarded,
                    p.lock
                FROM games g
                LEFT JOIN picks p ON g.id = p.game_id AND p.user_id = %s
                ORDER BY g.game_date
            """, (current_user.id,))
            picks = cur.fetchall()
            return [serialize_game_row(p) for p in picks]
    except Exception as e:
        logger.error(f"Error fetching user picks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/user_picks_status")
async def get_user_picks_status(current_user: User = Depends(get_current_admin_user)):
    """Get the picks status for all users."""
    with get_db_cursor() as cur:
        current_time = get_current_utc_time()

        # Calculate current week bounds (Tuesday 3am to next Tuesday 2:59am ET)
        current_week_start, current_week_end = get_game_week_bounds(current_time)
        
        # Get total number of upcoming games
        cur.execute("""
            SELECT COUNT(*) as total 
            FROM games 
            WHERE game_date > %s
        """, (current_time,))
        total_upcoming_games = cur.fetchone()['total']
        
        # Get total number of upcoming tiebreakers
        cur.execute("""
            SELECT COUNT(*) as total 
            FROM tiebreakers 
            WHERE start_time > %s AND is_active = TRUE
        """, (current_time,))
        total_upcoming_tiebreakers = cur.fetchone()['total']
        
        total_required_picks = total_upcoming_games + total_upcoming_tiebreakers
        
        # Get all users and their picks count for upcoming games and tiebreakers, plus current week locks
        cur.execute("""
            WITH upcoming_picks AS (
                SELECT u.id as user_id, COUNT(p.id) as picks_count
                FROM users u
                LEFT JOIN picks p ON u.id = p.user_id
                LEFT JOIN games g ON p.game_id = g.id
                WHERE g.game_date > %s
                GROUP BY u.id
            ),
            upcoming_tiebreaker_picks AS (
                SELECT u.id as user_id, COUNT(tp.id) as picks_count
                FROM users u
                LEFT JOIN tiebreaker_picks tp ON u.id = tp.user_id
                LEFT JOIN tiebreakers t ON tp.tiebreaker_id = t.id
                WHERE t.start_time > %s AND t.is_active = TRUE
                GROUP BY u.id
            ),
            current_week_locks AS (
                SELECT u.id as user_id, COUNT(p.id) as locks_count
                FROM users u
                LEFT JOIN picks p ON u.id = p.user_id
                LEFT JOIN games g ON p.game_id = g.id
                WHERE p.lock = TRUE
                AND g.game_date BETWEEN %s AND %s
                GROUP BY u.id
            )
            SELECT
                u.username,
                u.full_name,
                COALESCE(up.picks_count, 0) + COALESCE(utp.picks_count, 0) as total_picks_made,
                CASE WHEN COALESCE(cwl.locks_count, 0) > 0 THEN TRUE ELSE FALSE END as has_current_week_lock
            FROM users u
            LEFT JOIN upcoming_picks up ON u.id = up.user_id
            LEFT JOIN upcoming_tiebreaker_picks utp ON u.id = utp.user_id
            LEFT JOIN current_week_locks cwl ON u.id = cwl.user_id
            WHERE u.make_picks = TRUE
            ORDER BY u.username
        """, (current_time, current_time, current_week_start, current_week_end))
        
        users_status = []
        for row in cur.fetchall():
            users_status.append(UserPicksStatus(
                username=row['username'],
                full_name=row['full_name'],
                total_games=total_required_picks,
                picks_made=row['total_picks_made'],
                is_complete=row['total_picks_made'] == total_required_picks,
                has_current_week_lock=row['has_current_week_lock']
            ))
        
        return users_status

class Pick(BaseModel):
    game_id: int
    picked_team: str

class Tiebreaker(BaseModel):
    question: str
    start_time: datetime

    @validator('start_time', pre=True, always=True)
    def normalize_start_time(cls, v):
        if isinstance(v, str):
            # Handle ISO format strings with 'Z' (UTC) or timezone offsets
            if 'Z' in v:
                # Replace 'Z' with '+00:00' for proper parsing
                v = v.replace('Z', '+00:00')
            elif '+' not in v and '-' not in v[10:]:
                raise ValueError("Datetime string must include timezone information")
            
            try:
                v = datetime.fromisoformat(v)
            except ValueError as e:
                raise ValueError(f"Invalid datetime format: {e}")
        
        if not isinstance(v, datetime):
            raise ValueError("Invalid datetime format")

        if v.tzinfo is None:
            raise ValueError("Datetime must be timezone-aware")
            
        dt = normalize_datetime(v)
        return dt.replace(second=0, microsecond=0)

class TiebreakerUpdate(BaseModel):
    question: str
    start_time: datetime
    answer: Optional[Union[str, float]] = None
    is_active: bool = True

    @validator('start_time', pre=True, always=True)
    def normalize_start_time(cls, v):
        if isinstance(v, str):
            # Handle ISO format strings with 'Z' (UTC) or timezone offsets
            if 'Z' in v:
                # Replace 'Z' with '+00:00' for proper parsing
                v = v.replace('Z', '+00:00')
            elif '+' not in v and '-' not in v[10:]:
                raise ValueError("Datetime string must include timezone information")
            
            try:
                v = datetime.fromisoformat(v)
            except ValueError as e:
                raise ValueError(f"Invalid datetime format: {e}")
        
        if not isinstance(v, datetime):
            raise ValueError("Invalid datetime format")

        if v.tzinfo is None:
            raise ValueError("Datetime must be timezone-aware")
            
        dt = normalize_datetime(v)
        return dt.replace(second=0, microsecond=0)

class TiebreakerPick(BaseModel):
    tiebreaker_id: int
    answer: Union[str, float]

class TiebreakerPointsUpdate(BaseModel):
    user_id: int
    tiebreaker_id: int
    points: int

@app.post("/tiebreakers")
async def create_tiebreaker(
    tiebreaker: Tiebreaker,
    current_user: User = Depends(get_current_admin_user)
):
    """Create a new tiebreaker (admin only)."""
    try:
        # Validate start time is not in the past
        current_time = get_current_utc_time()
        if tiebreaker.start_time <= current_time:
            raise HTTPException(
                status_code=400, 
                detail="Tiebreaker start time must be in the future"
            )
        
        # Validate start time is reasonable (not more than 1 year in the future)
        max_future_date = current_time + timedelta(days=365)
        if tiebreaker.start_time > max_future_date:
            raise HTTPException(
                status_code=400,
                detail="Tiebreaker start time cannot be more than 1 year in the future"
            )
        
        with get_db_cursor(commit=True) as cur:
            logger.info(f"Creating new tiebreaker: {tiebreaker}")
            cur.execute(
                """
                INSERT INTO tiebreakers (question, start_time)
                VALUES (%s, %s)
                RETURNING *
                """,
                (tiebreaker.question, tiebreaker.start_time)
            )
            new_tiebreaker = cur.fetchone()
            logger.info(f"Tiebreaker created successfully: {new_tiebreaker}")
            return new_tiebreaker
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating tiebreaker: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tiebreakers")
def get_tiebreakers():
    """Get all tiebreakers."""
    try:
        with get_db_cursor() as cur:
            # Only fetch active tiebreakers for better performance
            current_time = get_current_utc_time()
            cur.execute("SELECT * FROM tiebreakers WHERE start_time > %s AND is_active = TRUE ORDER BY start_time", (current_time,))
            tiebreakers = cur.fetchall()
            return [serialize_tiebreaker_row(t) for t in tiebreakers]
    except Exception as e:
        logger.error(f"Error fetching tiebreakers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live_tiebreakers")
def get_live_tiebreakers():
    """Get all live tiebreakers with pick counts."""
    try:
        current_time = get_current_utc_time()
        logger.debug(f"Checking live tiebreakers at {current_time}")
        
        # Use optimized query with retry logic
        query = """
            SELECT 
                t.id as tiebreaker_id,
                t.question,
                t.start_time,
                t.is_active,
                COUNT(tp.id) as total_picks
            FROM tiebreakers t
            LEFT JOIN tiebreaker_picks tp ON t.id = tp.tiebreaker_id
            LEFT JOIN users u ON tp.user_id = u.id AND u.make_picks = TRUE
            WHERE t.start_time <= %s 
            AND t.is_active = TRUE
            AND t.answer IS NULL
            GROUP BY t.id, t.question, t.start_time, t.is_active
            ORDER BY t.start_time DESC
        """
        
        tiebreakers = execute_query_with_retry(query, (current_time,))
        logger.debug(f"Found {len(tiebreakers)} live tiebreakers")
        return tiebreakers
    except Exception as e:
        logger.error(f"Error fetching live tiebreakers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live_tiebreakers/{tiebreaker_id}/picks")
def get_tiebreaker_picks(tiebreaker_id: int):
    """Get detailed picks for a specific tiebreaker - called only when modal is opened."""
    try:
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT 
                    u.username,
                    u.full_name,
                    tp.answer
                FROM tiebreaker_picks tp
                JOIN users u ON tp.user_id = u.id
                WHERE tp.tiebreaker_id = %s AND u.make_picks = TRUE
                ORDER BY u.full_name
            """, (tiebreaker_id,))
            picks = cur.fetchall()
            return picks
    except Exception as e:
        logger.error(f"Error fetching tiebreaker picks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/tiebreakers/{tiebreaker_id}")
async def update_tiebreaker(
    tiebreaker_id: int,
    tiebreaker: TiebreakerUpdate,
    current_user: User = Depends(get_current_admin_user)
):
    """Update a tiebreaker (admin only)."""
    try:
        with get_db_cursor(commit=True) as cur:
            # Check if tiebreaker exists
            cur.execute("SELECT * FROM tiebreakers WHERE id = %s", (tiebreaker_id,))
            existing_tiebreaker = cur.fetchone()
            if not existing_tiebreaker:
                raise HTTPException(status_code=404, detail="Tiebreaker not found")
            
            # Validate start time is not in the past (only if it's being changed)
            existing_start_time = normalize_datetime(existing_tiebreaker["start_time"])
            
            # Compare dates with tolerance for small differences (within 1 minute)
            date_difference = abs((tiebreaker.start_time - existing_start_time).total_seconds())
            logger.info(f"Tiebreaker update - existing start time: {existing_start_time}, new start time: {tiebreaker.start_time}, difference: {date_difference} seconds")
            
            if date_difference > 60:  # More than 1 minute difference
                current_time = get_current_utc_time()
                logger.info(f"Tiebreaker start time changed significantly, validating. Current time: {current_time}")
                
                # Check if the new date is in the past
                if tiebreaker.start_time <= current_time:
                    logger.warning(f"Admin is setting tiebreaker start time to past: {tiebreaker.start_time} (current: {current_time})")
                    # Allow past dates for admin updates, but log a warning
                    # This allows admins to correct tiebreaker times or handle rescheduled events
                
                # Validate start time is reasonable (not more than 1 year in the future)
                max_future_date = current_time + timedelta(days=365)
                if tiebreaker.start_time > max_future_date:
                    logger.error(f"Tiebreaker start time validation failed - start time {tiebreaker.start_time} is too far in the future")
                    raise HTTPException(
                        status_code=400,
                        detail="Tiebreaker start time cannot be more than 1 year in the future"
                    )
            else:
                logger.info("Tiebreaker start time unchanged or changed by less than 1 minute, skipping validation")
            
            # Update tiebreaker
            cur.execute(
                """
                UPDATE tiebreakers 
                SET question = %s, start_time = %s, answer = %s, is_active = %s
                WHERE id = %s
                RETURNING *
                """,
                (tiebreaker.question, tiebreaker.start_time, tiebreaker.answer, tiebreaker.is_active, tiebreaker_id)
            )
            updated_tiebreaker = cur.fetchone()
            
            return updated_tiebreaker
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating tiebreaker: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/tiebreakers/{tiebreaker_id}")
async def delete_tiebreaker(
    tiebreaker_id: int,
    current_user: User = Depends(get_current_admin_user)
):
    """Delete a tiebreaker (admin only)."""
    try:
        with get_db_cursor(commit=True) as cur:
            # Check if tiebreaker exists
            cur.execute("SELECT * FROM tiebreakers WHERE id = %s", (tiebreaker_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Tiebreaker not found")
            
            # Delete tiebreaker (picks will be deleted automatically due to CASCADE)
            cur.execute("DELETE FROM tiebreakers WHERE id = %s RETURNING *", (tiebreaker_id,))
            deleted_tiebreaker = cur.fetchone()
            
            # Update leaderboard points
            cur.execute(
                """
                UPDATE leaderboard l
                SET total_points = (
                    SELECT COALESCE(SUM(points_awarded), 0)
                    FROM picks
                    WHERE user_id = l.user_id
                ) + (
                    SELECT COALESCE(SUM(points_awarded), 0)
                    FROM tiebreaker_picks
                    WHERE user_id = l.user_id
                )
                """
            )
            
            return {"message": "Tiebreaker deleted successfully", "tiebreaker": deleted_tiebreaker}
    except Exception as e:
        logger.error(f"Error deleting tiebreaker: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tiebreaker_picks")
async def create_tiebreaker_pick(
    pick: TiebreakerPick,
    current_user: User = Depends(get_current_user)
):
    """Create a new tiebreaker pick."""
    # Check if user has permission to make picks
    if not current_user.make_picks:
        raise HTTPException(
            status_code=403, 
            detail="You do not have permission to make picks"
        )
    
    try:
        with get_db_cursor(commit=True) as cur:
            # Check if tiebreaker exists and is active
            cur.execute(
                """
                SELECT * FROM tiebreakers 
                WHERE id = %s AND is_active = TRUE AND answer IS NULL
                """, 
                (pick.tiebreaker_id,)
            )
            tiebreaker = cur.fetchone()
            if not tiebreaker:
                raise HTTPException(status_code=404, detail="Tiebreaker not found or is no longer active")
            
            # Check if tiebreaker has started
            current_time = get_current_utc_time()
            tiebreaker_start_time = normalize_datetime(tiebreaker["start_time"])
            
            if current_time >= tiebreaker_start_time:
                raise HTTPException(
                    status_code=400, 
                    detail="Cannot submit tiebreaker pick after the tiebreaker has started"
                )
            
            # Check if user already has a pick for this tiebreaker
            cur.execute(
                """
                SELECT * FROM tiebreaker_picks 
                WHERE user_id = %s AND tiebreaker_id = %s
                """, 
                (current_user.id, pick.tiebreaker_id)
            )
            existing_pick = cur.fetchone()
            
            if existing_pick:
                # Update existing pick
                cur.execute(
                    """
                    UPDATE tiebreaker_picks 
                    SET answer = %s
                    WHERE user_id = %s AND tiebreaker_id = %s
                    RETURNING *
                    """,
                    (pick.answer, current_user.id, pick.tiebreaker_id)
                )
            else:
                # Create new pick
                cur.execute(
                    """
                    INSERT INTO tiebreaker_picks (user_id, tiebreaker_id, answer)
                    VALUES (%s, %s, %s)
                    RETURNING *
                    """,
                    (current_user.id, pick.tiebreaker_id, pick.answer)
                )
            
            new_pick = cur.fetchone()
            return new_pick
    except Exception as e:
        logger.error(f"Error creating tiebreaker pick: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/picks_data")
async def get_picks_data(current_user: User = Depends(get_current_user)):
    """Get all data needed for the Picks page in a single optimized call."""
    # Check if user has permission to make picks
    if not current_user.make_picks:
        raise HTTPException(
            status_code=403, 
            detail="You do not have permission to make picks"
        )
    
    try:
        with get_db_cursor() as cur:
            # Get current time for filtering
            current_time = get_current_utc_time()
            
            # Single query to get games with user picks and locks
            cur.execute("""
                SELECT 
                    g.id as game_id,
                    g.home_team,
                    g.away_team,
                    g.spread,
                    g.game_date,
                    g.winning_team,
                    p.picked_team,
                    p.points_awarded,
                    p.lock
                FROM games g
                LEFT JOIN picks p ON g.id = p.game_id AND p.user_id = %s
                WHERE g.game_date > %s
                ORDER BY g.game_date
            """, (current_user.id, current_time))
            games = cur.fetchall()
            
            # Single query to get active tiebreakers with user picks
            cur.execute("""
                SELECT 
                    t.id as tiebreaker_id,
                    t.question,
                    t.start_time,
                    t.answer as correct_answer,
                    t.is_active,
                    tp.answer as user_answer,
                    tp.points_awarded
                FROM tiebreakers t
                LEFT JOIN tiebreaker_picks tp ON t.id = tp.tiebreaker_id AND tp.user_id = %s
                WHERE t.start_time > %s AND t.is_active = TRUE
                ORDER BY t.start_time
            """, (current_user.id, current_time))
            tiebreakers = cur.fetchall()
            
            return {
                "games": [serialize_game_row(g) for g in games],
                "tiebreakers": [serialize_tiebreaker_row(t) for t in tiebreakers]
            }
    except Exception as e:
        logger.error(f"Error fetching picks data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/my_tiebreaker_picks")
async def get_my_tiebreaker_picks(current_user: User = Depends(get_current_user)):
    """Get all tiebreaker picks for the current user."""
    try:
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT 
                    t.id as tiebreaker_id,
                    t.question,
                    t.start_time,
                    t.answer as correct_answer,
                    t.is_active,
                    tp.answer as user_answer,
                    tp.points_awarded
                FROM tiebreakers t
                LEFT JOIN tiebreaker_picks tp ON t.id = tp.tiebreaker_id AND tp.user_id = %s
                ORDER BY t.start_time
            """, (current_user.id,))
            picks = cur.fetchall()
            return [serialize_tiebreaker_row(p) for p in picks]
    except Exception as e:
        logger.error(f"Error fetching user tiebreaker picks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/user_all_picks/{username}")
async def get_user_all_picks(
    username: str,
    current_user: User = Depends(get_current_admin_user)
):
    """Get ALL picks for a specific user (admin only), regardless of start time."""
    try:
        with get_db_cursor() as cur:
            # Get user info
            cur.execute("SELECT id, username, full_name FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Check if user has make_picks permission
            cur.execute("SELECT make_picks FROM users WHERE username = %s", (username,))
            user_permissions = cur.fetchone()
            if not user_permissions or not user_permissions['make_picks']:
                raise HTTPException(status_code=404, detail="User not found")

            # Get all game picks
            cur.execute("""
                SELECT
                    g.id as game_id,
                    g.home_team,
                    g.away_team,
                    g.spread,
                    g.game_date,
                    g.winning_team,
                    p.picked_team,
                    p.points_awarded,
                    p.lock
                FROM games g
                LEFT JOIN picks p ON g.id = p.game_id AND p.user_id = %s
                ORDER BY g.game_date
            """, (user['id'],))
            game_picks = cur.fetchall()

            # Get all tiebreaker picks
            cur.execute("""
                SELECT 
                    t.id as tiebreaker_id,
                    t.question,
                    t.start_time,
                    t.answer as correct_answer,
                    t.is_active,
                    tp.answer as user_answer,
                    tp.points_awarded
                FROM tiebreakers t
                LEFT JOIN tiebreaker_picks tp ON t.id = tp.tiebreaker_id AND tp.user_id = %s
                ORDER BY t.start_time
            """, (user['id'],))
            tiebreaker_picks = cur.fetchall()

            return {
                "user": user,
                "game_picks": game_picks,
                "tiebreaker_picks": tiebreaker_picks
            }
    except Exception as e:
        logger.error(f"Error fetching all user picks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/tiebreaker_picks/points")
async def update_tiebreaker_points(
    points_update: TiebreakerPointsUpdate,
    current_user: User = Depends(get_current_admin_user)
):
    """Update points for a tiebreaker pick (admin only)."""
    try:
        with get_db_cursor(commit=True) as cur:
            # Check if tiebreaker pick exists
            cur.execute(
                """
                SELECT * FROM tiebreaker_picks 
                WHERE user_id = %s AND tiebreaker_id = %s
                """, 
                (points_update.user_id, points_update.tiebreaker_id)
            )
            existing_pick = cur.fetchone()
            if not existing_pick:
                raise HTTPException(status_code=404, detail="Tiebreaker pick not found")
            
            # Update points
            cur.execute(
                """
                UPDATE tiebreaker_picks 
                SET points_awarded = %s
                WHERE user_id = %s AND tiebreaker_id = %s
                RETURNING *
                """,
                (points_update.points, points_update.user_id, points_update.tiebreaker_id)
            )
            updated_pick = cur.fetchone()
            
            # Update leaderboard
            cur.execute(
                """
                UPDATE leaderboard 
                SET total_points = (
                    SELECT COALESCE(SUM(points_awarded), 0)
                    FROM picks
                    WHERE user_id = %s
                ) + (
                    SELECT COALESCE(SUM(points_awarded), 0)
                    FROM tiebreaker_picks
                    WHERE user_id = %s
                )
                WHERE user_id = %s
                """,
                (points_update.user_id, points_update.user_id, points_update.user_id)
            )
            
            return updated_pick
    except Exception as e:
        logger.error(f"Error updating tiebreaker points: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def create_admin_user(username, full_name, password):
    """Create an admin user or update existing user to admin."""
    try:
        with get_db_cursor(commit=True) as cur:
            # Check if user already exists
            cur.execute("SELECT id, admin FROM users WHERE username = %s", (username,))
            existing_user = cur.fetchone()
            
            if existing_user:
                # User exists, make sure they're admin
                if not existing_user['admin']:
                    cur.execute(
                        "UPDATE users SET admin = TRUE WHERE username = %s",
                        (username,)
                    )
                    logger.info(f"Updated existing user {username} to admin")
                else:
                    logger.info(f"User {username} already exists and is admin")
                return
            
            # Check if any admin exists
            cur.execute("SELECT id FROM users WHERE admin = TRUE")
            if cur.fetchone():
                logger.info("Admin user already exists, skipping creation")
                return
            
            # Create new admin user
            admin_password = password
            hashed_password = get_password_hash(admin_password)
            cur.execute(
                """
                INSERT INTO users (username, full_name, email, league_id, password_hash, admin)
                VALUES (%s, %s, %s, %s, %s, TRUE)
                RETURNING id
                """,
                (username, full_name, f"{username}@admin.local", "ADMIN", hashed_password)
            )
            admin_id = cur.fetchone()["id"]
            
            # Create leaderboard entry for admin
            cur.execute(
                "INSERT INTO leaderboard (user_id) VALUES (%s)",
                (admin_id,)
            )
            
            logger.info(f"Created admin user with username: {username}")
    except Exception as e:
        logger.error(f"Error creating admin user: {str(e)}")
        # Don't raise exception to avoid breaking app startup

def wipe_all_admin_users():
    with get_db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM users WHERE admin = TRUE")

# Initialize database
with get_db_connection() as conn:
    db.create_tables(conn)

@app.get("/user_all_past_picks/{username}")
async def get_user_all_past_picks(username: str, filter: str = "overall"):
    """Get all past picks (games and tiebreakers that have started) for a specific user."""
    try:
        with get_db_cursor() as cur:
            current_time = get_current_utc_time()
            print(f"Current time: {current_time}")
             
            # Get user info
            cur.execute("SELECT id, username, full_name FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Check if user has make_picks permission
            cur.execute("SELECT make_picks FROM users WHERE username = %s", (username,))
            user_permissions = cur.fetchone()
            if not user_permissions or not user_permissions['make_picks']:
                raise HTTPException(status_code=404, detail="User not found")

            # Get all game picks for games that have started
            game_query = """
                SELECT 
                    g.id as game_id,
                    g.home_team,
                    g.away_team,
                    g.spread,
                    g.game_date,
                    g.winning_team,
                    p.picked_team,
                    p.points_awarded,
                    p.lock
                FROM games g
                LEFT JOIN picks p ON g.id = p.game_id AND p.user_id = %s
                WHERE g.game_date <= %s
            """
            
            # Add time filter for games using week-based filtering
            start_condition, end_condition = get_week_filter_conditions(filter)
            game_query += start_condition + end_condition
                
            game_query += " ORDER BY g.game_date DESC"
            
            cur.execute(game_query, (user['id'], current_time))
            game_picks = cur.fetchall()

            # Get all tiebreaker picks for tiebreakers that have started
            tiebreaker_query = """
                SELECT 
                    t.id as tiebreaker_id,
                    t.question,
                    t.start_time,
                    t.answer as correct_answer,
                    t.is_active,
                    tp.answer as user_answer,
                    tp.points_awarded,
                    CASE 
                        WHEN t.answer ~ '^[0-9]+\\.?[0-9]*$' AND tp.answer ~ '^[0-9]+\\.?[0-9]*$'
                        THEN ABS(CAST(t.answer AS NUMERIC) - CAST(tp.answer AS NUMERIC))
                        ELSE NULL
                    END as accuracy_diff
                FROM tiebreakers t
                LEFT JOIN tiebreaker_picks tp ON t.id = tp.tiebreaker_id AND tp.user_id = %s
                WHERE t.start_time <= %s
            """
            
            # Add time filter for tiebreakers using week-based filtering
            tiebreaker_start_condition, tiebreaker_end_condition = get_tiebreaker_week_filter_conditions(filter)
            tiebreaker_query += tiebreaker_start_condition + tiebreaker_end_condition
                
            tiebreaker_query += " ORDER BY t.start_time DESC"
            
            cur.execute(tiebreaker_query, (user['id'], current_time))
            tiebreaker_picks = cur.fetchall()

            return {
                "user": user,
                "game_picks": game_picks,
                "tiebreaker_picks": tiebreaker_picks
            }
    except Exception as e:
        logger.error(f"Error fetching user past picks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/admin/delete_user/{user_id}", response_model=dict)
async def delete_user(user_id: int, current_user: User = Depends(get_current_admin_user)):
    """Delete a user and their associated picks (admin only)."""
    try:
        with get_db_cursor(commit=True) as cur:
            # Check if user exists
            cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Delete user (picks will be deleted automatically due to CASCADE)
            cur.execute("DELETE FROM users WHERE id = %s RETURNING *", (user_id,))
            deleted_user = cur.fetchone()
            
            return {"message": "User deleted successfully", "user": deleted_user}
    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while deleting the user")

# Add caching for game scores
game_scores_cache = {
    'data': None,
    'timestamp': None,
    'cache_duration': 120  # Cache for 2 minutes (increased from 30s for 20 users)
}

def get_cached_game_scores():
    """Get cached game scores if they're still valid."""
    if (game_scores_cache['data'] is not None and 
        game_scores_cache['timestamp'] is not None and
        time.time() - game_scores_cache['timestamp'] < game_scores_cache['cache_duration']):
        return game_scores_cache['data']
    return None

def set_cached_game_scores(data):
    """Cache game scores with current timestamp."""
    game_scores_cache['data'] = data
    game_scores_cache['timestamp'] = time.time()

@app.get("/traffic/status")
def get_traffic_status():
    """Get current traffic status and recommendations for users."""
    pool_status = get_pool_status()
    queue_status = get_queue_status()
    
    # Calculate traffic level
    active_percentage = (queue_status['active_requests'] / queue_status['max_concurrent']) * 100
    queue_length = queue_status['queue_length']
    
    if active_percentage < 50:
        traffic_level = "low"
        message = "Service operating normally"
    elif active_percentage < 80:
        traffic_level = "moderate"
        message = "Slight delays possible"
    elif active_percentage < 100:
        traffic_level = "high"
        message = "Please be patient, high traffic detected"
    else:
        traffic_level = "critical"
        message = "Service under heavy load, please try again later"
    
    return {
        "traffic_level": traffic_level,
        "message": message,
        "active_requests": queue_status['active_requests'],
        "max_concurrent": queue_status['max_concurrent'],
        "queue_length": queue_length,
        "active_percentage": round(active_percentage, 1),
        "pool_status": pool_status['status'],
        "cache_size": len(response_cache),
        "recommendations": {
            "low": "Normal usage",
            "moderate": "Consider refreshing less frequently",
            "high": "Please wait between requests",
            "critical": "Please try again in 30 seconds"
        }.get(traffic_level, "Please wait"),
        "timestamp": get_current_utc_time().isoformat()
    }

@app.get("/api/gamescores")
async def get_game_scores(request: Request):
    # Check cache first
    cached_data = get_cached_game_scores()
    if cached_data is not None:
        logger.debug("Returning cached game scores")
        return cached_data
    
    # Old March Madness URL (commented out)
    # url = 'https://www.cbssports.com/college-basketball/scoreboard/?layout=compact'
    urls = [
        'https://www.cbssports.com/college-football/scoreboard/?layout=compact',
        'https://www.cbssports.com/nfl/scoreboard/?layout=compact'
    ]
    games_data = []
    try:
        for url in urls:
            logger.info(f"Fetching game scores from: {url}")
            response = requests.get(url, timeout=5)  # Reduced timeout for 20 users
            response.raise_for_status()
            html_content = response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            game_cards = soup.find_all('div', class_='single-score-card')
            logger.info(f"Found {len(game_cards)} game cards at {url}")
            for game in game_cards:
                try:
                    # Try different selectors to find the teams and scores
                    team_cells = game.find_all('td', class_='team')
                    if not team_cells:
                        team_cells = game.find_all('td', class_='team--collegebasketball')
                    score_cells = game.find_all('td', class_='total')
                    if len(team_cells) < 2 or len(score_cells) < 2:
                        logger.debug(f"Not enough cells found. Team cells: {len(team_cells)}, Score cells: {len(score_cells)}")
                        continue
                    away_team = team_cells[0].find('a', class_='team-name-link')
                    home_team = team_cells[1].find('a', class_='team-name-link')
                    if not away_team or not home_team:
                        logger.debug("Could not find team name links")
                        continue
                    away_team = away_team.text.strip()
                    home_team = home_team.text.strip()
                    away_score = score_cells[0].text.strip()
                    home_score = score_cells[1].text.strip()
                    game_status = game.find('div', class_='game-status emphasis')
                    time_left = game_status.text.strip() if game_status else 'FINAL'
                    games_data.append({
                        'AwayTeam': away_team,
                        'HomeTeam': home_team,
                        'AwayScore': away_score,
                        'HomeScore': home_score,
                        'Time': time_left
                    })
                    logger.debug(f"Processed game: {away_team} @ {home_team}")
                except Exception as e:
                    logger.debug(f"Error processing individual game: {str(e)}")
                    continue
        
        # Cache the results
        set_cached_game_scores(games_data)
        logger.info(f"Successfully processed {len(games_data)} games in total")
        return games_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data from CBS Sports: {str(e)}")
        # Return cached data if available, otherwise empty array
        return cached_data if cached_data is not None else []
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        # Return cached data if available, otherwise empty array
        return cached_data if cached_data is not None else []

@app.get("/scaling/status")
def get_scaling_status():
    """Get detailed scaling status and recommendations."""
    try:
        user_count = check_user_count()  # This will log alerts if needed
        pool_status = get_pool_status()
        queue_status = get_queue_status()
        
        # Determine scaling urgency
        if user_count > 25:
            urgency = "CRITICAL"
            action = "IMMEDIATE UPGRADE REQUIRED"
            recommendation = "Upgrade to Render.com Standard-1GB plan immediately"
            color = "red"
        elif user_count > 20:
            urgency = "HIGH"
            action = "PLAN FOR UPGRADE"
            recommendation = "Consider upgrading to Standard-1GB plan soon"
            color = "orange"
        elif user_count > 15:
            urgency = "MEDIUM"
            action = "MONITOR CLOSELY"
            recommendation = "Monitor user growth and prepare for scaling"
            color = "yellow"
        else:
            urgency = "LOW"
            action = "NO ACTION NEEDED"
            recommendation = "Current plan sufficient for user count"
            color = "green"
        
        # Calculate capacity percentages
        capacity_percentage = (user_count / 25) * 100
        pool_usage = (queue_status['active_requests'] / queue_status['max_concurrent']) * 100
        
        return {
            "scaling_status": {
                "urgency": urgency,
                "action": action,
                "recommendation": recommendation,
                "color": color
            },
            "user_metrics": {
                "current_count": user_count,
                "max_capacity": 25,
                "capacity_percentage": round(capacity_percentage, 1),
                "scaling_threshold": 25
            },
            "performance_metrics": {
                "pool_usage_percentage": round(pool_usage, 1),
                "active_requests": queue_status['active_requests'],
                "max_concurrent": queue_status['max_concurrent'],
                "cache_size": len(response_cache)
            },
            "current_plan": {
                "name": "Render.com Basic-1GB",
                "cpu": "0.5 cores",
                "ram": "1GB",
                "cost": "$5/month"
            },
            "recommended_plan": {
                "name": "Render.com Standard-1GB" if user_count > 25 else "Current plan",
                "cpu": "1 core" if user_count > 25 else "0.5 cores",
                "ram": "1GB",
                "cost": "$7/month" if user_count > 25 else "$5/month",
                "max_users": "50" if user_count > 25 else "25"
            },
            "scaling_guide": {
                "file": "SCALING_GUIDE.md",
                "location": "Backend root directory",
                "last_updated": "August 19, 2025"
            },
            "alerts": {
                "critical_threshold": 25,
                "warning_threshold": 20,
                "info_threshold": 15,
                "log_message": "🚨 SCALING ALERT: User count has exceeded 25! Refer to SCALING_GUIDE.md for immediate action."
            },
            "timestamp": get_current_utc_time().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting scaling status: {str(e)}")
        return {
            "error": "Failed to get scaling status",
            "message": str(e),
            "timestamp": get_current_utc_time().isoformat()
        }

@app.post("/debug-password")
async def debug_password_verification(username: str, password: str):
    """Debug endpoint to test password verification (only in debug mode)."""
    if not os.getenv("DEBUG_MODE", "false").lower() in ["true", "1"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debug mode is not enabled"
        )
    
    try:
        with get_db_cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash FROM users WHERE username = %s",
                (username,)
            )
            user = cur.fetchone()
            
            if not user:
                return {
                    "status": "user_not_found",
                    "username": username,
                    "message": "User does not exist in database"
                }
            
            # Test password verification with detailed logging
            logger.info(f"Debug: Testing password for user {username}")
            logger.info(f"Debug: Password hash starts with: {user['password_hash'][:10]}...")
            
            try:
                password_valid = verify_password(password, user["password_hash"])
                return {
                    "status": "verification_complete",
                    "username": username,
                    "password_valid": password_valid,
                    "hash_prefix": user['password_hash'][:10],
                    "hash_type": "bcrypt" if user['password_hash'].startswith('$2') else "other"
                }
            except Exception as e:
                return {
                    "status": "verification_error",
                    "username": username,
                    "error": str(e),
                    "hash_prefix": user['password_hash'][:10],
                    "hash_type": "bcrypt" if user['password_hash'].startswith('$2') else "other"
                }
                
    except Exception as e:
        return {
            "status": "database_error",
            "error": str(e)
        }

@app.post("/admin/migrate-passwords")
async def migrate_passwords(current_user: User = Depends(get_current_admin_user)):
    """Re-hash all user passwords with current bcrypt version (admin only)."""
    try:
        with get_db_cursor(commit=True) as cur:
            # Get all users
            cur.execute("SELECT id, username, password_hash FROM users")
            users = cur.fetchall()
            
            migrated_count = 0
            for user in users:
                try:
                    # Try to identify if this is an old hash that needs migration
                    old_hash = user['password_hash']
                    
                    # For security, we can't reverse the hash, so this endpoint
                    # would need the user to provide their password or use a reset
                    logger.info(f"User {user['username']} hash type: {'bcrypt' if old_hash.startswith('$2') else 'other'}")
                    
                except Exception as e:
                    logger.error(f"Error checking user {user['username']}: {str(e)}")
                    continue
            
            return {
                "message": f"Password migration check completed for {len(users)} users",
                "users_checked": len(users),
                "note": "Use forgot-password endpoint for users with login issues"
            }
            
    except Exception as e:
        logger.error(f"Error in password migration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/reset-password")
async def admin_reset_password(username: str, new_password: str, current_user: User = Depends(get_current_admin_user)):
    """Reset a user's password with a fresh hash (admin only)."""
    try:
        with get_db_cursor(commit=True) as cur:
            # Check if user exists
            cur.execute("SELECT id, username FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Generate new password hash with current environment's bcrypt
            new_hashed_password = get_password_hash(new_password)
            
            # Update user's password
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE username = %s RETURNING username",
                (new_hashed_password, username)
            )
            updated_user = cur.fetchone()
            
            logger.info(f"Admin reset password for user: {username}")
            return {
                "message": f"Password reset successful for user {username}",
                "username": updated_user["username"],
                "hash_type": "bcrypt" if new_hashed_password.startswith('$2') else "other"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting password: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/emergency-admin-reset")
async def emergency_admin_reset(username: str, new_password: str, emergency_key: str):
    """Emergency admin password reset (requires emergency key)."""
    # This is for emergency access when admin can't log in
    expected_key = os.getenv("EMERGENCY_RESET_KEY", "emergency-key-not-set")
    
    if emergency_key != expected_key or expected_key == "emergency-key-not-set":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid emergency key"
        )
    
    try:
        with get_db_cursor(commit=True) as cur:
            # Check if user exists and is admin
            cur.execute("SELECT id, username, admin FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            if not user['admin']:
                raise HTTPException(status_code=403, detail="User is not an admin")
            
            # Generate new password hash
            new_hashed_password = get_password_hash(new_password)
            
            # Update password
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE username = %s RETURNING username",
                (new_hashed_password, username)
            )
            updated_user = cur.fetchone()
            
            logger.info(f"Emergency password reset for admin user: {username}")
            return {
                "message": f"Emergency password reset successful for admin {username}",
                "username": updated_user["username"]
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in emergency password reset: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Run the server
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)