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
    with patch("src.scorer.db.get_connection") as mock_get_conn, \
         patch("src.scorer.db") as mock_db:

        # Mock connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock query result: 10 games, 500 total ratings, 4.2 avg rating
        mock_cursor.fetchone.return_value = (10, 500, 4.2)

        result = score_creator(creator_id=1)

        assert result.creator_id == 1
        assert result.game_count == 10
        assert result.total_ratings == 500
        assert result.avg_rating == 4.2
        assert result.bayesian_score > 0

        # With 500 ratings, Bayesian score should be very close to avg_rating
        assert abs(result.bayesian_score - 4.2) < 0.1


def test_score_creator_no_games():
    """Test scoring a creator with no rated games."""
    with patch("src.scorer.db.get_connection") as mock_get_conn:

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # No games
        mock_cursor.fetchone.return_value = (0, None, None)

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

        # 2 games, 5 total ratings, 5.0 avg rating
        mock_cursor.fetchone.return_value = (2, 5, 5.0)

        result = score_creator(creator_id=1)

        assert result.creator_id == 1
        assert result.game_count == 2
        assert result.total_ratings == 5
        assert result.avg_rating == 5.0

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

        # avg_rating with many decimals
        mock_cursor.fetchone.return_value = (5, 25, 4.123456)

        result = score_creator(creator_id=1)

        # avg_rating should be rounded to 2 decimals
        assert result.avg_rating == 4.12

        # bayesian_score should be rounded to 4 decimals
        assert len(str(result.bayesian_score).split('.')[-1]) <= 4
