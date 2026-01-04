#!/usr/bin/env python3
"""
CLI entry point for itch-creators scraper.
"""
import argparse
import sys
from datetime import datetime
from urllib.parse import urlparse, urlunparse

from . import backfiller, browse_scraper, db, enricher, feed_poller, scorer, seeder
from .logger import setup_logger, LogContext
from .models import Creator

logger = setup_logger(__name__)


def cmd_poll(args):
    """Poll RSS feeds for new games and creators."""
    logger.info("Polling RSS feeds...")

    entries = feed_poller.get_new_releases()
    logger.info(f"Found {len(entries)} new releases")

    new_creators = 0
    new_games = 0

    for entry in entries:
        # Skip entries where creator could not be extracted
        if not entry["creator"]:
            logger.warning(f"Could not extract creator from URL: {entry['game_url']}")
            continue

        # Check if creator exists, if not create them
        creator = db.get_creator_by_name(entry["creator"])

        if not creator:
            # Extract profile URL from game URL
            profile_url = _extract_profile_url(entry["game_url"])

            creator = Creator(
                id=None,
                name=entry["creator"],
                profile_url=profile_url,
                backfilled=False,
                first_seen=datetime.now()
            )

            creator_id = db.insert_creator(creator)
            if creator_id:
                new_creators += 1
                logger.info(f"New creator: {entry['creator']}")

        # Extract game ID from URL
        game_id = backfiller._extract_game_id(entry["game_url"])

        # Create game object
        from .models import Game
        game = Game(
            id=None,
            itch_id=game_id,
            title=entry["title"],
            creator_name=entry["creator"],
            url=entry["game_url"],
            publish_date=entry["publish_date"].date() if entry["publish_date"] else None,
            rating=None,
            rating_count=0,
            comment_count=0,
            description=None,
            tags=None,
            scraped_at=None
        )

        inserted_id = db.insert_game(game)
        if inserted_id:
            new_games += 1

    logger.info(f"Results: new_creators={new_creators}, new_games={new_games}")


def cmd_backfill(args):
    """Backfill creator game histories."""
    with LogContext(logger, "Backfilling creators"):
        stats = backfiller.backfill_all()

    logger.info(f"Results: creators_processed={stats['creators_processed']}, games_inserted={stats['games_inserted']}, errors={stats['errors']}")


def cmd_enrich(args):
    """Enrich games with ratings."""
    limit = getattr(args, 'limit', None)

    with LogContext(logger, "Enriching game ratings"):
        stats = enricher.enrich_all(limit=limit)

    logger.info(f"Results: games_processed={stats['games_processed']}, errors={stats['errors']}")


def cmd_re_enrich(args):
    """Re-enrich stale games to update ratings and data."""
    days = getattr(args, 'days', 7)
    limit = getattr(args, 'limit', 500)

    with LogContext(logger, f"Re-enriching games older than {days} days"):
        stats = enricher.re_enrich_stale(days_old=days, limit=limit)

    logger.info(f"Results: games_processed={stats['games_processed']}, errors={stats['errors']}")


def cmd_score(args):
    """Recalculate creator scores."""
    with LogContext(logger, "Calculating creator scores"):
        stats = scorer.score_all()

    logger.info(f"Results: creators_scored={stats['creators_scored']}")


def cmd_run(args):
    """Run full pipeline: poll → discover → backfill → enrich → re-enrich → score."""
    with LogContext(logger, "Running full pipeline"):
        cmd_poll(args)
        cmd_discover(args)
        cmd_backfill(args)
        cmd_enrich(args)
        cmd_re_enrich(args)
        cmd_score(args)

    logger.info("Pipeline complete!")


def cmd_init_db(args):
    """Initialize database schema."""
    logger.info("Initializing database...")
    db.create_tables()
    logger.info("Database initialized successfully!")


def _extract_profile_url(game_url: str) -> str:
    """
    Extract creator profile URL from game URL.

    Example:
        https://testdev.itch.io/cool-game -> https://testdev.itch.io
        testdev.itch.io/cool-game -> https://testdev.itch.io

    Args:
        game_url: Full game URL

    Returns:
        Profile URL
    """
    # Add scheme if missing
    if not game_url.startswith(("http://", "https://")):
        game_url = "https://" + game_url

    parsed = urlparse(game_url)
    # Reconstruct with just scheme and netloc (domain)
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def cmd_seed(args):
    """Seed database with known prolific creators."""
    with LogContext(logger, "Seeding known creators"):
        stats = seeder.seed_creators()
        logger.info(f"Results: added={stats['added']}, skipped={stats['skipped']}")


def cmd_discover(args):
    """Discover creators from itch.io browse pages."""
    max_pages = getattr(args, 'pages', 2)

    with LogContext(logger, "Discovering creators from browse pages"):
        games = browse_scraper.scrape_all_browse_pages(max_pages_per_source=max_pages)

    new_creators = 0
    new_games = 0

    for game in games:
        if not game["creator"]:
            continue

        # Check if creator exists, if not create them
        creator = db.get_creator_by_name(game["creator"])

        if not creator:
            profile_url = _extract_profile_url(game["url"])

            creator = Creator(
                id=None,
                name=game["creator"],
                profile_url=profile_url,
                backfilled=False,
                first_seen=datetime.now()
            )

            creator_id = db.insert_creator(creator)
            if creator_id:
                new_creators += 1

        # Extract game ID and insert
        game_id = backfiller._extract_game_id(game["url"])

        from .models import Game
        game_obj = Game(
            id=None,
            itch_id=game_id,
            title=game["title"],
            creator_name=game["creator"],
            url=game["url"],
            publish_date=None,
            rating=None,
            rating_count=0,
            comment_count=0,
            description=None,
            tags=None,
            scraped_at=None
        )

        inserted_id = db.insert_game(game_obj)
        if inserted_id:
            new_games += 1

    logger.info(f"Results: games_found={len(games)}, new_creators={new_creators}, new_games={new_games}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="itch.io creator ranking scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init-db command
    subparsers.add_parser("init-db", help="Initialize database schema")

    # poll command
    subparsers.add_parser("poll", help="Poll RSS feeds for new releases")

    # backfill command
    subparsers.add_parser("backfill", help="Backfill creator game histories")

    # enrich command
    enrich_parser = subparsers.add_parser("enrich", help="Enrich games with ratings")
    enrich_parser.add_argument("--limit", type=int, default=None, help="Max games to process per run (default: unlimited)")

    # score command
    subparsers.add_parser("score", help="Recalculate creator scores")

    # run command
    subparsers.add_parser("run", help="Run full pipeline")

    # seed command
    subparsers.add_parser("seed", help="Seed database with known prolific creators")

    # discover command
    discover_parser = subparsers.add_parser("discover", help="Discover creators from browse pages")
    discover_parser.add_argument("--pages", type=int, default=2, help="Pages to scrape per source (default: 2)")

    # re-enrich command
    re_enrich_parser = subparsers.add_parser("re-enrich", help="Re-enrich stale games to update ratings")
    re_enrich_parser.add_argument("--days", type=int, default=7, help="Re-enrich games older than X days (default: 7)")
    re_enrich_parser.add_argument("--limit", type=int, default=500, help="Max games to process per run (default: 500)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    commands = {
        "init-db": cmd_init_db,
        "poll": cmd_poll,
        "backfill": cmd_backfill,
        "enrich": cmd_enrich,
        "re-enrich": cmd_re_enrich,
        "score": cmd_score,
        "run": cmd_run,
        "seed": cmd_seed,
        "discover": cmd_discover,
    }

    command_func = commands.get(args.command)
    if command_func:
        try:
            command_func(args)
        except KeyboardInterrupt:
            logger.warning("Interrupted by user")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
