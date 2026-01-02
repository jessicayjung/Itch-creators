import re
from typing import TypedDict

from bs4 import BeautifulSoup


class GameRating(TypedDict):
    """Represents rating and engagement information extracted from a game page."""
    rating: float | None
    rating_count: int
    comment_count: int


def parse_game(html: str) -> GameRating:
    """
    Extract rating and engagement information from a game page.

    Args:
        html: Raw HTML of the game page

    Returns:
        Dictionary with rating, rating_count, and comment_count
    """
    soup = BeautifulSoup(html, "lxml")

    # Look for the aggregate rating widget
    # Use itemprop instead of itemtype for more robust matching
    aggregate_rating = soup.find("div", class_="aggregate_rating", itemprop="aggregateRating")

    rating = None
    rating_count = 0

    if aggregate_rating:
        # Extract rating value
        rating_value = aggregate_rating.find("span", itemprop="ratingValue")
        rating = float(rating_value.get_text(strip=True)) if rating_value else None

        # Extract rating count
        rating_count_span = aggregate_rating.find("span", itemprop="ratingCount")
        if rating_count_span:
            try:
                rating_count = int(rating_count_span.get_text(strip=True))
            except ValueError:
                rating_count = 0

    # Extract comment count
    # Comments are in a section with class "comments_frame" or similar
    # The count is often in a header like "12 comments" or "Comments (12)"
    comment_count = 0

    # Try finding the comments section header
    comments_header = soup.find("h2", class_="row_title")
    if comments_header:
        header_text = comments_header.get_text(strip=True).lower()
        # Look for patterns like "12 comments", "comments (12)", etc.
        match = re.search(r'(\d+)\s*comments?', header_text)
        if match:
            comment_count = int(match.group(1))
        else:
            # Check for "comments (12)" format
            match = re.search(r'comments?\s*\((\d+)\)', header_text)
            if match:
                comment_count = int(match.group(1))

    # Alternative: look for community widget comment count
    if comment_count == 0:
        community_widget = soup.find("div", class_="community_widget")
        if community_widget:
            community_text = community_widget.get_text()
            match = re.search(r'(\d+)\s*comments?', community_text.lower())
            if match:
                comment_count = int(match.group(1))

    # Alternative: count actual comment divs if they're loaded
    if comment_count == 0:
        comments = soup.find_all("div", class_="community_post")
        if comments:
            comment_count = len(comments)

    return {
        "rating": rating,
        "rating_count": rating_count,
        "comment_count": comment_count,
    }
