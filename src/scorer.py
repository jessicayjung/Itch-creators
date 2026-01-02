import math

from . import db
from .models import CreatorScore


# Love Score constants
# Higher threshold means more ratings needed for confidence in quality
_BAYESIAN_MIN_VOTES = 20
_GLOBAL_AVG = 3.5

# Engagement multiplier: how much to reward total ratings
# log(ratings)/log(1000) * 0.5 means ~1000 ratings = 1.5x, ~5000 ratings = 1.8x
_ENGAGEMENT_LOG_BASE = 1000
_ENGAGEMENT_WEIGHT = 0.5

# Track record multiplier: how much to reward shipping multiple games
# sqrt(games)/15 * 0.4 means 10 games ≈ 1.08x, 30 games ≈ 1.15x, 80 games ≈ 1.24x
_TRACK_RECORD_DIVISOR = 15
_TRACK_RECORD_WEIGHT = 0.4


def calculate_love_score(
    avg_rating: float,
    total_ratings: int,
    game_count: int
) -> float:
    """
    Calculate Love Score for a creator.

    Love Score = Quality × Engagement × Track Record

    Components:
    1. Quality: Bayesian average protects against small sample sizes
    2. Engagement: Log-scaled bonus for total ratings (how many people love the work)
    3. Track Record: Sqrt-scaled bonus for game count (consistency of shipping)

    This formula rewards creators who:
    - Have high-quality games (high ratings)
    - Have broad reach (many total ratings)
    - Ship consistently (multiple games)

    Args:
        avg_rating: Weighted average rating across all games
        total_ratings: Total number of ratings across all games
        game_count: Total number of games published

    Returns:
        Love Score (typically ranges from 4.0 to 10.0)
    """
    # 1. Quality component: Bayesian average (range: ~3.5 to ~5.0)
    # Higher min_votes means more ratings needed before we trust the average
    quality = (
        (total_ratings / (total_ratings + _BAYESIAN_MIN_VOTES)) * avg_rating +
        (_BAYESIAN_MIN_VOTES / (total_ratings + _BAYESIAN_MIN_VOTES)) * _GLOBAL_AVG
    )

    # 2. Engagement multiplier (range: 1.0 to ~2.0)
    # Rewards creators whose work has reached many people
    engagement = 1 + (
        math.log(total_ratings + 1) / math.log(_ENGAGEMENT_LOG_BASE)
    ) * _ENGAGEMENT_WEIGHT

    # 3. Track record multiplier (range: 1.0 to ~1.4)
    # Rewards creators who have shipped multiple games
    # Single-game creators get no track record bonus
    if game_count > 1:
        track_record = 1 + (
            math.sqrt(game_count) / _TRACK_RECORD_DIVISOR
        ) * _TRACK_RECORD_WEIGHT
    else:
        track_record = 1.0

    return round(quality * engagement * track_record, 4)


def score_creator(creator_id: int) -> CreatorScore:
    """
    Calculate Love Score for a single creator.

    Args:
        creator_id: ID of the creator to score

    Returns:
        CreatorScore object with calculated metrics
    """
    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Get aggregate stats for this creator's games
        # Use weighted sum to properly account for rating_count per game
        cursor.execute("""
            SELECT
                COUNT(*) as total_games,
                SUM(CASE WHEN rating IS NOT NULL THEN rating_count ELSE 0 END) as total_ratings,
                SUM(CASE WHEN rating IS NOT NULL THEN rating * rating_count ELSE 0 END) as weighted_rating_sum
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
        total_ratings = row[1] or 0
        weighted_rating_sum = float(row[2]) if row[2] else 0.0

        # Compute weighted average: sum of (rating * count) / total count
        if total_ratings > 0:
            avg_rating = weighted_rating_sum / total_ratings
        else:
            avg_rating = _GLOBAL_AVG

        # Calculate Love Score
        love_score = calculate_love_score(avg_rating, total_ratings, total_games)

        return CreatorScore(
            creator_id=creator_id,
            game_count=total_games,
            total_ratings=total_ratings,
            avg_rating=round(avg_rating, 2),
            bayesian_score=love_score  # Using bayesian_score field for Love Score
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
