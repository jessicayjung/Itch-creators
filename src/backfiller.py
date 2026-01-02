import hashlib
from datetime import datetime

from . import db
from .http_client import fetch
from .logger import setup_logger, log_error_with_context
from .models import Creator, Game
from .parsers import profile

logger = setup_logger(__name__)


# Maximum pages to fetch per creator to prevent infinite loops
_MAX_PAGES_PER_CREATOR = 50


def backfill_creator(creator: Creator) -> int:
    """
    Fetch a creator's profile and backfill their game history.

    Handles paginated profiles by following "next page" links.

    Args:
        creator: Creator object to backfill

    Returns:
        Number of games inserted

    Raises:
        Exception: If profile fetching fails
    """
    inserted_count = 0
    current_url = creator.profile_url

    for _ in range(_MAX_PAGES_PER_CREATOR):
        # Fetch the current profile page
        html = fetch(current_url)

        # Parse games and get next page URL
        games, next_url = profile.parse_profile(html)

        # Insert games into database
        for game_data in games:
            # Extract itch_id from URL
            # Example: https://testdev.itch.io/cool-game -> cool-game
            itch_id = _extract_game_id(game_data["url"])

            game = Game(
                id=None,
                itch_id=itch_id,
                title=game_data["title"],
                creator_name=creator.name,
                url=game_data["url"],
                publish_date=game_data["publish_date"].date() if game_data["publish_date"] else None,
                rating=None,
                rating_count=0,
                scraped_at=None
            )

            game_id = db.insert_game(game)
            if game_id:
                inserted_count += 1

        # Stop if no more pages
        if not next_url:
            break

        current_url = next_url

    # Mark creator as backfilled
    db.mark_creator_backfilled(creator.id)

    return inserted_count


def backfill_all() -> dict[str, int]:
    """
    Process all unbackfilled creators.

    Returns:
        Dictionary with stats: {creators_processed, games_inserted, errors}
    """
    stats = {
        "creators_processed": 0,
        "games_inserted": 0,
        "errors": 0,
    }

    creators = db.get_unbackfilled_creators()

    for creator in creators:
        try:
            games_count = backfill_creator(creator)
            stats["creators_processed"] += 1
            stats["games_inserted"] += games_count
        except Exception as e:
            stats["errors"] += 1
            log_error_with_context(logger, "Backfill", creator.name, e)

    return stats


def _extract_game_id(url: str) -> str:
    """
    Extract game slug from itch.io URL.

    Example:
        https://testdev.itch.io/cool-game -> cool-game
        https://testdev.itch.io/cool-game?secret=xyz -> cool-game
        https://testdev.itch.io/cool-game/ -> cool-game

    Args:
        url: Full game URL

    Returns:
        Game slug/ID
    """
    # Remove query parameters
    url = url.split("?")[0]

    # Remove trailing slash
    url = url.rstrip("/")

    # Get the path part
    parts = url.split("/")

    # Last part is the game slug
    if len(parts) > 0 and parts[-1]:
        return parts[-1]

    # Generate stable hash for unparseable URLs to avoid uniqueness collisions
    return f"unknown-{hashlib.sha256(url.encode()).hexdigest()[:12]}"
