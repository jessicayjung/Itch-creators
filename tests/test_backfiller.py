from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.backfiller import _extract_game_id, backfill_all, backfill_creator
from src.models import Creator


@pytest.fixture
def sample_creator():
    """Create a sample creator for testing."""
    return Creator(
        id=1,
        name="testdev",
        profile_url="https://testdev.itch.io",
        backfilled=False,
        first_seen=datetime(2024, 1, 1)
    )


@pytest.fixture
def sample_profile_html():
    """Load sample profile HTML."""
    fixture_path = Path(__file__).parent / "fixtures" / "profile_sample.html"
    return fixture_path.read_text()


def test_backfill_creator(sample_creator, sample_profile_html):
    """Test backfilling a single creator."""
    with patch("src.backfiller.fetch") as mock_fetch, \
         patch("src.backfiller.db.insert_game") as mock_insert_game, \
         patch("src.backfiller.db.mark_creator_backfilled") as mock_mark_backfilled:

        mock_fetch.return_value = sample_profile_html
        mock_insert_game.return_value = 1  # Return a valid ID

        result = backfill_creator(sample_creator)

        # Should have fetched the profile
        mock_fetch.assert_called_once_with("https://testdev.itch.io")

        # Should have inserted 4 games (from fixture)
        assert mock_insert_game.call_count == 4
        assert result == 4

        # Should have marked creator as backfilled
        mock_mark_backfilled.assert_called_once_with(1)


def test_backfill_creator_empty_profile(sample_creator):
    """Test backfilling a creator with no games."""
    with patch("src.backfiller.fetch") as mock_fetch, \
         patch("src.backfiller.db.insert_game") as mock_insert_game, \
         patch("src.backfiller.db.mark_creator_backfilled") as mock_mark_backfilled:

        mock_fetch.return_value = "<html><body></body></html>"

        result = backfill_creator(sample_creator)

        # No games inserted
        assert result == 0
        mock_insert_game.assert_not_called()

        # Still marked as backfilled
        mock_mark_backfilled.assert_called_once_with(1)


def test_backfill_all():
    """Test backfilling all unbackfilled creators."""
    creator1 = Creator(1, "dev1", "https://dev1.itch.io", False, datetime(2024, 1, 1))
    creator2 = Creator(2, "dev2", "https://dev2.itch.io", False, datetime(2024, 1, 2))

    with patch("src.backfiller.db.get_unbackfilled_creators") as mock_get_creators, \
         patch("src.backfiller.backfill_creator") as mock_backfill_creator:

        mock_get_creators.return_value = [creator1, creator2]
        mock_backfill_creator.side_effect = [5, 3]  # Return game counts

        result = backfill_all()

        assert result["creators_processed"] == 2
        assert result["games_inserted"] == 8  # 5 + 3
        assert result["errors"] == 0

        # Should have called backfill_creator twice
        assert mock_backfill_creator.call_count == 2


def test_backfill_all_with_errors():
    """Test backfilling with some errors."""
    creator1 = Creator(1, "dev1", "https://dev1.itch.io", False, datetime(2024, 1, 1))
    creator2 = Creator(2, "dev2", "https://dev2.itch.io", False, datetime(2024, 1, 2))
    creator3 = Creator(3, "dev3", "https://dev3.itch.io", False, datetime(2024, 1, 3))

    with patch("src.backfiller.db.get_unbackfilled_creators") as mock_get_creators, \
         patch("src.backfiller.backfill_creator") as mock_backfill_creator:

        mock_get_creators.return_value = [creator1, creator2, creator3]
        # First succeeds, second fails, third succeeds
        mock_backfill_creator.side_effect = [5, Exception("Network error"), 3]

        result = backfill_all()

        assert result["creators_processed"] == 2  # Only successful ones
        assert result["games_inserted"] == 8  # 5 + 3
        assert result["errors"] == 1


def test_backfill_all_no_creators():
    """Test backfilling when there are no unbackfilled creators."""
    with patch("src.backfiller.db.get_unbackfilled_creators") as mock_get_creators:
        mock_get_creators.return_value = []

        result = backfill_all()

        assert result["creators_processed"] == 0
        assert result["games_inserted"] == 0
        assert result["errors"] == 0


def test_extract_game_id():
    """Test extracting game ID from URLs."""
    # Standard URL
    assert _extract_game_id("https://testdev.itch.io/cool-game") == "cool-game"

    # With query parameters
    assert _extract_game_id("https://testdev.itch.io/cool-game?secret=xyz") == "cool-game"

    # Different game
    assert _extract_game_id("https://testdev.itch.io/puzzle-master") == "puzzle-master"

    # With trailing slash
    assert _extract_game_id("https://testdev.itch.io/space-game/") == "space-game"

    # With both query params and trailing slash
    assert _extract_game_id("https://testdev.itch.io/another-game/?key=value") == "another-game"


def test_backfill_creator_inserts_correct_game_data(sample_creator, sample_profile_html):
    """Test that game data is correctly formatted for insertion."""
    with patch("src.backfiller.fetch") as mock_fetch, \
         patch("src.backfiller.db.insert_game") as mock_insert_game, \
         patch("src.backfiller.db.mark_creator_backfilled"):

        mock_fetch.return_value = sample_profile_html
        mock_insert_game.return_value = 1

        backfill_creator(sample_creator)

        # Check the first game inserted
        first_call = mock_insert_game.call_args_list[0]
        game = first_call[0][0]

        assert game.creator_name == "testdev"
        assert game.title == "Cool Adventure Game"
        assert game.itch_id == "cool-adventure"
        assert game.url == "https://testdev.itch.io/cool-adventure"
        assert game.rating is None
        assert game.rating_count == 0
        assert game.scraped_at is None
