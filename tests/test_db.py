import os
from datetime import datetime, date
from unittest.mock import MagicMock, patch

import pytest

from src.db import (
    create_tables,
    get_creator_by_name,
    get_unbackfilled_creators,
    get_unenriched_games,
    insert_creator,
    insert_game,
    mark_creator_backfilled,
    update_game_ratings,
    upsert_creator_score,
)
from src.models import Creator, CreatorScore, Game


@pytest.fixture
def mock_env(monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv("POSTGRES_DATABASE", "test_db")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")


def test_create_tables(mock_env):
    """Test that create_tables executes SQL without errors."""
    with patch("src.db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        create_tables()

        # Verify connection was established
        mock_connect.assert_called_once()
        # Verify SQL was executed multiple times for schema setup
        # 3 CREATE TABLE + 5 ALTER TABLE + 2 constraint checks + 2 CREATE INDEX = 12 minimum
        assert mock_cursor.execute.call_count >= 12
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()


def test_insert_creator(mock_env):
    """Test inserting a new creator."""
    with patch("src.db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (123,)

        creator = Creator(
            id=None,
            name="testdev",
            profile_url="https://testdev.itch.io",
            backfilled=False,
            first_seen=datetime.now()
        )

        result = insert_creator(creator)

        assert result == 123
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()


def test_insert_game(mock_env):
    """Test inserting a new game."""
    with patch("src.db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # First call returns creator_id, second returns game id
        mock_cursor.fetchone.side_effect = [(1,), (456,)]

        game = Game(
            id=None,
            itch_id="test-game-123",
            title="Test Game",
            creator_name="testdev",
            url="https://testdev.itch.io/test-game",
            publish_date=date(2024, 1, 1),
            rating=None,
            rating_count=0,
            comment_count=0,
            description=None,
            tags=None,
            scraped_at=None
        )

        result = insert_game(game)

        assert result == 456
        assert mock_cursor.execute.call_count == 2  # creator lookup + insert
        mock_conn.commit.assert_called_once()


def test_insert_game_missing_creator(mock_env):
    """Test inserting a game with missing creator returns None."""
    with patch("src.db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Creator lookup returns None
        mock_cursor.fetchone.return_value = None

        game = Game(
            id=None,
            itch_id="orphan-game",
            title="Orphan Game",
            creator_name="missingdev",
            url="https://missingdev.itch.io/orphan-game",
            publish_date=date(2024, 1, 1),
            rating=None,
            rating_count=0,
            comment_count=0,
            description=None,
            tags=None,
            scraped_at=None
        )

        result = insert_game(game)

        assert result is None
        assert mock_cursor.execute.call_count == 1  # creator lookup only
def test_get_creator_by_name(mock_env):
    """Test fetching a creator by name."""
    with patch("src.db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = {
            "id": 1,
            "name": "testdev",
            "profile_url": "https://testdev.itch.io",
            "backfilled": False,
            "first_seen": datetime(2024, 1, 1)
        }

        result = get_creator_by_name("testdev")

        assert result is not None
        assert result.name == "testdev"
        assert result.id == 1
        assert result.backfilled is False


def test_get_creator_by_name_not_found(mock_env):
    """Test fetching a non-existent creator."""
    with patch("src.db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = get_creator_by_name("nonexistent")

        assert result is None


def test_get_unbackfilled_creators(mock_env):
    """Test fetching unbackfilled creators."""
    with patch("src.db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "name": "dev1",
                "profile_url": "https://dev1.itch.io",
                "backfilled": False,
                "first_seen": datetime(2024, 1, 1)
            },
            {
                "id": 2,
                "name": "dev2",
                "profile_url": "https://dev2.itch.io",
                "backfilled": False,
                "first_seen": datetime(2024, 1, 2)
            }
        ]

        result = get_unbackfilled_creators()

        assert len(result) == 2
        assert result[0].name == "dev1"
        assert result[1].name == "dev2"


def test_get_unenriched_games(mock_env):
    """Test fetching games without ratings."""
    with patch("src.db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "itch_id": "game-1",
                "title": "Game 1",
                "creator_name": "dev1",
                "url": "https://dev1.itch.io/game-1",
                "publish_date": date(2024, 1, 1),
                "rating": None,
                "rating_count": 0,
                "comment_count": 0,
                "description": None,
                "tags": None,
                "scraped_at": None
            }
        ]

        result = get_unenriched_games()

        assert len(result) == 1
        assert result[0].title == "Game 1"
        assert result[0].scraped_at is None


def test_get_unenriched_games_with_zero_rating(mock_env):
    """Test that 0.0 rating is preserved and not coerced to None."""
    with patch("src.db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "itch_id": "game-zero-rating",
                "title": "Game with Zero Rating",
                "creator_name": "dev1",
                "url": "https://dev1.itch.io/game-zero-rating",
                "publish_date": date(2024, 1, 1),
                "rating": 0.0,  # Zero rating should be preserved
                "rating_count": 10,
                "comment_count": 0,
                "description": None,
                "tags": None,
                "scraped_at": None
            }
        ]

        result = get_unenriched_games()

        assert len(result) == 1
        assert result[0].rating == 0.0  # Should NOT be None
        assert result[0].rating_count == 10


def test_get_unenriched_games_with_null_creator(mock_env):
    """Test that games with NULL creator_id are included (LEFT JOIN)."""
    with patch("src.db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "itch_id": "orphaned-game",
                "title": "Orphaned Game",
                "creator_name": None,  # NULL creator_id
                "url": "https://example.itch.io/orphaned-game",
                "publish_date": date(2024, 1, 1),
                "rating": None,
                "rating_count": 0,
                "comment_count": 0,
                "description": None,
                "tags": None,
                "scraped_at": None
            }
        ]

        result = get_unenriched_games()

        assert len(result) == 1
        assert result[0].title == "Orphaned Game"
        assert result[0].creator_name == "unknown"  # NULL mapped to "unknown"


def test_get_unenriched_games_includes_missing_metadata(mock_env):
    """Test that query includes missing metadata criteria."""
    with patch("src.db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = []

        get_unenriched_games()

        args = mock_cursor.execute.call_args[0]
        query = args[0]
        assert "g.description IS NULL" in query
        assert "g.publish_date IS NULL" in query
        assert "g.title IS NULL" in query


def test_mark_game_failed_sets_cooldown(mock_env):
    """Test marking a game as failed uses a cooldown interval."""
    with patch("src.db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        from src.db import mark_game_failed

        mark_game_failed(42, cooldown_days=5)

        args = mock_cursor.execute.call_args[0]
        assert "make_interval" in args[0]
        assert args[1] == (5, 42)


def test_update_game_ratings(mock_env):
    """Test updating game ratings."""
    with patch("src.db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        update_game_ratings(1, 4.5, 100, comment_count=25, description="A cool game")

        mock_cursor.execute.assert_called_once()
        args = mock_cursor.execute.call_args[0]
        # SQL params order: rating, rating_count, comment_count, description, tags,
        #                   publish_date, title, scraped_at, game_id
        assert args[1][0] == 4.5  # rating
        assert args[1][1] == 100  # rating_count
        assert args[1][2] == 25   # comment_count
        assert args[1][3] == "A cool game"  # description
        assert args[1][8] == 1    # game_id (last param)


def test_mark_creator_backfilled(mock_env):
    """Test marking a creator as backfilled."""
    with patch("src.db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mark_creator_backfilled(1)

        mock_cursor.execute.assert_called_once()
        assert "backfilled = TRUE" in mock_cursor.execute.call_args[0][0]


def test_upsert_creator_score(mock_env):
    """Test upserting a creator score."""
    with patch("src.db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        score = CreatorScore(
            creator_id=1,
            game_count=10,
            total_ratings=500,
            avg_rating=4.2,
            bayesian_score=4.15
        )

        upsert_creator_score(score)

        mock_cursor.execute.assert_called_once()
        args = mock_cursor.execute.call_args[0]
        assert args[1][0] == 1  # creator_id
        assert args[1][1] == 10  # game_count
        assert args[1][2] == 500  # total_ratings
