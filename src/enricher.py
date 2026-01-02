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

    # Detect if ratings are hidden (no rating and no rating count)
    ratings_hidden = rating_data["rating"] is None and rating_data["rating_count"] == 0

    # Update in database
    db.update_game_ratings(
        game_id=game.id,
        rating=rating_data["rating"],
        rating_count=rating_data["rating_count"],
        ratings_hidden=ratings_hidden
    )

    return True


def enrich_all() -> dict[str, int]:
    """
    Process all unenriched games.

    Returns:
        Dictionary with stats: {games_processed, errors}
    """
    stats = {
        "games_processed": 0,
        "errors": 0,
    }

    games = db.get_unenriched_games()

    for game in games:
        try:
            enrich_game(game)
            stats["games_processed"] += 1
        except Exception as e:
            stats["errors"] += 1
            log_error_with_context(logger, "Enrich", f"{game.title} ({game.url})", e)

    return stats
