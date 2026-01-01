from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from src.feed_poller import _extract_creator_from_url, get_new_releases, poll_feed


@pytest.fixture
def sample_feed_xml():
    """Load sample RSS feed fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "feed_sample.xml"
    return fixture_path.read_text()


def test_poll_feed(sample_feed_xml):
    """Test parsing an RSS feed."""
    with patch("src.feed_poller.fetch") as mock_fetch:
        mock_fetch.return_value = sample_feed_xml

        result = poll_feed("https://itch.io/games.xml")

        assert len(result) == 3

        # Check first entry
        assert result[0]["title"] == "Cool Adventure Game"
        assert result[0]["creator"] == "testdev"
        assert result[0]["game_url"] == "https://testdev.itch.io/cool-adventure"
        assert result[0]["publish_date"] is not None
        assert isinstance(result[0]["publish_date"], datetime)

        # Check second entry
        assert result[1]["title"] == "Puzzle Master"
        assert result[1]["creator"] == "puzzleguru"

        # Check third entry
        assert result[2]["title"] == "Space Shooter"
        assert result[2]["creator"] == "gamerdev"


def test_poll_feed_empty():
    """Test polling an empty feed."""
    empty_feed = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>itch.io - newest games</title>
    <link>https://itch.io/games</link>
  </channel>
</rss>"""

    with patch("src.feed_poller.fetch") as mock_fetch:
        mock_fetch.return_value = empty_feed

        result = poll_feed("https://itch.io/games.xml")

        assert len(result) == 0


def test_get_new_releases(sample_feed_xml):
    """Test getting new releases from multiple feeds."""
    with patch("src.feed_poller.fetch") as mock_fetch:
        # Return same feed for both URLs
        mock_fetch.return_value = sample_feed_xml

        result = get_new_releases()

        # Should have 3 entries (deduplicated)
        assert len(result) == 3

        # Check that fetch was called twice (for both default feeds)
        assert mock_fetch.call_count == 2


def test_get_new_releases_deduplication(sample_feed_xml):
    """Test that duplicate entries are removed."""
    with patch("src.feed_poller.fetch") as mock_fetch:
        # Return same feed for both URLs to test deduplication
        mock_fetch.return_value = sample_feed_xml

        result = get_new_releases()

        # Should deduplicate entries with same URL
        urls = [entry["game_url"] for entry in result]
        assert len(urls) == len(set(urls))  # No duplicates


def test_extract_creator_from_url():
    """Test extracting creator name from various URL formats."""
    # Standard format
    assert _extract_creator_from_url("https://testdev.itch.io/cool-game") == "testdev"
    assert _extract_creator_from_url("https://puzzleguru.itch.io/puzzle-master") == "puzzleguru"

    # Without protocol
    assert _extract_creator_from_url("testdev.itch.io/cool-game") == "testdev"

    # Valid creator subdomain
    assert _extract_creator_from_url("https://creator123.itch.io/game") == "creator123"

    # Non-subdomain URLs should return None (not "unknown")
    assert _extract_creator_from_url("https://itch.io/creator/game") is None
    assert _extract_creator_from_url("https://www.itch.io/game") is None
    assert _extract_creator_from_url("https://itch.io/games") is None


def test_poll_feed_no_publish_date():
    """Test parsing feed entries without publish dates."""
    feed_no_dates = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>itch.io - games</title>
    <link>https://itch.io/games</link>
    <item>
      <title>No Date Game</title>
      <link>https://testdev.itch.io/no-date-game</link>
      <description>A game without a publish date</description>
    </item>
  </channel>
</rss>"""

    with patch("src.feed_poller.fetch") as mock_fetch:
        mock_fetch.return_value = feed_no_dates

        result = poll_feed("https://itch.io/games.xml")

        assert len(result) == 1
        assert result[0]["title"] == "No Date Game"
        assert result[0]["publish_date"] is None


def test_poll_feed_calls_http_client():
    """Test that poll_feed uses the HTTP client."""
    with patch("src.feed_poller.fetch") as mock_fetch:
        mock_fetch.return_value = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel></channel></rss>"""

        poll_feed("https://test.com/feed.xml")

        mock_fetch.assert_called_once_with("https://test.com/feed.xml")


def test_poll_feed_handles_malformed_entries():
    """Test that poll_feed skips malformed entries gracefully."""
    # Create a feed with one good entry and one malformed (missing link)
    feed_with_malformed = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>itch.io - games</title>
    <link>https://itch.io/games</link>
    <item>
      <title>Good Game</title>
      <link>https://testdev.itch.io/good-game</link>
      <description>A properly formatted entry</description>
    </item>
    <item>
      <description>Malformed entry - no title or link</description>
    </item>
  </channel>
</rss>"""

    with patch("src.feed_poller.fetch") as mock_fetch:
        mock_fetch.return_value = feed_with_malformed

        result = poll_feed("https://itch.io/games.xml")

        # Should only return the valid entry, skipping malformed one
        assert len(result) == 1
        assert result[0]["title"] == "Good Game"
        assert result[0]["game_url"] == "https://testdev.itch.io/good-game"
