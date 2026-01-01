from . import db
from .http_client import fetch
from .models import Game
from .parsers import game as game_parser


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

    # Update in database
    db.update_game_ratings(
        game_id=game.id,
        rating=rating_data["rating"],
        rating_count=rating_data["rating_count"]
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
            # Log error but continue processing other games
            print(f"Error enriching {game.title} ({game.url}): {e}")

    return stats
