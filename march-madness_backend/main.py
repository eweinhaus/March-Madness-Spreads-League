from fastapi import HTTPException
from datetime import datetime
from .database import get_db_cursor
from .logger import logger

@app.get("/live_games")
def get_live_games():
    """Get all live games (games that have started but don't have a winner yet) and their picks."""
    try:
        with get_db_cursor() as cur:
            current_time = datetime.now()
            logger.info(f"Checking live games at {current_time}")
            
            # First get all games to log their dates
            cur.execute("SELECT id, game_date, winning_team FROM games")
            all_games = cur.fetchall()
            for game in all_games:
                logger.info(f"Game {game['id']}: date={game['game_date']}, winner={game['winning_team']}, is_live={game['game_date'] <= current_time and game['winning_team'] is None}")
            
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
            return games
    except Exception as e:
        logger.error(f"Error fetching live games: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 