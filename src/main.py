#!/usr/bin/env python3
"""
CLI entry point for itch-creators scraper.
"""
import argparse
import sys
from datetime import datetime

from . import backfiller, db, enricher, feed_poller, scorer
from .models import Creator


def cmd_poll(args):
    """Poll RSS feeds for new games and creators."""
    print("Polling RSS feeds...")

    entries = feed_poller.get_new_releases()
    print(f"Found {len(entries)} new releases")

    new_creators = 0
    new_games = 0

    for entry in entries:
        # Skip entries where creator could not be extracted
        if not entry["creator"]:
            print(f"  Warning: Could not extract creator from URL: {entry['game_url']}")
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
                print(f"  New creator: {entry['creator']}")

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
            scraped_at=None
        )

        inserted_id = db.insert_game(game)
        if inserted_id:
            new_games += 1

    print(f"\nResults:")
    print(f"  New creators: {new_creators}")
    print(f"  New games: {new_games}")


def cmd_backfill(args):
    """Backfill creator game histories."""
    print("Backfilling creators...")

    stats = backfiller.backfill_all()

    print(f"\nResults:")
    print(f"  Creators processed: {stats['creators_processed']}")
    print(f"  Games inserted: {stats['games_inserted']}")
    print(f"  Errors: {stats['errors']}")


def cmd_enrich(args):
    """Enrich games with ratings."""
    print("Enriching game ratings...")

    stats = enricher.enrich_all()

    print(f"\nResults:")
    print(f"  Games processed: {stats['games_processed']}")
    print(f"  Errors: {stats['errors']}")


def cmd_score(args):
    """Recalculate creator scores."""
    print("Calculating creator scores...")

    stats = scorer.score_all()

    print(f"\nResults:")
    print(f"  Creators scored: {stats['creators_scored']}")


def cmd_run(args):
    """Run full pipeline: poll → backfill → enrich → score."""
    print("Running full pipeline...\n")

    print("=" * 50)
    cmd_poll(args)

    print("\n" + "=" * 50)
    cmd_backfill(args)

    print("\n" + "=" * 50)
    cmd_enrich(args)

    print("\n" + "=" * 50)
    cmd_score(args)

    print("\n" + "=" * 50)
    print("Pipeline complete!")


def cmd_init_db(args):
    """Initialize database schema."""
    print("Initializing database...")
    db.create_tables()
    print("Database initialized successfully!")


def _extract_profile_url(game_url: str) -> str:
    """
    Extract creator profile URL from game URL.

    Example:
        https://testdev.itch.io/cool-game -> https://testdev.itch.io

    Args:
        game_url: Full game URL

    Returns:
        Profile URL
    """
    parts = game_url.split("/")
    if len(parts) >= 3:
        # Reconstruct: protocol + // + domain
        return f"{parts[0]}//{parts[2]}"
    return game_url


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
    subparsers.add_parser("enrich", help="Enrich games with ratings")

    # score command
    subparsers.add_parser("score", help="Recalculate creator scores")

    # run command
    subparsers.add_parser("run", help="Run full pipeline")

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
        "score": cmd_score,
        "run": cmd_run,
    }

    command_func = commands.get(args.command)
    if command_func:
        try:
            command_func(args)
        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"\nError: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
