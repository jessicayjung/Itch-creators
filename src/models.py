from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class Game:
    id: int | None
    itch_id: str
    title: str
    creator_name: str
    url: str
    publish_date: date | None
    rating: float | None
    rating_count: int
    comment_count: int
    description: str | None
    tags: list[str] | None
    scraped_at: datetime | None


@dataclass
class Creator:
    id: int | None
    name: str
    profile_url: str
    backfilled: bool
    first_seen: datetime


@dataclass
class CreatorScore:
    creator_id: int
    game_count: int
    total_ratings: int
    avg_rating: float
    bayesian_score: float
