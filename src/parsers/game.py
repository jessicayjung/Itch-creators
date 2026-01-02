import re
from datetime import datetime
from typing import TypedDict

from bs4 import BeautifulSoup


class GameRating(TypedDict):
    """Represents rating and engagement information extracted from a game page."""
    title: str | None
    rating: float | None
    rating_count: int
    comment_count: int
    description: str | None
    publish_date: datetime | None


def parse_game(html: str) -> GameRating:
    """
    Extract rating and engagement information from a game page.

    Args:
        html: Raw HTML of the game page

    Returns:
        Dictionary with title, rating, rating_count, comment_count, description, and publish_date
    """
    soup = BeautifulSoup(html, "lxml")

    # Extract title from the page
    title = None
    # Try the main game title element
    title_elem = soup.find("h1", class_="game_title")
    if title_elem:
        title = title_elem.get_text(strip=True)
    # Fallback to meta og:title
    if not title:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()

    # Look for the aggregate rating widget
    # Use itemprop instead of itemtype for more robust matching
    aggregate_rating = soup.find("div", class_="aggregate_rating", itemprop="aggregateRating")

    rating = None
    rating_count = 0

    if aggregate_rating:
        # Extract rating value - it's in a div with itemprop="ratingValue"
        # The value is in the "content" attribute, not the text
        rating_elem = aggregate_rating.find(itemprop="ratingValue")
        if rating_elem:
            # Try content attribute first (preferred)
            content = rating_elem.get("content")
            if content:
                try:
                    rating = float(content)
                except ValueError:
                    rating = None
            else:
                # Fallback to text content
                try:
                    rating = float(rating_elem.get_text(strip=True))
                except ValueError:
                    rating = None

        # Extract rating count - also uses content attribute
        rating_count_elem = aggregate_rating.find(itemprop="ratingCount")
        if rating_count_elem:
            content = rating_count_elem.get("content")
            if content:
                try:
                    rating_count = int(content)
                except ValueError:
                    rating_count = 0
            else:
                # Fallback to parsing text (e.g., "(49)")
                try:
                    text = rating_count_elem.get_text(strip=True)
                    # Remove parentheses and other non-numeric chars
                    rating_count = int(''.join(c for c in text if c.isdigit()))
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

    # Extract game description
    # The description is typically in a div with class "formatted_description" or similar
    description = None

    # Try to find the game description/summary
    # Look for meta description first (short summary)
    meta_description = soup.find("meta", attrs={"name": "description"})
    if meta_description and meta_description.get("content"):
        description = meta_description.get("content").strip()

    # If no meta description, try to find the formatted description on the page
    if not description:
        desc_div = soup.find("div", class_="formatted_description")
        if desc_div:
            # Get just the text, limit to first paragraph or first ~200 chars for summary
            desc_text = desc_div.get_text(separator=" ", strip=True)
            if desc_text:
                # Limit to first 500 characters as a summary
                description = desc_text[:500].strip()
                if len(desc_text) > 500:
                    description += "..."

    # Extract publish date
    # Look for the publish date in the game info table or meta tags
    publish_date = None

    # Try finding date in the info panel (e.g., "Published Dec 25, 2024")
    info_panel = soup.find("div", class_="info_panel_wrapper")
    if info_panel:
        # Look for "Published" or "Released" text
        for td in info_panel.find_all("td"):
            text = td.get_text(strip=True).lower()
            if "published" in text or "released" in text:
                # Get the next sibling or value cell
                value_td = td.find_next_sibling("td")
                if value_td:
                    date_str = value_td.get_text(strip=True)
                    # Try parsing common date formats
                    for fmt in ["%b %d, %Y", "%B %d, %Y", "%Y-%m-%d", "%d %b %Y"]:
                        try:
                            publish_date = datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            continue

    # Alternative: look for abbr with title attribute containing ISO date
    if not publish_date:
        date_abbr = soup.find("abbr", class_="date_format")
        if date_abbr and date_abbr.get("title"):
            try:
                # ISO format: 2024-12-25T12:00:00Z
                date_str = date_abbr["title"]
                publish_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

    return {
        "title": title,
        "rating": rating,
        "rating_count": rating_count,
        "comment_count": comment_count,
        "description": description,
        "publish_date": publish_date,
    }
