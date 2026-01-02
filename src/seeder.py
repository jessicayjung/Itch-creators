"""Seed database with known prolific itch.io creators."""

from . import db
from .models import Creator
from datetime import datetime

# Known prolific itch.io creators
# Format: (username, profile_url)
KNOWN_CREATORS = [
    # Indie legends
    ("hempuli", "https://hempuli.itch.io"),
    ("sokpop", "https://sokpop.itch.io"),
    ("terrycavanagh", "https://terrycavanagh.itch.io"),
    ("mossmouth", "https://mossmouth.itch.io"),
    ("freebirdgames", "https://freebirdgames.itch.io"),
    ("devolverdigital", "https://devolverdigital.itch.io"),
    ("amanita-design", "https://amanita-design.itch.io"),
    ("dodgerollgames", "https://dodgerollgames.itch.io"),

    # Prolific jam creators
    ("managore", "https://managore.itch.io"),
    ("pietepiet", "https://pietepiet.itch.io"),
    ("npckc", "https://npckc.itch.io"),
    ("dukope", "https://dukope.itch.io"),
    ("ztiromoritz", "https://ztiromoritz.itch.io"),
    ("farmergnome", "https://farmergnome.itch.io"),
    ("johanpeitz", "https://johanpeitz.itch.io"),
    ("trasevol-dog", "https://trasevol-dog.itch.io"),
    ("pentadrangle", "https://pentadrangle.itch.io"),
    ("sylvie", "https://sylvie.itch.io"),
    ("notagoth", "https://notagoth.itch.io"),

    # Game jam regulars with many entries
    ("adamgryu", "https://adamgryu.itch.io"),
    ("mrmo", "https://mrmo.itch.io"),
    ("porpentine", "https://porpentine.itch.io"),
    ("vlambeer", "https://vlambeer.itch.io"),
    ("increpare", "https://increpare.itch.io"),
    ("thekla", "https://thekla.itch.io"),
    ("bitrich-info", "https://bitrich-info.itch.io"),
    ("kenney", "https://kenney.itch.io"),
    ("leafo", "https://leafo.itch.io"),

    # More prolific developers
    ("cannonbreed", "https://cannonbreed.itch.io"),
    ("madcock", "https://madcock.itch.io"),
    ("ncase", "https://ncase.itch.io"),
    ("daisyowl", "https://daisyowl.itch.io"),
    ("pixeljam", "https://pixeljam.itch.io"),
    ("glaielgames", "https://glaielgames.itch.io"),
    ("radicalfishgames", "https://radicalfishgames.itch.io"),
    ("tobyfox", "https://tobyfox.itch.io"),
    ("concerned-ape", "https://concerned-ape.itch.io"),
    ("playables", "https://playables.itch.io"),

    # More indie devs
    ("bfod", "https://bfod.itch.io"),
    ("eevee", "https://eevee.itch.io"),
    ("morphcat", "https://morphcat.itch.io"),
    ("davemakes", "https://davemakes.itch.io"),
    ("mightyvision", "https://mightyvision.itch.io"),
    ("cephalopodunk", "https://cephalopodunk.itch.io"),
    ("anotak", "https://anotak.itch.io"),
    ("futurecat", "https://futurecat.itch.io"),
    ("zaratustra", "https://zaratustra.itch.io"),
    ("tccoxon", "https://tccoxon.itch.io"),
]


def seed_creators() -> dict[str, int]:
    """
    Add known creators to database if they don't already exist.

    Returns:
        Dictionary with stats: {added, skipped}
    """
    stats = {"added": 0, "skipped": 0}

    for name, profile_url in KNOWN_CREATORS:
        existing = db.get_creator_by_name(name)
        if existing:
            stats["skipped"] += 1
            continue

        creator = Creator(
            id=None,
            name=name,
            profile_url=profile_url,
            backfilled=False,
            first_seen=datetime.now(),
        )
        db.insert_creator(creator)
        stats["added"] += 1
        print(f"Added creator: {name}")

    return stats


if __name__ == "__main__":
    print("Seeding database with known creators...")
    stats = seed_creators()
    print(f"\nDone! Added: {stats['added']}, Skipped: {stats['skipped']}")
