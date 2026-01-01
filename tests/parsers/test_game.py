from pathlib import Path

import pytest

from src.parsers.game import parse_game


@pytest.fixture
def sample_game_html():
    """Load sample game HTML with ratings."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "game_sample.html"
    return fixture_path.read_text()


@pytest.fixture
def sample_game_no_ratings_html():
    """Load sample game HTML without ratings."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "game_no_ratings.html"
    return fixture_path.read_text()


def test_parse_game_with_ratings(sample_game_html):
    """Test parsing a game page with ratings."""
    result = parse_game(sample_game_html)

    assert result["rating"] == 4.5
    assert result["rating_count"] == 150


def test_parse_game_no_ratings(sample_game_no_ratings_html):
    """Test parsing a game page without ratings."""
    result = parse_game(sample_game_no_ratings_html)

    assert result["rating"] is None
    assert result["rating_count"] == 0


def test_parse_game_empty_html():
    """Test parsing empty HTML."""
    html = "<html><body></body></html>"
    result = parse_game(html)

    assert result["rating"] is None
    assert result["rating_count"] == 0


def test_parse_game_different_rating():
    """Test parsing games with different rating values."""
    html_high_rating = """
    <html>
    <body>
        <div class="aggregate_rating" itemprop="aggregateRating" itemscope itemtype="http://schema.org/AggregateRating">
            <span itemprop="ratingValue">5.0</span>
            <span itemprop="ratingCount">1000</span> ratings
        </div>
    </body>
    </html>
    """

    result = parse_game(html_high_rating)
    assert result["rating"] == 5.0
    assert result["rating_count"] == 1000


def test_parse_game_low_rating_count():
    """Test parsing game with few ratings."""
    html_few_ratings = """
    <html>
    <body>
        <div class="aggregate_rating" itemprop="aggregateRating" itemscope itemtype="http://schema.org/AggregateRating">
            <span itemprop="ratingValue">3.2</span>
            <span itemprop="ratingCount">5</span> ratings
        </div>
    </body>
    </html>
    """

    result = parse_game(html_few_ratings)
    assert result["rating"] == 3.2
    assert result["rating_count"] == 5


def test_parse_game_single_rating():
    """Test parsing game with a single rating."""
    html_single = """
    <html>
    <body>
        <div class="aggregate_rating" itemprop="aggregateRating" itemscope itemtype="http://schema.org/AggregateRating">
            <span itemprop="ratingValue">4.0</span>
            <span itemprop="ratingCount">1</span> rating
        </div>
    </body>
    </html>
    """

    result = parse_game(html_single)
    assert result["rating"] == 4.0
    assert result["rating_count"] == 1


def test_parse_game_malformed_rating_count():
    """Test parsing game with malformed rating count."""
    html_malformed = """
    <html>
    <body>
        <div class="aggregate_rating" itemprop="aggregateRating" itemscope itemtype="http://schema.org/AggregateRating">
            <span itemprop="ratingValue">4.5</span>
            <span itemprop="ratingCount">invalid</span> ratings
        </div>
    </body>
    </html>
    """

    result = parse_game(html_malformed)
    assert result["rating"] == 4.5
    assert result["rating_count"] == 0  # Should default to 0 on parse error


def test_parse_game_missing_rating_value():
    """Test parsing game with missing rating value."""
    html_missing_value = """
    <html>
    <body>
        <div class="aggregate_rating" itemprop="aggregateRating" itemscope itemtype="http://schema.org/AggregateRating">
            <span itemprop="ratingCount">100</span> ratings
        </div>
    </body>
    </html>
    """

    result = parse_game(html_missing_value)
    assert result["rating"] is None
    assert result["rating_count"] == 100


def test_parse_game_missing_rating_count():
    """Test parsing game with missing rating count."""
    html_missing_count = """
    <html>
    <body>
        <div class="aggregate_rating" itemprop="aggregateRating" itemscope itemtype="http://schema.org/AggregateRating">
            <span itemprop="ratingValue">4.5</span>
        </div>
    </body>
    </html>
    """

    result = parse_game(html_missing_count)
    assert result["rating"] == 4.5
    assert result["rating_count"] == 0


def test_parse_game_without_itemtype():
    """Test parsing game with itemprop but without itemtype attribute."""
    html_no_itemtype = """
    <html>
    <body>
        <div class="aggregate_rating" itemprop="aggregateRating">
            <span itemprop="ratingValue">3.8</span>
            <span itemprop="ratingCount">42</span> ratings
        </div>
    </body>
    </html>
    """

    result = parse_game(html_no_itemtype)
    assert result["rating"] == 3.8
    assert result["rating_count"] == 42
