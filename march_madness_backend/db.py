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
            """)
            conn.commit()
            logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        conn.rollback()
        raise

def drop_and_recreate_tables(conn):
    """Drop and recreate all tables."""
    try:
        logger.info("Dropping and recreating database tables...")
        with conn.cursor() as cur:
            # Drop existing tables in correct order (respecting foreign key constraints)
            cur.execute("""
                DROP TABLE IF EXISTS picks CASCADE;
                DROP TABLE IF EXISTS games CASCADE;
                DROP TABLE IF EXISTS leaderboard CASCADE;
                DROP TABLE IF EXISTS users CASCADE;
            """)
            
            # Create tables
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
            """)
            conn.commit()
            logger.info("Database tables dropped and recreated successfully")
    except Exception as e:
        logger.error(f"Error dropping and recreating tables: {str(e)}")
        conn.rollback()
        raise

# Create initial connection and tables
conn = get_db_connection()
drop_and_recreate_tables(conn)
