from datetime import datetime, date
from pathlib import Path
from unittest.mock import patch

import pytest

from src.enricher import enrich_all, enrich_game
from src.models import Game


@pytest.fixture
def sample_game():
    """Create a sample game for testing."""
    return Game(
        id=1,
        itch_id="cool-adventure",
        title="Cool Adventure Game",
        creator_name="testdev",
        url="https://testdev.itch.io/cool-adventure",
        publish_date=date(2024, 1, 15),
        rating=None,
        rating_count=0,
        comment_count=0,
        description=None,
        tags=None,
        scraped_at=None
    )


@pytest.fixture
def sample_game_html():
    """Load sample game HTML with ratings."""
    fixture_path = Path(__file__).parent / "fixtures" / "game_sample.html"
    return fixture_path.read_text()


@pytest.fixture
def sample_game_no_ratings_html():
    """Load sample game HTML without ratings."""
    fixture_path = Path(__file__).parent / "fixtures" / "game_no_ratings.html"
    return fixture_path.read_text()


def test_enrich_game(sample_game, sample_game_html):
    """Test enriching a single game."""
    with patch("src.enricher.fetch") as mock_fetch, \
         patch("src.enricher.db.update_game_ratings") as mock_update:

        mock_fetch.return_value = sample_game_html

        result = enrich_game(sample_game)

        assert result is True

        # Should have fetched the game page
        mock_fetch.assert_called_once_with("https://testdev.itch.io/cool-adventure")

        # Should have updated ratings (not hidden since we have a rating)
        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args[1]
        assert call_kwargs["game_id"] == 1
        assert call_kwargs["rating"] == 4.5
        assert call_kwargs["rating_count"] == 150
        assert call_kwargs["comment_count"] == 0
        assert call_kwargs["ratings_hidden"] is False
        # description is extracted from the page


def test_enrich_game_no_ratings(sample_game, sample_game_no_ratings_html):
    """Test enriching a game without ratings."""
    with patch("src.enricher.fetch") as mock_fetch, \
         patch("src.enricher.db.update_game_ratings") as mock_update:

        mock_fetch.return_value = sample_game_no_ratings_html

        result = enrich_game(sample_game)

        assert result is True

        # Should have updated with None rating and marked as hidden
        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args[1]
        assert call_kwargs["game_id"] == 1
        assert call_kwargs["rating"] is None
        assert call_kwargs["rating_count"] == 0
        assert call_kwargs["comment_count"] == 0
        assert call_kwargs["ratings_hidden"] is True


def test_enrich_all():
    """Test enriching all unenriched games."""
    game1 = Game(1, "game1", "Game 1", "dev1", "https://dev1.itch.io/game1",
                 date(2024, 1, 1), None, 0, 0, None, None, None)
    game2 = Game(2, "game2", "Game 2", "dev2", "https://dev2.itch.io/game2",
                 date(2024, 1, 2), None, 0, 0, None, None, None)

    with patch("src.enricher.db.get_unenriched_games") as mock_get_games, \
         patch("src.enricher.enrich_game") as mock_enrich_game:

        mock_get_games.return_value = [game1, game2]
        mock_enrich_game.return_value = True

        result = enrich_all()

        assert result["games_processed"] == 2
        assert result["errors"] == 0

        # Should have enriched both games
        assert mock_enrich_game.call_count == 2


def test_enrich_all_with_errors():
    """Test enriching with some errors."""
    game1 = Game(1, "game1", "Game 1", "dev1", "https://dev1.itch.io/game1",
                 date(2024, 1, 1), None, 0, 0, None, None, None)
    game2 = Game(2, "game2", "Game 2", "dev2", "https://dev2.itch.io/game2",
                 date(2024, 1, 2), None, 0, 0, None, None, None)
    game3 = Game(3, "game3", "Game 3", "dev3", "https://dev3.itch.io/game3",
                 date(2024, 1, 3), None, 0, 0, None, None, None)

    with patch("src.enricher.db.get_unenriched_games") as mock_get_games, \
         patch("src.enricher.enrich_game") as mock_enrich_game, \
         patch("src.enricher.db.mark_game_failed") as mock_mark_failed:

        mock_get_games.return_value = [game1, game2, game3]
        # First succeeds, second fails, third succeeds
        mock_enrich_game.side_effect = [True, Exception("Network error"), True]

        result = enrich_all()

        assert result["games_processed"] == 2  # Only successful ones
        assert result["errors"] == 1
        # Failed game should be marked with cooldown
        mock_mark_failed.assert_called_once_with(2)


def test_enrich_all_no_games():
    """Test enriching when there are no unenriched games."""
    with patch("src.enricher.db.get_unenriched_games") as mock_get_games:
        mock_get_games.return_value = []

        result = enrich_all()

        assert result["games_processed"] == 0
        assert result["errors"] == 0


def test_enrich_game_fetch_failure(sample_game):
    """Test handling fetch failures."""
    with patch("src.enricher.fetch") as mock_fetch:
        mock_fetch.side_effect = Exception("Network error")

        with pytest.raises(Exception):
            enrich_game(sample_game)


def test_enrich_game_calls_http_client(sample_game, sample_game_html):
    """Test that enrich_game uses the HTTP client."""
    with patch("src.enricher.fetch") as mock_fetch, \
         patch("src.enricher.db.update_game_ratings"):

        mock_fetch.return_value = sample_game_html

        enrich_game(sample_game)

        # Verify fetch was called with the game URL
        mock_fetch.assert_called_once_with(sample_game.url)
