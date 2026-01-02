export interface Creator {
  id: number;
  name: string;
  profile_url: string;
  backfilled: boolean;
  first_seen: Date;
  updated_at: Date;
}

export interface Game {
  id: number;
  itch_id: string;
  title: string;
  creator_id: number;
  url: string;
  publish_date: Date | null;
  rating: number | null;
  rating_count: number;
  scraped_at: Date | null;
  created_at: Date;
}

export interface CreatorScore {
  id: number;
  creator_id: number;
  game_count: number;
  total_ratings: number;
  avg_rating: number | null;
  bayesian_score: number | null;
  calculated_at: Date;
}

export interface RankedCreator {
  rank: number;
  id: number;
  name: string;
  profile_url: string;
  game_count: number;
  total_ratings: number;
  avg_rating: number | null;
  bayesian_score: number | null;
  latest_game_title: string | null;
  latest_game_date: string | null;
}

export type LeaderboardFilter =
  | 'qualified'    // game_count >= 2 OR total_ratings >= 5
  | 'multi-game'   // game_count >= 2
  | 'well-rated'   // total_ratings >= 10
  | 'rising'       // 1 game with 1-4 ratings
  | 'all';         // no filter

export interface CreatorWithGames extends Creator {
  games: Game[];
  score: CreatorScore | null;
}
