import os
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

from .models import Creator, CreatorScore, Game

load_dotenv()


def get_connection_string() -> str:
    """Get database connection string from environment.

    Supports POSTGRES_URL or individual POSTGRES_* variables.
    """
    url = os.getenv("POSTGRES_URL")
    if url:
        return url

    # Build from individual components
    host = os.getenv("POSTGRES_HOST")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    database = os.getenv("POSTGRES_DATABASE")
    port = os.getenv("POSTGRES_PORT", "5432")

    if not all([host, user, password, database]):
        raise ValueError(
            "Missing database configuration. Set POSTGRES_URL or individual POSTGRES_* variables."
        )

    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


@contextmanager
def get_connection() -> Iterator[psycopg2.extensions.connection]:
    """Context manager for database connections."""
    conn = psycopg2.connect(get_connection_string())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_tables() -> None:
    """Initialize database schema."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS creators (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                profile_url VARCHAR(512) NOT NULL,
                backfilled BOOLEAN DEFAULT FALSE,
                first_seen TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id SERIAL PRIMARY KEY,
                itch_id VARCHAR(255) UNIQUE,
                title VARCHAR(512) NOT NULL,
                creator_id INTEGER REFERENCES creators(id),
                url VARCHAR(512) NOT NULL,
                publish_date DATE,
                rating DECIMAL(3,2),
                rating_count INTEGER DEFAULT 0,
                scraped_at TIMESTAMP,
                ratings_hidden BOOLEAN DEFAULT FALSE,
                ratings_hidden_until TIMESTAMP,
                comment_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Add columns for existing databases
        cursor.execute("""
            ALTER TABLE games ADD COLUMN IF NOT EXISTS ratings_hidden BOOLEAN DEFAULT FALSE
        """)
        cursor.execute("""
            ALTER TABLE games ADD COLUMN IF NOT EXISTS ratings_hidden_until TIMESTAMP
        """)
        cursor.execute("""
            ALTER TABLE games ADD COLUMN IF NOT EXISTS comment_count INTEGER DEFAULT 0
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS creator_scores (
                id SERIAL PRIMARY KEY,
                creator_id INTEGER REFERENCES creators(id) UNIQUE,
                game_count INTEGER DEFAULT 0,
                total_ratings INTEGER DEFAULT 0,
                avg_rating DECIMAL(3,2),
                bayesian_score DECIMAL(5,4),
                calculated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_games_creator ON games(creator_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_scores_bayesian
            ON creator_scores(bayesian_score DESC)
        """)

        cursor.close()


def insert_creator(creator: Creator) -> int:
    """Insert a creator and return their ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO creators (name, profile_url, backfilled, first_seen)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name) DO NOTHING
            RETURNING id
            """,
            (creator.name, creator.profile_url, creator.backfilled, creator.first_seen)
        )
        result = cursor.fetchone()
        cursor.close()

        if result:
            return result[0]

        # If conflict occurred, fetch existing ID
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM creators WHERE name = %s", (creator.name,))
        result = cursor.fetchone()
        cursor.close()
        return result[0] if result else None


def insert_game(game: Game) -> int:
    """Insert a game and return its ID."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # First get creator_id
        cursor.execute("SELECT id FROM creators WHERE name = %s", (game.creator_name,))
        creator_result = cursor.fetchone()
        creator_id = creator_result[0] if creator_result else None

        cursor.execute(
            """
            INSERT INTO games (
                itch_id, title, creator_id, url, publish_date,
                rating, rating_count, scraped_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (itch_id) DO NOTHING
            RETURNING id
            """,
            (
                game.itch_id, game.title, creator_id, game.url,
                game.publish_date, game.rating, game.rating_count, game.scraped_at
            )
        )
        result = cursor.fetchone()
        cursor.close()

        if result:
            return result[0]

        # If conflict occurred, fetch existing ID
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM games WHERE itch_id = %s", (game.itch_id,))
        result = cursor.fetchone()
        cursor.close()
        return result[0] if result else None


def get_creator_by_name(name: str) -> Creator | None:
    """Fetch a creator by name."""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM creators WHERE name = %s", (name,))
        row = cursor.fetchone()
        cursor.close()

        if not row:
            return None

        return Creator(
            id=row["id"],
            name=row["name"],
            profile_url=row["profile_url"],
            backfilled=row["backfilled"],
            first_seen=row["first_seen"]
        )


def get_unbackfilled_creators() -> list[Creator]:
    """Fetch all creators that haven't been backfilled."""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM creators WHERE backfilled = FALSE")
        rows = cursor.fetchall()
        cursor.close()

        return [
            Creator(
                id=row["id"],
                name=row["name"],
                profile_url=row["profile_url"],
                backfilled=row["backfilled"],
                first_seen=row["first_seen"]
            )
            for row in rows
        ]


def get_unenriched_games() -> list[Game]:
    """Fetch all games that haven't been scraped for ratings or need re-enrichment."""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT g.*, c.name as creator_name
            FROM games g
            LEFT JOIN creators c ON g.creator_id = c.id
            WHERE g.scraped_at IS NULL
               OR (g.ratings_hidden = TRUE AND g.ratings_hidden_until < NOW())
        """)
        rows = cursor.fetchall()
        cursor.close()

        return [
            Game(
                id=row["id"],
                itch_id=row["itch_id"],
                title=row["title"],
                creator_name=row["creator_name"] if row["creator_name"] else "unknown",
                url=row["url"],
                publish_date=row["publish_date"],
                rating=float(row["rating"]) if row["rating"] is not None else None,
                rating_count=row["rating_count"],
                scraped_at=row["scraped_at"]
            )
            for row in rows
        ]


def update_game_ratings(
    game_id: int,
    rating: float | None,
    rating_count: int,
    comment_count: int = 0,
    ratings_hidden: bool = False
) -> None:
    """Update game ratings, comment count, and mark as scraped.

    Args:
        game_id: ID of the game to update
        rating: The game's rating (None if not available)
        rating_count: Number of ratings
        comment_count: Number of comments on the game
        ratings_hidden: If True, ratings were hidden and should be retried later
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        if ratings_hidden:
            # Set retry cooldown (7 days) without marking as fully scraped
            # Still update comment_count as it's always available
            cursor.execute(
                """
                UPDATE games
                SET ratings_hidden = TRUE, ratings_hidden_until = NOW() + INTERVAL '7 days',
                    comment_count = %s
                WHERE id = %s
                """,
                (comment_count, game_id)
            )
        else:
            cursor.execute(
                """
                UPDATE games
                SET rating = %s, rating_count = %s, comment_count = %s, scraped_at = %s,
                    ratings_hidden = FALSE, ratings_hidden_until = NULL
                WHERE id = %s
                """,
                (rating, rating_count, comment_count, datetime.now(), game_id)
            )
        cursor.close()


def mark_creator_backfilled(creator_id: int) -> None:
    """Mark a creator as backfilled."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE creators SET backfilled = TRUE, updated_at = %s WHERE id = %s",
            (datetime.now(), creator_id)
        )
        cursor.close()


def upsert_creator_score(score: CreatorScore) -> None:
    """Insert or update a creator's score."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO creator_scores (
                creator_id, game_count, total_ratings, avg_rating, bayesian_score, calculated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (creator_id) DO UPDATE SET
                game_count = EXCLUDED.game_count,
                total_ratings = EXCLUDED.total_ratings,
                avg_rating = EXCLUDED.avg_rating,
                bayesian_score = EXCLUDED.bayesian_score,
                calculated_at = EXCLUDED.calculated_at
            """,
            (
                score.creator_id, score.game_count, score.total_ratings,
                score.avg_rating, score.bayesian_score, datetime.now()
            )
        )
        cursor.close()
