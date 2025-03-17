from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import logging
from contextlib import contextmanager
from auth import (
    Token, UserCreate, UserLogin, User,
    verify_password, get_password_hash, create_access_token, verify_token
)
from typing import Optional, Union
import urllib.parse
import db

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def get_current_utc_time():
    """Get current time in UTC."""
    return datetime.now(timezone.utc)

# Parse database URL and handle port
database_url = os.getenv("DATABASE_URL")
if database_url:
    # Parse the URL
    parsed = urllib.parse.urlparse(database_url)
    # Get the port from the URL or use default
    port = parsed.port or 5432
    # Reconstruct the URL with the correct port
    database_url = database_url.replace(f":{parsed.port}", f":{port}")

# Create connection pool
pool = SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    dsn=database_url
)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@contextmanager
def get_db_connection():
    """Get a database connection from the pool."""
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)

@contextmanager
def get_db_cursor(commit=False):
    """Get a database cursor and handle transactions."""
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

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://march-madness-spreads-league.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Get the current user from the token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    username = verify_token(token)
    if username is None:
        raise credentials_exception
    
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT id, username, full_name, is_admin FROM users WHERE username = %s",
            (username,)
        )
        user = cur.fetchone()
        
    if user is None:
        raise credentials_exception
        
    return User(**user)

async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Check if the current user is an admin."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

@app.post("/register", response_model=User)
async def register(user: UserCreate):
    """Register a new user."""
    try:
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
                INSERT INTO users (username, full_name, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id, username, full_name, is_admin
                """,
                (user.username, user.full_name, hashed_password)
            )
            new_user = cur.fetchone()
            
            # Create leaderboard entry
            cur.execute(
                "INSERT INTO leaderboard (user_id) VALUES (%s)",
                (new_user["id"],)
            )
            
            return User(**new_user)
    except Exception as e:
        logger.error(f"Error registering user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating user"
        )

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login and get access token."""
    try:
        with get_db_cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash FROM users WHERE username = %s",
                (form_data.username,)
            )
            user = cur.fetchone()
            
            if not user or not verify_password(form_data.password, user["password_hash"]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            access_token = create_access_token(data={"sub": user["username"]})
            return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        logger.error(f"Error logging in: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error logging in"
        )

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return current_user

# Pydantic Models
class PickSubmission(BaseModel):
    game_id: int
    picked_team: str

class GameResult(BaseModel):
    game_id: int
    winning_team: str

class Game(BaseModel):
    home_team: str
    away_team: str
    spread: float
    game_date: datetime

    def __init__(self, **data):
        super().__init__(**data)
        # Ensure game_date is timezone-aware
        if self.game_date.tzinfo is None:
            self.game_date = self.game_date.replace(tzinfo=timezone.utc)
        # Truncate seconds from game_date
        self.game_date = self.game_date.replace(second=0, microsecond=0)

class GameUpdate(BaseModel):
    home_team: str
    away_team: str
    spread: float
    game_date: datetime
    winning_team: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        # Ensure game_date is timezone-aware
        if self.game_date.tzinfo is None:
            self.game_date = self.game_date.replace(tzinfo=timezone.utc)
        # Truncate seconds from game_date
        self.game_date = self.game_date.replace(second=0, microsecond=0)

class UserPicksStatus(BaseModel):
    username: str
    full_name: str
    total_games: int
    picks_made: int
    is_complete: bool

@app.post("/submit_pick")
async def submit_pick(
    pick: PickSubmission,
    current_user: User = Depends(get_current_user)
):
    """Submit a pick for a game."""
    try:
        with get_db_cursor(commit=True) as cur:
            # Check if game exists
            cur.execute("SELECT * FROM games WHERE id = %s", (pick.game_id,))
            game = cur.fetchone()
            if not game:
                raise HTTPException(status_code=404, detail="Game not found")
            
            # Check if game has already started
            current_time = datetime.now()
            if current_time >= game["game_date"]:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot submit pick: game has already started"
                )

            # Check if user has already submitted a pick for this game
            cur.execute(
                "SELECT * FROM picks WHERE user_id = %s AND game_id = %s",
                (current_user.id, pick.game_id)
            )
            existing_pick = cur.fetchone()
            
            if existing_pick:
                # Update existing pick
                cur.execute(
                    """
                    UPDATE picks 
                    SET picked_team = %s 
                    WHERE user_id = %s AND game_id = %s
                    RETURNING *
                    """,
                    (pick.picked_team, current_user.id, pick.game_id)
                )
                updated_pick = cur.fetchone()
                return {"message": "Pick updated successfully", "pick": updated_pick}
            else:
                # Insert new pick
                cur.execute(
                    """
                    INSERT INTO picks (user_id, game_id, picked_team)
                    VALUES (%s, %s, %s) RETURNING *
                    """,
                    (current_user.id, pick.game_id, pick.picked_team),
                )
                new_pick = cur.fetchone()
                return {"message": "Pick submitted successfully", "pick": new_pick}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting pick: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while submitting your pick"
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

            # If it's a push, no points are awarded
            if result.winning_team == "PUSH":
                return {"message": "Game marked as a push", "winning_team": "PUSH"}

            # Update points for correct picks
            cur.execute(
                """
                UPDATE picks 
                SET points_awarded = 1
                WHERE game_id = %s AND picked_team = %s
                RETURNING user_id;
                """,
                (result.game_id, result.winning_team),
            )
            correct_picks = cur.fetchall()

            # Update leaderboard
            for pick in correct_picks:
                cur.execute(
                    """
                    UPDATE leaderboard 
                    SET total_points = total_points + 1 
                    WHERE user_id = %s
                    """,
                    (pick["user_id"],),
                )

            return {"message": "Scores updated successfully", "winning_team": result.winning_team}
    except Exception as e:
        logger.error(f"Error updating score: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/leaderboard")
def get_leaderboard():
    try:
        with get_db_cursor() as cur:
            # Get the most recent numerical tiebreaker with an answer
            cur.execute("""
                SELECT id, answer::numeric
                FROM tiebreakers 
                WHERE answer ~ '^[0-9]+\.?[0-9]*$'
                AND answer IS NOT NULL
                ORDER BY start_time DESC 
                LIMIT 1
            """)
            latest_tiebreaker = cur.fetchone()
            
            if latest_tiebreaker:
                # If we have a numerical tiebreaker, sort by points and then by answer closeness
                cur.execute("""
                    WITH tiebreaker_diffs AS (
                        SELECT 
                            tp.user_id,
                            ABS(tp.answer::numeric - %s) as answer_diff
                        FROM tiebreaker_picks tp
                        WHERE tp.tiebreaker_id = %s
                        AND tp.answer ~ '^[0-9]+\.?[0-9]*$'
                    )
                    SELECT 
                        u.username, 
                        u.full_name, 
                        l.total_points,
                        COALESCE(td.answer_diff, float8 'infinity') as tiebreaker_diff
                    FROM leaderboard l 
                    JOIN users u ON l.user_id = u.id
                    LEFT JOIN tiebreaker_diffs td ON l.user_id = td.user_id
                    ORDER BY l.total_points DESC, td.answer_diff ASC NULLS LAST
                """, (latest_tiebreaker['answer'], latest_tiebreaker['id']))
            else:
                # If no numerical tiebreaker exists, just sort by points
                cur.execute("""
                    SELECT u.username, u.full_name, l.total_points, NULL as tiebreaker_diff
                    FROM leaderboard l 
                    JOIN users u ON l.user_id = u.id
                    ORDER BY l.total_points DESC
                """)
            
            leaderboard = cur.fetchall()
            return leaderboard
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/games")
async def create_game(
    game: Game,
    current_user: User = Depends(get_current_admin_user)
):
    """Create a new game (admin only)."""
    try:
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
            return new_game
    except Exception as e:
        logger.error(f"Error creating game: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/games")
def get_games():
    try:
        with get_db_cursor() as cur:
            logger.info("Fetching all games")
            cur.execute("SELECT * FROM games ORDER BY game_date")
            games = cur.fetchall()
            logger.info(f"Found {len(games)} games")
            return games
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
                "UPDATE users SET is_admin = TRUE WHERE username = %s RETURNING username, is_admin",
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
            current_time = datetime.now()
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
    #subtract 4 hours from the current time
    current_time = current_time - timedelta(hours=4)

    logger.info(f"Backend UTC time: {current_time}")
    logger.info(f"Current time timezone info: {current_time.tzinfo}")
    try:
        with get_db_cursor() as cur:
            logger.info(f"Checking live games at {current_time}")
            
            # First get all games to log their dates
            cur.execute("SELECT id, game_date, winning_team FROM games")
            all_games = cur.fetchall()
            for game in all_games:
                # Ensure game_date is timezone-aware
                game_date = game['game_date']
                logger.info(f"Game {game['id']} date from DB: {game_date}")
                logger.info(f"Game {game['id']} date timezone info: {game_date.tzinfo if hasattr(game_date, 'tzinfo') else 'None'}")
                
                if game_date.tzinfo is None:
                    game_date = game_date.replace(tzinfo=timezone.utc)
                    logger.info(f"Game {game['id']} date after timezone conversion: {game_date}")
                
                is_live = game_date <= current_time and (game['winning_team'] is None or game['winning_team'] == '')
                logger.info(f"Game {game['id']}: date={game_date}, winner={game['winning_team']}, is_live={is_live}")
                logger.info(f"Game {game['id']} comparison: {game_date} <= {current_time} = {game_date <= current_time}")
            
            cur.execute("""
                SELECT 
                    g.id as game_id,
                    g.home_team,
                    g.away_team,
                    g.spread,
                    g.game_date,
                    g.winning_team,
                    COALESCE(
                        json_agg(
                            json_build_object(
                                'username', u.username,
                                'full_name', u.full_name,
                                'picked_team', p.picked_team
                            )
                        ) FILTER (WHERE u.username IS NOT NULL),
                        '[]'
                    ) as picks
                FROM games g
                LEFT JOIN picks p ON g.id = p.game_id
                LEFT JOIN users u ON p.user_id = u.id
                WHERE g.game_date <= %s 
                AND (g.winning_team IS NULL OR g.winning_team = '')
                GROUP BY g.id
                ORDER BY g.game_date DESC
            """, (current_time,))
            games = cur.fetchall()
            logger.info(f"Found {len(games)} live games")
            for game in games:
                logger.info(f"Live game {game['game_id']}: date={game['game_date']}, winner={game['winning_team']}")
            return games
    except Exception as e:
        logger.error(f"Error fetching live games: {str(e)}")
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
            
            # If winning team changed, update points
            if game.winning_team != existing_game["winning_team"]:
                if game.winning_team == "PUSH":
                    # Reset all points for this game
                    cur.execute(
                        "UPDATE picks SET points_awarded = 0 WHERE game_id = %s",
                        (game_id,)
                    )
                else:
                    # Update points for correct picks
                    cur.execute(
                        """
                        UPDATE picks 
                        SET points_awarded = CASE 
                            WHEN picked_team = %s THEN 1 
                            ELSE 0 
                        END
                        WHERE game_id = %s
                        RETURNING user_id, points_awarded
                        """,
                        (game.winning_team, game_id)
                    )
                    pick_updates = cur.fetchall()
                    
                    # Update leaderboard
                    for pick in pick_updates:
                        cur.execute(
                            """
                            UPDATE leaderboard 
                            SET total_points = (
                                SELECT COALESCE(SUM(points_awarded), 0)
                                FROM picks
                                WHERE user_id = %s
                            )
                            WHERE user_id = %s
                            """,
                            (pick["user_id"], pick["user_id"])
                        )
            
            return updated_game
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
                    p.points_awarded
                FROM games g
                LEFT JOIN picks p ON g.id = p.game_id AND p.user_id = %s
                ORDER BY g.game_date
            """, (current_user.id,))
            picks = cur.fetchall()
            return picks
    except Exception as e:
        logger.error(f"Error fetching user picks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/user_picks_status")
async def get_user_picks_status(current_user: User = Depends(get_current_admin_user)):
    """Get the picks status for all users."""
    with get_db_cursor() as cur:
        current_time = datetime.now()
        
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
        
        # Get all users and their picks count for upcoming games and tiebreakers
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
            )
            SELECT 
                u.username, 
                u.full_name,
                COALESCE(up.picks_count, 0) + COALESCE(utp.picks_count, 0) as total_picks_made
            FROM users u
            LEFT JOIN upcoming_picks up ON u.id = up.user_id
            LEFT JOIN upcoming_tiebreaker_picks utp ON u.id = utp.user_id
            ORDER BY u.username
        """, (current_time, current_time))
        
        users_status = []
        for row in cur.fetchall():
            users_status.append(UserPicksStatus(
                username=row['username'],
                full_name=row['full_name'],
                total_games=total_required_picks,
                picks_made=row['total_picks_made'],
                is_complete=row['total_picks_made'] == total_required_picks
            ))
        
        return users_status

class Pick(BaseModel):
    game_id: int
    picked_team: str

class Tiebreaker(BaseModel):
    question: str
    start_time: datetime

class TiebreakerUpdate(BaseModel):
    question: str
    start_time: datetime
    answer: Optional[Union[str, float]] = None
    is_active: bool = True

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
    except Exception as e:
        logger.error(f"Error creating tiebreaker: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tiebreakers")
def get_tiebreakers():
    """Get all tiebreakers."""
    try:
        with get_db_cursor() as cur:
            logger.info("Fetching all tiebreakers")
            cur.execute("SELECT * FROM tiebreakers ORDER BY start_time")
            tiebreakers = cur.fetchall()
            logger.info(f"Found {len(tiebreakers)} tiebreakers")
            return tiebreakers
    except Exception as e:
        logger.error(f"Error fetching tiebreakers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live_tiebreakers")
def get_live_tiebreakers():
    """Get all live tiebreakers (tiebreakers that have started but don't have an answer yet)."""
    try:
        with get_db_cursor() as cur:
            current_time = datetime.now()
            logger.info(f"Checking live tiebreakers at {current_time}")
            
            cur.execute("""
                SELECT 
                    t.id as tiebreaker_id,
                    t.question,
                    t.start_time,
                    t.is_active,
                    COALESCE(
                        json_agg(
                            json_build_object(
                                'username', u.username,
                                'full_name', u.full_name,
                                'answer', tp.answer
                            )
                        ) FILTER (WHERE u.username IS NOT NULL),
                        '[]'
                    ) as picks
                FROM tiebreakers t
                LEFT JOIN tiebreaker_picks tp ON t.id = tp.tiebreaker_id
                LEFT JOIN users u ON tp.user_id = u.id
                WHERE t.start_time <= %s 
                AND t.is_active = TRUE
                AND t.answer IS NULL
                GROUP BY t.id
                ORDER BY t.start_time DESC
            """, (current_time,))
            tiebreakers = cur.fetchall()
            logger.info(f"Found {len(tiebreakers)} live tiebreakers")
            return tiebreakers
    except Exception as e:
        logger.error(f"Error fetching live tiebreakers: {str(e)}")
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
            return picks
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
                    p.points_awarded
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
    """Create an admin user if no admin exists."""
    try:
        with get_db_cursor(commit=True) as cur:
            # Check if any admin exists
            cur.execute("SELECT id FROM users WHERE is_admin = TRUE")
            # if cur.fetchone():
            #     return
            
            # Create admin user
            admin_password = password  # This is a temporary password
            hashed_password = get_password_hash(admin_password)
            cur.execute(
                """
                INSERT INTO users (username, full_name, password_hash, is_admin)
                VALUES (%s, %s, %s, TRUE)
                RETURNING id
                """,
                (username, full_name, hashed_password)
            )
            admin_id = cur.fetchone()["id"]
            
            # Create leaderboard entry for admin
            cur.execute(
                "INSERT INTO leaderboard (user_id) VALUES (%s)",
                (admin_id,)
            )
            
            logger.info("Created admin user with username: admin and password: admin123")
    except Exception as e:
        logger.error(f"Error creating admin user: {str(e)}")

def wipe_all_admin_users():
    with get_db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM users WHERE is_admin = TRUE")

# Initialize database
with get_db_connection() as conn:
    db.create_tables(conn)
    #create_admin_user(username, full_name, password)

@app.get("/user_all_past_picks/{username}")
async def get_user_all_past_picks(username: str):
    """Get all past picks (games and tiebreakers that have started) for a specific user."""
    try:
        with get_db_cursor() as cur:
            current_time = datetime.now()
            
            # Get user info
            cur.execute("SELECT id, username, full_name FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Get all game picks for games that have started
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
                LEFT JOIN picks p ON g.id = p.game_id AND p.user_id = %s
                WHERE g.game_date <= %s
                ORDER BY g.game_date DESC
            """, (user['id'], current_time))
            game_picks = cur.fetchall()

            # Get all tiebreaker picks for tiebreakers that have started
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
                WHERE t.start_time <= %s
                ORDER BY t.start_time DESC
            """, (user['id'], current_time))
            tiebreaker_picks = cur.fetchall()

            return {
                "user": user,
                "game_picks": game_picks,
                "tiebreaker_picks": tiebreaker_picks
            }
    except Exception as e:
        logger.error(f"Error fetching user past picks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Run the server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)