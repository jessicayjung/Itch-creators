from typing import TypedDict

from bs4 import BeautifulSoup


class GameRating(TypedDict):
    """Represents rating information extracted from a game page."""
    rating: float | None
    rating_count: int


def parse_game(html: str) -> GameRating:
    """
    Extract rating information from a game page.

    Args:
        html: Raw HTML of the game page

    Returns:
        Dictionary with rating and rating_count (None if ratings are hidden)
    """
    soup = BeautifulSoup(html, "lxml")

    # Look for the aggregate rating widget
    # Use itemprop instead of itemtype for more robust matching
    aggregate_rating = soup.find("div", class_="aggregate_rating", itemprop="aggregateRating")

    if not aggregate_rating:
        # No ratings available or hidden
        return {
            "rating": None,
            "rating_count": 0,
        }

    # Extract rating value
    rating_value = aggregate_rating.find("span", itemprop="ratingValue")
    rating = float(rating_value.get_text(strip=True)) if rating_value else None

    # Extract rating count
    rating_count_span = aggregate_rating.find("span", itemprop="ratingCount")
    rating_count = 0
    if rating_count_span:
        try:
            rating_count = int(rating_count_span.get_text(strip=True))
        except ValueError:
            rating_count = 0

    return {
        "rating": rating,
        "rating_count": rating_count,
    }
