from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging
from contextlib import contextmanager
from auth import (
    Token, UserCreate, UserLogin, User,
    verify_password, get_password_hash, create_access_token, verify_token
)
from typing import Optional
import urllib.parse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

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
            "SELECT id, username, email, is_admin FROM users WHERE username = %s",
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
            
            # Check if email exists
            cur.execute("SELECT id FROM users WHERE email = %s", (user.email,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            
            # Create user
            hashed_password = get_password_hash(user.password)
            cur.execute(
                """
                INSERT INTO users (username, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id, username, email, is_admin
                """,
                (user.username, user.email, hashed_password)
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
    half: int = 1  # 1 for "Start through 32", 2 for "16 through Finals"

    def __init__(self, **data):
        super().__init__(**data)
        # Truncate seconds from game_date
        self.game_date = self.game_date.replace(second=0, microsecond=0)

class GameUpdate(BaseModel):
    home_team: str
    away_team: str
    spread: float
    game_date: datetime
    winning_team: Optional[str] = None
    half: int = 1  # 1 for "Start through 32", 2 for "16 through Finals"

    def __init__(self, **data):
        super().__init__(**data)
        # Truncate seconds from game_date
        self.game_date = self.game_date.replace(second=0, microsecond=0)

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
            current_time = datetime.utcnow()
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
            cur.execute("""
                SELECT u.username, l.total_points 
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
            logger.info(f"Creating new game: {game}")
            cur.execute(
                """
                INSERT INTO games (home_team, away_team, spread, game_date, half)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
                """,
                (game.home_team, game.away_team, game.spread, game.game_date, game.half)
            )
            new_game = cur.fetchone()
            logger.info(f"Game created successfully: {new_game}")
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
            current_time = datetime.utcnow()
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
    try:
        with get_db_cursor() as cur:
            current_time = datetime.utcnow()
            four_hours_ago = current_time - timedelta(hours=4)
            logger.info(f"Checking live games at {current_time} UTC")
            
            # First get all games to log their dates
            cur.execute("SELECT id, game_date, winning_team FROM games")
            all_games = cur.fetchall()
            for game in all_games:
                logger.info(f"Game {game['id']}: date={game['game_date']} UTC, winner={game['winning_team']}, is_live={game['game_date'] <= current_time and game['game_date'] >= four_hours_ago and (game['winning_team'] is None or game['winning_team'] == '')}")
            
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
                                'picked_team', p.picked_team
                            )
                        ) FILTER (WHERE u.username IS NOT NULL),
                        '[]'
                    ) as picks
                FROM games g
                LEFT JOIN picks p ON g.id = p.game_id
                LEFT JOIN users u ON p.user_id = u.id
                WHERE g.game_date <= %s 
                AND g.game_date >= %s
                AND (g.winning_team IS NULL OR g.winning_team = '')
                GROUP BY g.id
                ORDER BY g.game_date DESC
            """, (current_time, four_hours_ago))
            games = cur.fetchall()
            logger.info(f"Found {len(games)} live games")
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
                SET home_team = %s, away_team = %s, spread = %s, game_date = %s, winning_team = %s, half = %s
                WHERE id = %s
                RETURNING *
                """,
                (game.home_team, game.away_team, game.spread, game.game_date, game.winning_team, game.half, game_id)
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

# Create tables on startup
def create_tables():
    with get_db_cursor(commit=True) as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS games (
            id SERIAL PRIMARY KEY,
            home_team VARCHAR(50) NOT NULL,
            away_team VARCHAR(50) NOT NULL,
            spread NUMERIC(4,1) NOT NULL,
            game_date TIMESTAMP NOT NULL,
            winning_team VARCHAR(50) NULL,
            half INT DEFAULT 1 CHECK (half IN (1, 2)),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS picks (
            id SERIAL PRIMARY KEY,
            user_id INT REFERENCES users(id) ON DELETE CASCADE,
            game_id INT REFERENCES games(id) ON DELETE CASCADE,
            picked_team VARCHAR(50) NOT NULL,
            points_awarded INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, game_id)
        );

        CREATE TABLE IF NOT EXISTS leaderboard (
            user_id INT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            total_points INT DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

def create_admin_user():
    """Create an admin user if no admin exists."""
    try:
        with get_db_cursor(commit=True) as cur:
            # Check if any admin exists
            cur.execute("SELECT id FROM users WHERE is_admin = TRUE")
            if cur.fetchone():
                return
            
            # Create admin user
            admin_password = "admin123"  # This is a temporary password
            hashed_password = get_password_hash(admin_password)
            cur.execute(
                """
                INSERT INTO users (username, email, password_hash, is_admin)
                VALUES (%s, %s, %s, TRUE)
                RETURNING id
                """,
                ("admin", "admin@example.com", hashed_password)
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

# Initialize database
create_tables()
create_admin_user()

# Run the server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)