from unittest.mock import MagicMock, patch

import pytest

from src.scorer import calculate_bayesian_score, score_all, score_creator


def test_calculate_bayesian_score():
    """Test Bayesian score calculation."""
    # High rating with many votes - should be close to actual rating
    score = calculate_bayesian_score(avg_rating=4.5, rating_count=100)
    assert score > 4.4  # Should be close to 4.5

    # Low rating with many votes - should be close to actual rating
    score = calculate_bayesian_score(avg_rating=2.0, rating_count=100)
    assert score < 2.2  # Should be close to 2.0

    # High rating with few votes - should be pulled toward global average
    score = calculate_bayesian_score(avg_rating=5.0, rating_count=2)
    assert 3.5 < score < 5.0  # Between global avg (3.5) and actual (5.0)

    # No votes - should equal global average
    score = calculate_bayesian_score(avg_rating=4.0, rating_count=0)
    assert score == 3.5  # Should equal global avg


def test_calculate_bayesian_score_custom_params():
    """Test Bayesian score with custom parameters."""
    # Custom global average
    score = calculate_bayesian_score(
        avg_rating=4.0,
        rating_count=0,
        global_avg=4.5,
        min_votes=10
    )
    assert score == 4.5  # Should equal custom global avg

    # Custom min votes threshold
    score = calculate_bayesian_score(
        avg_rating=5.0,
        rating_count=5,
        global_avg=3.5,
        min_votes=5
    )
    # With min_votes=5 and rating_count=5, weights should be 50/50
    expected = (0.5 * 5.0) + (0.5 * 3.5)
    assert abs(score - expected) < 0.01


def test_score_creator():
    """Test scoring a single creator."""
    with patch("src.scorer.db.get_connection") as mock_get_conn:

        # Mock connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock query result: (total_games, rated_games, total_ratings, weighted_rating_sum, total_comments)
        # 10 games, 8 rated, 500 total ratings, weighted sum = 4.2 * 500 = 2100, 50 comments
        mock_cursor.fetchone.return_value = (10, 8, 500, 2100.0, 50)

        result = score_creator(creator_id=1)

        assert result.creator_id == 1
        assert result.game_count == 10
        assert result.total_ratings == 500
        # Weighted avg = 2100 / 500 = 4.2
        assert abs(result.avg_rating - 4.2) < 0.1
        assert result.bayesian_score > 0

        # With 500 ratings and 10 games (capped 1.10x bonus), score is boosted
        # Base score ~ 4.17, with 10% bonus = ~4.59
        assert result.bayesian_score > 4.5  # Has game count bonus


def test_score_creator_no_games():
    """Test scoring a creator with no rated games."""
    with patch("src.scorer.db.get_connection") as mock_get_conn:

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # No games: (total_games, rated_games, total_ratings, weighted_rating_sum, total_comments)
        mock_cursor.fetchone.return_value = (0, 0, 0, 0.0, 0)

        result = score_creator(creator_id=1)

        assert result.creator_id == 1
        assert result.game_count == 0
        assert result.total_ratings == 0
        assert result.avg_rating == 0.0
        assert result.bayesian_score == 0.0


def test_score_creator_few_ratings():
    """Test scoring a creator with few ratings."""
    with patch("src.scorer.db.get_connection") as mock_get_conn:

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # (total_games, rated_games, total_ratings, weighted_rating_sum, total_comments)
        # 2 games, 2 rated, 5 total ratings, weighted sum = 5.0 * 5 = 25, 0 comments
        mock_cursor.fetchone.return_value = (2, 2, 5, 25.0, 0)

        result = score_creator(creator_id=1)

        assert result.creator_id == 1
        assert result.game_count == 2
        assert result.total_ratings == 5
        # Weighted avg = 25 / 5 = 5.0
        assert abs(result.avg_rating - 5.0) < 0.1

        # With few ratings, score should be between avg and global avg
        assert 3.5 < result.bayesian_score < 5.0


def test_score_all():
    """Test scoring all creators."""
    with patch("src.scorer.db.get_connection") as mock_get_conn, \
         patch("src.scorer.score_creator") as mock_score_creator, \
         patch("src.scorer.db.upsert_creator_score") as mock_upsert:

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock 3 creators
        mock_cursor.fetchall.return_value = [(1,), (2,), (3,)]

        # Mock score_creator to return dummy scores
        from src.models import CreatorScore
        mock_score_creator.side_effect = [
            CreatorScore(1, 10, 100, 4.0, 3.95),
            CreatorScore(2, 5, 50, 4.5, 4.25),
            CreatorScore(3, 15, 200, 3.8, 3.78),
        ]

        result = score_all()

        assert result["creators_scored"] == 3

        # Should have called score_creator 3 times
        assert mock_score_creator.call_count == 3

        # Should have called upsert 3 times
        assert mock_upsert.call_count == 3


def test_score_all_no_creators():
    """Test scoring when there are no creators."""
    with patch("src.scorer.db.get_connection") as mock_get_conn:

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # No creators
        mock_cursor.fetchall.return_value = []

        result = score_all()

        assert result["creators_scored"] == 0


def test_bayesian_formula_correctness():
    """Test that Bayesian formula is correctly implemented."""
    # Manual calculation:
    # avg_rating = 4.0, rating_count = 20, global_avg = 3.5, min_votes = 10
    # weighted = (20 / (20 + 10)) * 4.0 + (10 / (20 + 10)) * 3.5
    # weighted = (20/30) * 4.0 + (10/30) * 3.5
    # weighted = 0.6667 * 4.0 + 0.3333 * 3.5
    # weighted = 2.6667 + 1.1667 = 3.8333

    score = calculate_bayesian_score(
        avg_rating=4.0,
        rating_count=20,
        global_avg=3.5,
        min_votes=10
    )

    expected = 3.8333
    assert abs(score - expected) < 0.01


def test_score_creator_rounds_correctly():
    """Test that scores are rounded to correct precision."""
    with patch("src.scorer.db.get_connection") as mock_get_conn:

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # (total_games, rated_games, total_ratings, weighted_rating_sum, total_comments)
        # 5 games, 5 rated, 25 ratings, weighted sum = 4.123456 * 25 = 103.0864, 0 comments
        mock_cursor.fetchone.return_value = (5, 5, 25, 103.0864, 0)

        result = score_creator(creator_id=1)

        # avg_rating = 103.0864 / 25 = 4.123456, should be rounded to 2 decimals
        assert result.avg_rating == 4.12

        # bayesian_score should be rounded to 4 decimals
        assert len(str(result.bayesian_score).split('.')[-1]) <= 4


def test_game_count_bonus_applied():
    """Test that multi-game creators get a score bonus."""
    with patch("src.scorer.db.get_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Creator with 3 games: should get 1.02^2 = 1.0404 bonus
        # (total_games, rated_games, total_ratings, weighted_rating_sum, total_comments)
        mock_cursor.fetchone.return_value = (3, 3, 100, 400.0, 0)  # avg = 4.0, 0 comments

        result = score_creator(creator_id=1)

        # Base bayesian score with avg=4.0, 100 ratings, min_votes=5
        # = (100/(100+5)) * 4.0 + (5/(100+5)) * 3.5
        # = 0.9524 * 4.0 + 0.0476 * 3.5 = 3.8095 + 0.1667 = 3.9762
        base_score = 3.9762
        expected_with_bonus = base_score * (1.02 ** 2)  # 1.0404 multiplier

        assert result.game_count == 3
        assert result.bayesian_score > base_score
        assert abs(result.bayesian_score - expected_with_bonus) < 0.05


def test_game_count_bonus_capped():
    """Test that game count bonus doesn't exceed 10%."""
    with patch("src.scorer.db.get_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Creator with 20 games: 1.02^19 = 1.456, but should cap at 1.10
        # (total_games, rated_games, total_ratings, weighted_rating_sum, total_comments)
        mock_cursor.fetchone.return_value = (20, 20, 200, 800.0, 0)  # avg = 4.0, 0 comments

        result = score_creator(creator_id=1)

        # Base bayesian score with avg=4.0, 200 ratings, min_votes=5
        # = (200/(200+5)) * 4.0 + (5/(200+5)) * 3.5 = 3.9878
        base_score = 3.9878
        max_with_cap = base_score * 1.10  # Max 10% bonus

        assert result.game_count == 20
        # Score should be capped, not exceed max
        assert result.bayesian_score <= max_with_cap + 0.01
        # Score should be at the cap (1.10x)
        assert abs(result.bayesian_score - max_with_cap) < 0.01


def test_single_game_no_bonus():
    """Test that single game creators get no bonus."""
    with patch("src.scorer.db.get_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Creator with 1 game: no bonus applied
        # (total_games, rated_games, total_ratings, weighted_rating_sum, total_comments)
        mock_cursor.fetchone.return_value = (1, 1, 50, 200.0, 0)  # avg = 4.0, 0 comments

        result = score_creator(creator_id=1)

        # Base bayesian score with avg=4.0, 50 ratings, min_votes=5
        # = (50/(50+5)) * 4.0 + (5/(50+5)) * 3.5
        # = 0.909 * 4.0 + 0.091 * 3.5 = 3.636 + 0.318 = 3.954
        expected_no_bonus = 3.9545

        assert result.game_count == 1
        assert abs(result.bayesian_score - expected_no_bonus) < 0.01
