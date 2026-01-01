from datetime import datetime

from . import db
from .http_client import fetch
from .models import Creator, Game
from .parsers import profile


def backfill_creator(creator: Creator) -> int:
    """
    Fetch a creator's profile and backfill their game history.

    Args:
        creator: Creator object to backfill

    Returns:
        Number of games inserted

    Raises:
        Exception: If profile fetching fails
    """
    # Fetch the creator's profile page
    html = fetch(creator.profile_url)

    # Parse games from profile
    games = profile.parse_profile(html)

    # Insert games into database
    inserted_count = 0
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
            # Log error but continue processing other creators
            print(f"Error backfilling {creator.name}: {e}")

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

    return "unknown"
