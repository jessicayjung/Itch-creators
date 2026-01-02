"""Database connection and CRUD operations for itch-creators scraper."""

import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Generator

import psycopg2
from dotenv import load_dotenv

load_dotenv()


# Data Models


@dataclass
class Creator:
    id: int | None
    name: str
    profile_url: str
    backfilled: bool
    first_seen: datetime


@dataclass
class Game:
    id: int | None
    itch_id: str
    title: str
    creator_name: str
    url: str
    publish_date: date | None
    rating: float | None
    rating_count: int
    scraped_at: datetime | None


@dataclass
class CreatorScore:
    creator_id: int
    game_count: int
    total_ratings: int
    avg_rating: float
    bayesian_score: float


# Database Connection


def get_connection_string() -> str:
    """Get database connection string from environment."""
    url = os.getenv("POSTGRES_URL")
    if url:
        return url

    # Build from individual components
    host = os.getenv("POSTGRES_HOST")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    database = os.getenv("POSTGRES_DATABASE")

    if not all([host, user, password, database]):
        raise ValueError("Missing database configuration. Set POSTGRES_URL or individual POSTGRES_* variables.")

    return f"postgresql://{user}:{password}@{host}/{database}"


@contextmanager
def get_connection() -> Generator[psycopg2.extensions.connection, None, None]:
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


# Schema Creation


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS creators (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    profile_url VARCHAR(512) NOT NULL,
    backfilled BOOLEAN DEFAULT FALSE,
    first_seen TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

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
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS creator_scores (
    id SERIAL PRIMARY KEY,
    creator_id INTEGER REFERENCES creators(id) UNIQUE,
    game_count INTEGER DEFAULT 0,
    total_ratings INTEGER DEFAULT 0,
    avg_rating DECIMAL(3,2),
    bayesian_score DECIMAL(5,4),
    calculated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_games_creator ON games(creator_id);
CREATE INDEX IF NOT EXISTS idx_scores_bayesian ON creator_scores(bayesian_score DESC);
"""


def create_tables() -> None:
    """Initialize database schema."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)


# CRUD Operations


def insert_creator(creator: Creator) -> int:
    """Insert a creator and return their id."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO creators (name, profile_url, backfilled, first_seen)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET updated_at = NOW()
                RETURNING id
                """,
                (creator.name, creator.profile_url, creator.backfilled, creator.first_seen),
            )
            result = cur.fetchone()
            return result[0] if result else 0


def insert_game(game: Game) -> int:
    """Insert a game and return its id."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # First get creator_id
            cur.execute("SELECT id FROM creators WHERE name = %s", (game.creator_name,))
            creator_row = cur.fetchone()
            creator_id = creator_row[0] if creator_row else None

            cur.execute(
                """
                INSERT INTO games (itch_id, title, creator_id, url, publish_date, rating, rating_count, scraped_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (itch_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    rating = EXCLUDED.rating,
                    rating_count = EXCLUDED.rating_count,
                    scraped_at = EXCLUDED.scraped_at
                RETURNING id
                """,
                (
                    game.itch_id,
                    game.title,
                    creator_id,
                    game.url,
                    game.publish_date,
                    game.rating,
                    game.rating_count,
                    game.scraped_at,
                ),
            )
            result = cur.fetchone()
            return result[0] if result else 0


def get_creator_by_name(name: str) -> Creator | None:
    """Get a creator by name."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, profile_url, backfilled, first_seen FROM creators WHERE name = %s",
                (name,),
            )
            row = cur.fetchone()
            if row:
                return Creator(
                    id=row[0],
                    name=row[1],
                    profile_url=row[2],
                    backfilled=row[3],
                    first_seen=row[4],
                )
            return None


def get_unbackfilled_creators() -> list[Creator]:
    """Get all creators that haven't been backfilled."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, profile_url, backfilled, first_seen FROM creators WHERE backfilled = FALSE"
            )
            rows = cur.fetchall()
            return [
                Creator(id=row[0], name=row[1], profile_url=row[2], backfilled=row[3], first_seen=row[4])
                for row in rows
            ]


def get_unenriched_games() -> list[Game]:
    """Get all games that haven't been enriched with ratings."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT g.id, g.itch_id, g.title, c.name, g.url, g.publish_date, g.rating, g.rating_count, g.scraped_at
                FROM games g
                LEFT JOIN creators c ON g.creator_id = c.id
                WHERE g.scraped_at IS NULL
                """
            )
            rows = cur.fetchall()
            return [
                Game(
                    id=row[0],
                    itch_id=row[1],
                    title=row[2],
                    creator_name=row[3] or "",
                    url=row[4],
                    publish_date=row[5],
                    rating=float(row[6]) if row[6] else None,
                    rating_count=row[7],
                    scraped_at=row[8],
                )
                for row in rows
            ]


def update_game_ratings(game_id: int, rating: float | None, rating_count: int) -> None:
    """Update a game's rating information."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE games
                SET rating = %s, rating_count = %s, scraped_at = NOW()
                WHERE id = %s
                """,
                (rating, rating_count, game_id),
            )


def mark_creator_backfilled(creator_id: int) -> None:
    """Mark a creator as having been backfilled."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE creators SET backfilled = TRUE, updated_at = NOW() WHERE id = %s",
                (creator_id,),
            )


def upsert_creator_score(score: CreatorScore) -> None:
    """Insert or update a creator's score."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO creator_scores (creator_id, game_count, total_ratings, avg_rating, bayesian_score, calculated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (creator_id) DO UPDATE SET
                    game_count = EXCLUDED.game_count,
                    total_ratings = EXCLUDED.total_ratings,
                    avg_rating = EXCLUDED.avg_rating,
                    bayesian_score = EXCLUDED.bayesian_score,
                    calculated_at = NOW()
                """,
                (
                    score.creator_id,
                    score.game_count,
                    score.total_ratings,
                    score.avg_rating,
                    score.bayesian_score,
                ),
            )
