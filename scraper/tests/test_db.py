"""Tests for database module."""

import os
from datetime import date, datetime

import pytest

from src.db import (
    Creator,
    CreatorScore,
    Game,
    create_tables,
    get_connection,
    get_creator_by_name,
    get_unenriched_games,
    get_unbackfilled_creators,
    insert_creator,
    insert_game,
    mark_creator_backfilled,
    update_game_ratings,
    upsert_creator_score,
)


@pytest.fixture(scope="module")
def setup_database():
    """Create tables before running tests."""
    create_tables()
    yield
    # Cleanup after tests
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM creator_scores")
            cur.execute("DELETE FROM games")
            cur.execute("DELETE FROM creators")


@pytest.fixture
def cleanup_test_data():
    """Clean up test data after each test."""
    yield
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM creator_scores")
            cur.execute("DELETE FROM games")
            cur.execute("DELETE FROM creators")


class TestConnection:
    """Tests for database connection."""

    def test_get_connection_succeeds(self, setup_database):
        """Should successfully connect to database."""
        with get_connection() as conn:
            assert conn is not None
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
                assert result[0] == 1


class TestCreateTables:
    """Tests for schema creation."""

    def test_create_tables_creates_creators_table(self, setup_database):
        """Should create creators table."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'creators')"
                )
                assert cur.fetchone()[0] is True

    def test_create_tables_creates_games_table(self, setup_database):
        """Should create games table."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'games')"
                )
                assert cur.fetchone()[0] is True

    def test_create_tables_creates_creator_scores_table(self, setup_database):
        """Should create creator_scores table."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'creator_scores')"
                )
                assert cur.fetchone()[0] is True


class TestCreatorCRUD:
    """Tests for creator CRUD operations."""

    def test_insert_creator_returns_id(self, setup_database, cleanup_test_data):
        """Should insert creator and return id."""
        creator = Creator(
            id=None,
            name="test_creator",
            profile_url="https://test_creator.itch.io",
            backfilled=False,
            first_seen=datetime.now(),
        )
        creator_id = insert_creator(creator)
        assert creator_id > 0

    def test_insert_creator_upserts_on_conflict(self, setup_database, cleanup_test_data):
        """Should update existing creator on name conflict."""
        creator = Creator(
            id=None,
            name="duplicate_creator",
            profile_url="https://duplicate_creator.itch.io",
            backfilled=False,
            first_seen=datetime.now(),
        )
        first_id = insert_creator(creator)
        second_id = insert_creator(creator)
        assert first_id == second_id

    def test_get_creator_by_name_returns_creator(self, setup_database, cleanup_test_data):
        """Should return creator when found."""
        creator = Creator(
            id=None,
            name="findable_creator",
            profile_url="https://findable_creator.itch.io",
            backfilled=False,
            first_seen=datetime.now(),
        )
        insert_creator(creator)

        found = get_creator_by_name("findable_creator")
        assert found is not None
        assert found.name == "findable_creator"
        assert found.profile_url == "https://findable_creator.itch.io"

    def test_get_creator_by_name_returns_none_when_not_found(self, setup_database, cleanup_test_data):
        """Should return None when creator not found."""
        found = get_creator_by_name("nonexistent_creator")
        assert found is None

    def test_get_unbackfilled_creators(self, setup_database, cleanup_test_data):
        """Should return only unbackfilled creators."""
        # Insert backfilled creator
        backfilled = Creator(
            id=None,
            name="backfilled_creator",
            profile_url="https://backfilled_creator.itch.io",
            backfilled=True,
            first_seen=datetime.now(),
        )
        insert_creator(backfilled)

        # Insert unbackfilled creator
        unbackfilled = Creator(
            id=None,
            name="unbackfilled_creator",
            profile_url="https://unbackfilled_creator.itch.io",
            backfilled=False,
            first_seen=datetime.now(),
        )
        insert_creator(unbackfilled)

        result = get_unbackfilled_creators()
        names = [c.name for c in result]
        assert "unbackfilled_creator" in names
        assert "backfilled_creator" not in names

    def test_mark_creator_backfilled(self, setup_database, cleanup_test_data):
        """Should mark creator as backfilled."""
        creator = Creator(
            id=None,
            name="to_backfill",
            profile_url="https://to_backfill.itch.io",
            backfilled=False,
            first_seen=datetime.now(),
        )
        creator_id = insert_creator(creator)

        mark_creator_backfilled(creator_id)

        found = get_creator_by_name("to_backfill")
        assert found is not None
        assert found.backfilled is True


class TestGameCRUD:
    """Tests for game CRUD operations."""

    def test_insert_game_returns_id(self, setup_database, cleanup_test_data):
        """Should insert game and return id."""
        # First insert creator
        creator = Creator(
            id=None,
            name="game_creator",
            profile_url="https://game_creator.itch.io",
            backfilled=False,
            first_seen=datetime.now(),
        )
        insert_creator(creator)

        game = Game(
            id=None,
            itch_id="test-game-123",
            title="Test Game",
            creator_name="game_creator",
            url="https://game_creator.itch.io/test-game",
            publish_date=date.today(),
            rating=None,
            rating_count=0,
            scraped_at=None,
        )
        game_id = insert_game(game)
        assert game_id > 0

    def test_insert_game_upserts_on_conflict(self, setup_database, cleanup_test_data):
        """Should update existing game on itch_id conflict."""
        creator = Creator(
            id=None,
            name="upsert_game_creator",
            profile_url="https://upsert_game_creator.itch.io",
            backfilled=False,
            first_seen=datetime.now(),
        )
        insert_creator(creator)

        game = Game(
            id=None,
            itch_id="upsert-game",
            title="Original Title",
            creator_name="upsert_game_creator",
            url="https://upsert_game_creator.itch.io/upsert-game",
            publish_date=date.today(),
            rating=None,
            rating_count=0,
            scraped_at=None,
        )
        first_id = insert_game(game)

        game.title = "Updated Title"
        second_id = insert_game(game)

        assert first_id == second_id

    def test_get_unenriched_games(self, setup_database, cleanup_test_data):
        """Should return only games without scraped_at."""
        creator = Creator(
            id=None,
            name="enrichment_creator",
            profile_url="https://enrichment_creator.itch.io",
            backfilled=False,
            first_seen=datetime.now(),
        )
        insert_creator(creator)

        # Insert unenriched game
        unenriched = Game(
            id=None,
            itch_id="unenriched-game",
            title="Unenriched Game",
            creator_name="enrichment_creator",
            url="https://enrichment_creator.itch.io/unenriched-game",
            publish_date=date.today(),
            rating=None,
            rating_count=0,
            scraped_at=None,
        )
        insert_game(unenriched)

        # Insert enriched game
        enriched = Game(
            id=None,
            itch_id="enriched-game",
            title="Enriched Game",
            creator_name="enrichment_creator",
            url="https://enrichment_creator.itch.io/enriched-game",
            publish_date=date.today(),
            rating=4.5,
            rating_count=100,
            scraped_at=datetime.now(),
        )
        insert_game(enriched)

        result = get_unenriched_games()
        itch_ids = [g.itch_id for g in result]
        assert "unenriched-game" in itch_ids
        assert "enriched-game" not in itch_ids

    def test_update_game_ratings(self, setup_database, cleanup_test_data):
        """Should update game ratings and set scraped_at."""
        creator = Creator(
            id=None,
            name="rating_creator",
            profile_url="https://rating_creator.itch.io",
            backfilled=False,
            first_seen=datetime.now(),
        )
        insert_creator(creator)

        game = Game(
            id=None,
            itch_id="rating-game",
            title="Rating Game",
            creator_name="rating_creator",
            url="https://rating_creator.itch.io/rating-game",
            publish_date=date.today(),
            rating=None,
            rating_count=0,
            scraped_at=None,
        )
        game_id = insert_game(game)

        update_game_ratings(game_id, 4.2, 50)

        # Verify update
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT rating, rating_count, scraped_at FROM games WHERE id = %s", (game_id,))
                row = cur.fetchone()
                assert float(row[0]) == 4.2
                assert row[1] == 50
                assert row[2] is not None  # scraped_at should be set


class TestCreatorScoreCRUD:
    """Tests for creator score CRUD operations."""

    def test_upsert_creator_score_inserts(self, setup_database, cleanup_test_data):
        """Should insert new creator score."""
        creator = Creator(
            id=None,
            name="score_creator",
            profile_url="https://score_creator.itch.io",
            backfilled=False,
            first_seen=datetime.now(),
        )
        creator_id = insert_creator(creator)

        score = CreatorScore(
            creator_id=creator_id,
            game_count=5,
            total_ratings=100,
            avg_rating=4.2,
            bayesian_score=3.8,
        )
        upsert_creator_score(score)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT game_count, total_ratings, avg_rating, bayesian_score FROM creator_scores WHERE creator_id = %s",
                    (creator_id,),
                )
                row = cur.fetchone()
                assert row[0] == 5
                assert row[1] == 100
                assert float(row[2]) == 4.2
                assert float(row[3]) == 3.8

    def test_upsert_creator_score_updates(self, setup_database, cleanup_test_data):
        """Should update existing creator score."""
        creator = Creator(
            id=None,
            name="update_score_creator",
            profile_url="https://update_score_creator.itch.io",
            backfilled=False,
            first_seen=datetime.now(),
        )
        creator_id = insert_creator(creator)

        # Insert initial score
        score = CreatorScore(
            creator_id=creator_id,
            game_count=5,
            total_ratings=100,
            avg_rating=4.2,
            bayesian_score=3.8,
        )
        upsert_creator_score(score)

        # Update score
        updated_score = CreatorScore(
            creator_id=creator_id,
            game_count=10,
            total_ratings=200,
            avg_rating=4.5,
            bayesian_score=4.2,
        )
        upsert_creator_score(updated_score)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT game_count, total_ratings, avg_rating, bayesian_score FROM creator_scores WHERE creator_id = %s",
                    (creator_id,),
                )
                row = cur.fetchone()
                assert row[0] == 10
                assert row[1] == 200
                assert float(row[2]) == 4.5
                assert float(row[3]) == 4.2
