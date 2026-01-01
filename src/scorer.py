from . import db
from .models import CreatorScore


# Default values for Bayesian averaging
_DEFAULT_MIN_VOTES = 10
_DEFAULT_GLOBAL_AVG = 3.5
_UNRATED_GAME_WEIGHT = 0.2


def calculate_bayesian_score(
    avg_rating: float,
    rating_count: int,
    global_avg: float = _DEFAULT_GLOBAL_AVG,
    min_votes: int = _DEFAULT_MIN_VOTES
) -> float:
    """
    Calculate Bayesian average rating.

    This weighs the creator's actual rating against a global average,
    giving more weight to the actual rating as the number of votes increases.

    Args:
        avg_rating: Creator's average rating
        rating_count: Total number of ratings across all games
        global_avg: Global average rating (default: 3.5)
        min_votes: Minimum votes threshold for confidence (default: 10)

    Returns:
        Weighted Bayesian score
    """
    weighted_score = (
        (rating_count / (rating_count + min_votes)) * avg_rating +
        (min_votes / (rating_count + min_votes)) * global_avg
    )
    return round(weighted_score, 4)


def score_creator(creator_id: int) -> CreatorScore:
    """
    Calculate score for a single creator.

    Args:
        creator_id: ID of the creator to score

    Returns:
        CreatorScore object with calculated metrics
    """
    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Get aggregate stats for this creator's games
        cursor.execute("""
            SELECT
                COUNT(*) as total_games,
                SUM(CASE WHEN rating IS NOT NULL THEN 1 ELSE 0 END) as rated_games,
                SUM(CASE WHEN rating IS NOT NULL THEN rating_count ELSE 0 END) as total_ratings,
                AVG(CASE WHEN rating IS NOT NULL THEN rating END) as avg_rating
            FROM games
            WHERE creator_id = %s
        """, (creator_id,))

        row = cursor.fetchone()
        cursor.close()

        if not row or row[0] == 0:
            # No games
            return CreatorScore(
                creator_id=creator_id,
                game_count=0,
                total_ratings=0,
                avg_rating=0.0,
                bayesian_score=0.0
            )

        total_games = row[0] or 0
        rated_games = row[1] or 0
        total_ratings = row[2] or 0
        avg_rating = float(row[3]) if row[3] else 0.0
        unrated_games = max(total_games - rated_games, 0)

        if rated_games == 0:
            adjusted_avg = _DEFAULT_GLOBAL_AVG
        else:
            weighted_unrated = unrated_games * _UNRATED_GAME_WEIGHT
            adjusted_avg = (
                (avg_rating * rated_games) + (_DEFAULT_GLOBAL_AVG * weighted_unrated)
            ) / (rated_games + weighted_unrated)

        # Calculate Bayesian score using adjusted average and real ratings volume
        bayesian_score = calculate_bayesian_score(adjusted_avg, total_ratings)

        return CreatorScore(
            creator_id=creator_id,
            game_count=total_games,
            total_ratings=total_ratings,
            avg_rating=round(adjusted_avg, 2),
            bayesian_score=bayesian_score
        )


def score_all() -> dict[str, int]:
    """
    Recalculate scores for all creators.

    Returns:
        Dictionary with stats: {creators_scored}
    """
    stats = {
        "creators_scored": 0,
    }

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Get all creator IDs
        cursor.execute("SELECT id FROM creators")
        creator_ids = [row[0] for row in cursor.fetchall()]
        cursor.close()

    # Score each creator
    for creator_id in creator_ids:
        score = score_creator(creator_id)
        db.upsert_creator_score(score)
        stats["creators_scored"] += 1

    return stats
