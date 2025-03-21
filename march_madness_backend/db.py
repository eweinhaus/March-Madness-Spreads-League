import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """Create a new database connection."""
    try:
        logger.info("Creating database connection...")
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        # Set timezone to UTC for this connection
        with conn.cursor() as cur:
            cur.execute("SET timezone TO 'UTC'")
        logger.info("Database connection successful")
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        raise

def create_tables(conn):
    """Create tables if they don't exist."""
    try:
        logger.info("Creating database tables...")
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    full_name VARCHAR(100) NOT NULL,
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
                
                CREATE TABLE IF NOT EXISTS tiebreakers (
                    id SERIAL PRIMARY KEY,
                    question TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    answer TEXT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS tiebreaker_picks (
                    id SERIAL PRIMARY KEY,
                    user_id INT REFERENCES users(id) ON DELETE CASCADE,
                    tiebreaker_id INT REFERENCES tiebreakers(id) ON DELETE CASCADE,
                    answer TEXT NOT NULL,
                    points_awarded FLOAT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, tiebreaker_id)
                );
            """)
            conn.commit()
            logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        conn.rollback()
        raise

# Create initial connection and tables
conn = get_db_connection()
create_tables(conn)
