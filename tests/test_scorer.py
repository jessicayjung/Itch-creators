from unittest.mock import MagicMock, patch

import pytest

from src.scorer import calculate_love_score, score_all, score_creator


def test_calculate_love_score_high_ratings():
    """Test Love Score with many ratings - should be close to actual rating."""
    # High rating with many votes
    score = calculate_love_score(avg_rating=4.5, total_ratings=100, game_count=5)
    assert score > 4.5  # Should be boosted by engagement and track record


def test_calculate_love_score_low_ratings():
    """Test Love Score with few ratings - should be pulled toward global average."""
    # High rating with few votes - should be pulled toward global average
    score = calculate_love_score(avg_rating=5.0, total_ratings=2, game_count=1)
    assert 3.5 < score < 5.0  # Between global avg (3.5) and actual (5.0)


def test_calculate_love_score_no_ratings():
    """Test Love Score with no ratings - should equal global average."""
    score = calculate_love_score(avg_rating=4.0, total_ratings=0, game_count=1)
    assert score == 3.5  # Should equal global avg with no engagement boost


def test_calculate_love_score_single_game():
    """Test that single game creators get no track record bonus."""
    score_single = calculate_love_score(avg_rating=4.0, total_ratings=50, game_count=1)
    score_multi = calculate_love_score(avg_rating=4.0, total_ratings=50, game_count=5)

    # Multi-game creator should have higher score due to track record bonus
    assert score_multi > score_single


def test_calculate_love_score_engagement_bonus():
    """Test that higher total ratings get engagement bonus."""
    score_few = calculate_love_score(avg_rating=4.0, total_ratings=10, game_count=1)
    score_many = calculate_love_score(avg_rating=4.0, total_ratings=1000, game_count=1)

    # Higher ratings should have higher score due to engagement
    assert score_many > score_few


def test_score_creator():
    """Test scoring a single creator."""
    with patch("src.scorer.db.get_connection") as mock_get_conn:

        # Mock connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock query result: (total_games, total_ratings, weighted_rating_sum)
        # 10 games, 500 total ratings, weighted sum = 4.2 * 500 = 2100
        mock_cursor.fetchone.return_value = (10, 500, 2100.0)

        result = score_creator(creator_id=1)

        assert result.creator_id == 1
        assert result.game_count == 10
        assert result.total_ratings == 500
        # Weighted avg = 2100 / 500 = 4.2
        assert abs(result.avg_rating - 4.2) < 0.1
        assert result.bayesian_score > 0

        # With 500 ratings and 10 games, score should be boosted
        assert result.bayesian_score > 4.5


def test_score_creator_no_games():
    """Test scoring a creator with no games."""
    with patch("src.scorer.db.get_connection") as mock_get_conn:

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # No games
        mock_cursor.fetchone.return_value = (0, 0, 0.0)

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

        # (total_games, total_ratings, weighted_rating_sum)
        # 2 games, 5 total ratings, weighted sum = 5.0 * 5 = 25
        mock_cursor.fetchone.return_value = (2, 5, 25.0)

        result = score_creator(creator_id=1)

        assert result.creator_id == 1
        assert result.game_count == 2
        assert result.total_ratings == 5
        # Weighted avg = 25 / 5 = 5.0
        assert abs(result.avg_rating - 5.0) < 0.1

        # With few ratings, quality component is pulled toward global avg
        assert result.bayesian_score > 0


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
            CreatorScore(1, 10, 100, 4.0, 5.95),
            CreatorScore(2, 5, 50, 4.5, 5.25),
            CreatorScore(3, 15, 200, 3.8, 6.78),
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


def test_love_score_formula_components():
    """Test that Love Score formula correctly combines quality, engagement, and track record."""
    # With 0 ratings, only quality component matters (equals global avg)
    score_zero = calculate_love_score(avg_rating=5.0, total_ratings=0, game_count=1)
    assert score_zero == 3.5  # Global avg

    # Adding ratings increases the score (engagement bonus)
    score_with_ratings = calculate_love_score(avg_rating=5.0, total_ratings=100, game_count=1)
    assert score_with_ratings > score_zero

    # Adding games increases the score (track record bonus)
    score_with_games = calculate_love_score(avg_rating=5.0, total_ratings=100, game_count=10)
    assert score_with_games > score_with_ratings


def test_score_creator_rounds_correctly():
    """Test that scores are rounded to correct precision."""
    with patch("src.scorer.db.get_connection") as mock_get_conn:

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # (total_games, total_ratings, weighted_rating_sum)
        mock_cursor.fetchone.return_value = (5, 25, 103.0864)

        result = score_creator(creator_id=1)

        # avg_rating = 103.0864 / 25 = 4.123456, should be rounded to 2 decimals
        assert result.avg_rating == 4.12

        # bayesian_score should be rounded to 4 decimals
        score_str = str(result.bayesian_score)
        if '.' in score_str:
            assert len(score_str.split('.')[-1]) <= 4
