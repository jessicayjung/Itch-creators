from datetime import datetime
from typing import TypedDict

import feedparser

from .http_client import fetch
from .logger import setup_logger

logger = setup_logger(__name__)


class FeedEntry(TypedDict):
    """Represents a game from an RSS feed."""
    title: str
    creator: str
    game_url: str
    publish_date: datetime | None


_default_feeds = [
    "https://itch.io/games.xml",
    "https://itch.io/games/newest.xml",
]


def poll_feed(feed_url: str) -> list[FeedEntry]:
    """
    Fetch and parse an itch.io RSS feed.

    Args:
        feed_url: URL of the RSS feed to fetch

    Returns:
        List of dictionaries containing game information
    """
    xml_content = fetch(feed_url)
    feed = feedparser.parse(xml_content)

    entries: list[FeedEntry] = []

    for entry in feed.entries:
        # Defensive: check if required fields exist
        if not hasattr(entry, "link") or not hasattr(entry, "title"):
            logger.warning("Skipping malformed feed entry (missing link or title)")
            continue

        # Extract creator from the link
        # itch.io URLs are typically: https://{creator}.itch.io/{game}
        creator = _extract_creator_from_url(entry.link)

        # Parse publish date if available
        publish_date = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            publish_date = datetime(*entry.published_parsed[:6])

        entries.append({
            "title": entry.title,
            "creator": creator,
            "game_url": entry.link,
            "publish_date": publish_date,
        })

    return entries


def get_new_releases() -> list[FeedEntry]:
    """
    Poll default itch.io feeds for new game releases.

    Returns:
        Combined list of games from all feeds (deduplicated by URL)
    """
    all_entries: list[FeedEntry] = []
    seen_urls: set[str] = set()

    for feed_url in _default_feeds:
        entries = poll_feed(feed_url)

        for entry in entries:
            # Deduplicate by URL
            if entry["game_url"] not in seen_urls:
                all_entries.append(entry)
                seen_urls.add(entry["game_url"])

    return all_entries


def _extract_creator_from_url(url: str) -> str | None:
    """
    Extract creator username from itch.io URL.

    Example:
        https://testdev.itch.io/cool-game -> testdev
        https://itch.io/creator/game -> None (unrecognized format)

    Args:
        url: Full game URL

    Returns:
        Creator username, or None if URL format is unrecognized
    """
    # Remove protocol
    without_protocol = url.split("://", 1)[-1]

    # Get the subdomain (creator name)
    parts = without_protocol.split(".")

    # Standard subdomain format: creator.itch.io
    if len(parts) >= 3 and parts[1] == "itch" and parts[2].startswith("io"):
        # Check if it's not just "itch.io" or "www.itch.io" (no valid subdomain)
        if parts[0] and parts[0] not in ["www", "itch"]:
            return parts[0]

    # Unrecognized URL format - return None instead of collapsing to "unknown"
    return None
