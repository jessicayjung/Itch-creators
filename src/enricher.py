from . import db
from .http_client import fetch
from .logger import setup_logger, log_error_with_context
from .models import Game
from .parsers import game as game_parser

logger = setup_logger(__name__)


def enrich_game(game: Game) -> bool:
    """
    Fetch a game's page and update its rating information.

    Args:
        game: Game object to enrich

    Returns:
        True if successful, False otherwise

    Raises:
        Exception: If page fetching fails
    """
    # Fetch the game page
    html = fetch(game.url)

    # Parse ratings from page
    rating_data = game_parser.parse_game(html)

    # Detect if ratings are hidden or parse failed
    # Case 1: No rating and no rating count = truly hidden/disabled ratings
    # Case 2: No rating but has rating count = parse failure, should retry
    parse_failed = rating_data["rating"] is None and rating_data["rating_count"] > 0
    ratings_hidden = rating_data["rating"] is None

    # Update in database
    db.update_game_ratings(
        game_id=game.id,
        rating=rating_data["rating"],
        rating_count=rating_data["rating_count"],
        comment_count=rating_data["comment_count"],
        description=rating_data["description"],
        publish_date=rating_data["publish_date"],
        title=rating_data["title"],
        tags=rating_data["tags"],
        ratings_hidden=ratings_hidden
    )

    if parse_failed:
        raise ValueError("Rating parse failed (rating_count present, rating missing)")

    return True


def enrich_all(limit: int | None = None) -> dict[str, int]:
    """
    Process unenriched games.

    Args:
        limit: Maximum number of games to process. None for unlimited.

    Returns:
        Dictionary with stats: {games_processed, errors}
    """
    stats = {
        "games_processed": 0,
        "errors": 0,
    }

    games = db.get_unenriched_games(limit=limit)

    for game in games:
        try:
            enrich_game(game)
            stats["games_processed"] += 1
        except Exception as e:
            stats["errors"] += 1
            log_error_with_context(logger, "Enrich", f"{game.title} ({game.url})", e)
            # Mark failed games with cooldown to prevent infinite retry loops
            db.mark_game_failed(game.id)

    return stats


def re_enrich_stale(days_old: int = 7, limit: int = 500) -> dict[str, int]:
    """
    Re-enrich games that haven't been updated in X days.

    Args:
        days_old: Re-enrich games older than this many days
        limit: Maximum games to process per run

    Returns:
        Dictionary with stats: {games_processed, errors}
    """
    stats = {
        "games_processed": 0,
        "errors": 0,
    }

    games = db.get_stale_games(days_old=days_old, limit=limit)
    logger.info(f"Found {len(games)} stale games to re-enrich")

    for game in games:
        try:
            enrich_game(game)
            stats["games_processed"] += 1
        except Exception as e:
            stats["errors"] += 1
            log_error_with_context(logger, "Re-enrich", f"{game.title} ({game.url})", e)
            # Mark failed games with cooldown to prevent infinite retry loops
            db.mark_game_failed(game.id)

    return stats
