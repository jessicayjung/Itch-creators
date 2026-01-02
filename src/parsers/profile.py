from datetime import datetime
from typing import TypedDict

from bs4 import BeautifulSoup


class ProfileGame(TypedDict):
    """Represents a game found on a creator's profile."""
    title: str
    url: str
    publish_date: datetime | None


def parse_profile(html: str) -> tuple[list[ProfileGame], str | None]:
    """
    Extract list of games from a creator's profile page.

    Args:
        html: Raw HTML of the profile page

    Returns:
        Tuple of (games list, next page URL or None)
    """
    soup = BeautifulSoup(html, "lxml")
    games: list[ProfileGame] = []

    # Find all game cells
    game_cells = soup.find_all("div", class_="game_cell")

    for cell in game_cells:
        # Extract title and URL - specifically look for the title link, not the thumbnail link
        # The title link has class "title game_link", thumbnail has "thumb_link game_link"
        title_link = cell.find("a", class_="title")
        if not title_link:
            # Fallback: try finding any game_link with text content
            for link in cell.find_all("a", class_="game_link"):
                if link.get_text(strip=True):
                    title_link = link
                    break
        if not title_link:
            continue

        title = title_link.get_text(strip=True)
        url = title_link.get("href", "")

        # Extract publish date if available
        publish_date = None
        published_at = cell.find("div", class_="published_at")
        if published_at:
            date_text = published_at.get_text(strip=True)
            publish_date = _parse_date_text(date_text)

        games.append({
            "title": title,
            "url": url,
            "publish_date": publish_date,
        })

    # Check for pagination - look for "next" link
    next_url = None
    next_link = soup.find("a", class_="next_page")
    if next_link:
        next_url = next_link.get("href")

    return games, next_url


def _parse_date_text(text: str) -> datetime | None:
    """
    Parse date from itch.io format.

    Example formats:
        "Published Jan 15, 2024"
        "Jan 15, 2024"

    Args:
        text: Date text to parse

    Returns:
        Datetime object or None if parsing fails
    """
    # Remove "Published" prefix
    text = text.replace("Published", "").strip()

    try:
        # Try parsing "Jan 15, 2024" format
        return datetime.strptime(text, "%b %d, %Y")
    except ValueError:
        pass

    try:
        # Try alternative format "January 15, 2024"
        return datetime.strptime(text, "%B %d, %Y")
    except ValueError:
        pass

    return None
