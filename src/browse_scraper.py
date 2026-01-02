"""Scrape itch.io browse pages for game discovery."""

import re
from typing import TypedDict
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .http_client import fetch
from .logger import setup_logger

logger = setup_logger(__name__)


class BrowseGame(TypedDict):
    """Represents a game found on a browse page."""
    title: str
    url: str
    creator: str


# Browse page configurations - expanded for maximum discovery
BROWSE_PAGES = {
    # Main discovery pages (high-value)
    "top-rated": "https://itch.io/games/top-rated",
    "popular": "https://itch.io/games",
    "new-popular": "https://itch.io/games/new-and-popular",
    "top-sellers": "https://itch.io/games/top-sellers",
    "newest": "https://itch.io/games/newest",
    "featured": "https://itch.io/games/featured",

    # All genres
    "action": "https://itch.io/games/genre-action",
    "adventure": "https://itch.io/games/genre-adventure",
    "card-game": "https://itch.io/games/genre-card-game",
    "educational": "https://itch.io/games/genre-educational",
    "fighting": "https://itch.io/games/genre-fighting",
    "interactive-fiction": "https://itch.io/games/genre-interactive-fiction",
    "platformer": "https://itch.io/games/genre-platformer",
    "puzzle": "https://itch.io/games/genre-puzzle",
    "racing": "https://itch.io/games/genre-racing",
    "rhythm": "https://itch.io/games/genre-rhythm",
    "roguelike": "https://itch.io/games/genre-roguelike",
    "rpg": "https://itch.io/games/genre-rpg",
    "shooter": "https://itch.io/games/genre-shooter",
    "simulation": "https://itch.io/games/genre-simulation",
    "sports": "https://itch.io/games/genre-sports",
    "strategy": "https://itch.io/games/genre-strategy",
    "survival": "https://itch.io/games/genre-survival",
    "visual-novel": "https://itch.io/games/genre-visual-novel",

    # Popular tags for niche discovery
    "horror": "https://itch.io/games/tag-horror",
    "pixel-art": "https://itch.io/games/tag-pixel-art",
    "retro": "https://itch.io/games/tag-retro",
    "indie": "https://itch.io/games/tag-indie",
    "atmospheric": "https://itch.io/games/tag-atmospheric",
    "story-rich": "https://itch.io/games/tag-story-rich",
    "metroidvania": "https://itch.io/games/tag-metroidvania",
    "singleplayer": "https://itch.io/games/tag-singleplayer",
    "multiplayer": "https://itch.io/games/tag-multiplayer",
    "co-op": "https://itch.io/games/tag-co-op",
    "local-multiplayer": "https://itch.io/games/tag-local-multiplayer",
    "open-world": "https://itch.io/games/tag-open-world",
    "short": "https://itch.io/games/tag-short",
    "difficult": "https://itch.io/games/tag-difficult",
    "relaxing": "https://itch.io/games/tag-relaxing",
    "cute": "https://itch.io/games/tag-cute",
    "dark": "https://itch.io/games/tag-dark",
    "funny": "https://itch.io/games/tag-funny",
    "2d": "https://itch.io/games/tag-2d",
    "3d": "https://itch.io/games/tag-3d",
    "top-down": "https://itch.io/games/tag-top-down",
    "side-scroller": "https://itch.io/games/tag-side-scroller",
    "first-person": "https://itch.io/games/tag-first-person",
    "isometric": "https://itch.io/games/tag-isometric",

    # Platforms
    "web-games": "https://itch.io/games/platform-web",
    "windows": "https://itch.io/games/platform-windows",
    "macos": "https://itch.io/games/platform-osx",
    "linux": "https://itch.io/games/platform-linux",
    "android": "https://itch.io/games/platform-android",

    # Game jams (prolific indie devs)
    "jam-games": "https://itch.io/games/in-jam",

    # Physical games (different creator pool)
    "physical": "https://itch.io/physical-games",
}


def scrape_browse_page(url: str, max_pages: int = 3) -> list[BrowseGame]:
    """
    Scrape games from an itch.io browse page.

    Args:
        url: Base URL of the browse page
        max_pages: Maximum number of pages to scrape (default 3)

    Returns:
        List of games found
    """
    games: list[BrowseGame] = []
    seen_urls: set[str] = set()

    current_url = url
    pages_scraped = 0

    while current_url and pages_scraped < max_pages:
        try:
            html = fetch(current_url)
            soup = BeautifulSoup(html, "lxml")

            # Find all game links
            # Game URLs follow pattern: https://{creator}.itch.io/{game}
            game_links = soup.find_all("a", class_="game_link")

            for link in game_links:
                href = link.get("href", "")
                if not href or href in seen_urls:
                    continue

                # Validate it's a game URL (creator.itch.io/game format)
                creator = _extract_creator_from_url(href)
                if not creator:
                    continue

                # Get title from link text or parent
                title = link.get_text(strip=True)
                if not title:
                    # Try to find title in parent game_cell
                    title_elem = link.find_parent("div", class_="game_cell")
                    if title_elem:
                        title_link = title_elem.find("a", class_="title")
                        if title_link:
                            title = title_link.get_text(strip=True)

                if not title:
                    title = href.split("/")[-1]  # Fallback to URL slug

                seen_urls.add(href)
                games.append({
                    "title": title,
                    "url": href,
                    "creator": creator,
                })

            # Find next page link
            next_link = soup.find("a", class_="next_page")
            if next_link and next_link.get("href"):
                current_url = urljoin(url, next_link["href"])
            else:
                current_url = None

            pages_scraped += 1
            logger.debug(f"Scraped page {pages_scraped} of {url}: found {len(games)} games so far")

        except Exception as e:
            logger.warning(f"Error scraping {current_url}: {e}")
            break

    return games


def scrape_all_browse_pages(max_pages_per_source: int = 2) -> list[BrowseGame]:
    """
    Scrape games from all configured browse pages.

    Args:
        max_pages_per_source: Maximum pages to scrape per browse page

    Returns:
        Combined deduplicated list of games
    """
    all_games: list[BrowseGame] = []
    seen_urls: set[str] = set()

    for name, url in BROWSE_PAGES.items():
        logger.info(f"Scraping {name}...")
        try:
            games = scrape_browse_page(url, max_pages=max_pages_per_source)

            new_count = 0
            for game in games:
                if game["url"] not in seen_urls:
                    seen_urls.add(game["url"])
                    all_games.append(game)
                    new_count += 1

            logger.info(f"  Found {len(games)} games, {new_count} new")

        except Exception as e:
            logger.warning(f"Error scraping {name}: {e}")
            continue

    logger.info(f"Total unique games discovered: {len(all_games)}")
    return all_games


def _extract_creator_from_url(url: str) -> str | None:
    """
    Extract creator username from itch.io URL.

    Example:
        https://testdev.itch.io/cool-game -> testdev

    Args:
        url: Full game URL

    Returns:
        Creator username, or None if URL format is unrecognized
    """
    # Remove protocol
    without_protocol = url.split("://", 1)[-1]

    # Get the subdomain (creator name)
    parts = without_protocol.split(".")

    # Standard subdomain format: creator.itch.io
    if len(parts) >= 3 and parts[1] == "itch" and parts[2].startswith("io"):
        if parts[0] and parts[0] not in ["www", "itch", "static"]:
            return parts[0]

    return None


if __name__ == "__main__":
    # Test scraping
    import sys

    if len(sys.argv) > 1:
        # Scrape specific page
        page_name = sys.argv[1]
        if page_name in BROWSE_PAGES:
            games = scrape_browse_page(BROWSE_PAGES[page_name], max_pages=2)
            print(f"\nFound {len(games)} games from {page_name}:")
            for g in games[:10]:
                print(f"  {g['creator']}: {g['title']}")
        else:
            print(f"Unknown page: {page_name}")
            print(f"Available: {', '.join(BROWSE_PAGES.keys())}")
    else:
        # Scrape all
        games = scrape_all_browse_pages(max_pages_per_source=1)
        print(f"\nTotal: {len(games)} unique games")
