from datetime import datetime
from pathlib import Path

import pytest

from src.parsers.profile import _parse_date_text, parse_profile


@pytest.fixture
def sample_profile_html():
    """Load sample profile HTML fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "profile_sample.html"
    return fixture_path.read_text()


def test_parse_profile(sample_profile_html):
    """Test parsing a creator profile page."""
    games, next_url = parse_profile(sample_profile_html)

    assert len(games) == 4

    # Check first game
    assert games[0]["title"] == "Cool Adventure Game"
    assert games[0]["url"] == "https://testdev.itch.io/cool-adventure"
    assert games[0]["publish_date"] == datetime(2024, 1, 15)

    # Check second game
    assert games[1]["title"] == "Puzzle Master"
    assert games[1]["url"] == "https://testdev.itch.io/puzzle-master"
    assert games[1]["publish_date"] == datetime(2024, 2, 20)

    # Check third game
    assert games[2]["title"] == "Space Game"
    assert games[2]["url"] == "https://testdev.itch.io/space-game"
    assert games[2]["publish_date"] == datetime(2024, 3, 10)

    # Check game without date
    assert games[3]["title"] == "Old Game"
    assert games[3]["url"] == "https://testdev.itch.io/old-game"
    assert games[3]["publish_date"] is None


def test_parse_profile_empty():
    """Test parsing an empty profile."""
    html = "<html><body></body></html>"
    games, next_url = parse_profile(html)
    assert len(games) == 0
    assert next_url is None


def test_parse_profile_no_dates():
    """Test parsing profile with games but no dates."""
    html = """
    <html>
    <body>
        <div class="game_cell">
            <a href="https://testdev.itch.io/game1" class="game_link">Game 1</a>
        </div>
        <div class="game_cell">
            <a href="https://testdev.itch.io/game2" class="game_link">Game 2</a>
        </div>
    </body>
    </html>
    """
    games, next_url = parse_profile(html)

    assert len(games) == 2
    assert games[0]["title"] == "Game 1"
    assert games[0]["publish_date"] is None
    assert games[1]["title"] == "Game 2"
    assert games[1]["publish_date"] is None
    assert next_url is None


def test_parse_profile_malformed():
    """Test parsing malformed HTML."""
    html = """
    <html>
    <body>
        <div class="game_cell">
            <!-- Missing game_link class -->
            <a href="https://testdev.itch.io/game1">Game 1</a>
        </div>
        <div class="game_cell">
            <a href="https://testdev.itch.io/game2" class="game_link">Game 2</a>
        </div>
    </body>
    </html>
    """
    games, next_url = parse_profile(html)

    # Should only find the one with correct class
    assert len(games) == 1
    assert games[0]["title"] == "Game 2"
    assert next_url is None


def test_parse_date_text():
    """Test date text parsing."""
    # Standard format with "Published"
    assert _parse_date_text("Published Jan 15, 2024") == datetime(2024, 1, 15)

    # Without "Published"
    assert _parse_date_text("Jan 15, 2024") == datetime(2024, 1, 15)

    # Full month name
    assert _parse_date_text("January 15, 2024") == datetime(2024, 1, 15)

    # Different months
    assert _parse_date_text("Dec 31, 2023") == datetime(2023, 12, 31)
    assert _parse_date_text("March 5, 2024") == datetime(2024, 3, 5)


def test_parse_date_text_invalid():
    """Test parsing invalid date text."""
    # Invalid format
    assert _parse_date_text("Invalid date") is None
    assert _parse_date_text("2024-01-15") is None
    assert _parse_date_text("") is None


def test_parse_profile_extracts_all_grids(sample_profile_html):
    """Test that games from multiple game grids are extracted."""
    games, next_url = parse_profile(sample_profile_html)

    # Should find games from both game_grid_widget divs
    assert len(games) == 4
    titles = [game["title"] for game in games]
    assert "Cool Adventure Game" in titles
    assert "Old Game" in titles
