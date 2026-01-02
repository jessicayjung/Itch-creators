import { sql } from "@vercel/postgres";
import type { RankedCreator, CreatorWithGames, Game, CreatorScore, LeaderboardFilter } from "./types";

// Build filter condition for leaderboard queries
function getFilterCondition(filter: LeaderboardFilter): string {
  switch (filter) {
    case 'qualified':
      return 'AND (cs.game_count >= 2 OR cs.total_ratings >= 5)';
    case 'multi-game':
      return 'AND cs.game_count >= 2';
    case 'well-rated':
      return 'AND cs.total_ratings >= 10';
    case 'rising':
      return 'AND cs.game_count = 1 AND cs.total_ratings BETWEEN 1 AND 4';
    case 'all':
    default:
      return '';
  }
}

export async function getRankedCreators(
  limit = 100,
  filter: LeaderboardFilter = 'qualified'
): Promise<RankedCreator[]> {
  const filterCondition = getFilterCondition(filter);

  // Use raw query to allow dynamic filter conditions
  const { rows } = await sql.query(`
    SELECT
      ROW_NUMBER() OVER (ORDER BY cs.bayesian_score DESC NULLS LAST) as rank,
      c.id,
      c.name,
      c.profile_url,
      cs.game_count,
      cs.total_ratings,
      cs.avg_rating,
      cs.bayesian_score,
      lg.title as latest_game_title,
      lg.publish_date as latest_game_date
    FROM creators c
    LEFT JOIN creator_scores cs ON c.id = cs.creator_id
    LEFT JOIN LATERAL (
      SELECT title, publish_date
      FROM games
      WHERE creator_id = c.id
      ORDER BY publish_date DESC NULLS LAST
      LIMIT 1
    ) lg ON true
    WHERE cs.bayesian_score IS NOT NULL
    ${filterCondition}
    ORDER BY cs.bayesian_score DESC NULLS LAST
    LIMIT $1
  `, [limit]);

  return rows.map((row) => ({
    rank: Number(row.rank),
    id: row.id,
    name: row.name,
    profile_url: row.profile_url,
    game_count: row.game_count ?? 0,
    total_ratings: row.total_ratings ?? 0,
    avg_rating: row.avg_rating ? Number(row.avg_rating) : null,
    bayesian_score: row.bayesian_score ? Number(row.bayesian_score) : null,
    latest_game_title: row.latest_game_title ?? null,
    latest_game_date: row.latest_game_date ? String(row.latest_game_date).split('T')[0] : null,
  }));
}

export async function getCreatorByName(name: string): Promise<CreatorWithGames | null> {
  // Get creator
  const { rows: creatorRows } = await sql`
    SELECT id, name, profile_url, backfilled, first_seen, updated_at
    FROM creators
    WHERE name = ${name}
  `;

  if (creatorRows.length === 0) {
    return null;
  }

  const creator = creatorRows[0];

  // Get games
  const { rows: gameRows } = await sql`
    SELECT id, itch_id, title, creator_id, url, publish_date, rating, rating_count, scraped_at, created_at
    FROM games
    WHERE creator_id = ${creator.id}
    ORDER BY publish_date DESC NULLS LAST
  `;

  const games: Game[] = gameRows.map((row) => ({
    id: row.id,
    itch_id: row.itch_id,
    title: row.title,
    creator_id: row.creator_id,
    url: row.url,
    publish_date: row.publish_date,
    rating: row.rating ? Number(row.rating) : null,
    rating_count: row.rating_count ?? 0,
    scraped_at: row.scraped_at,
    created_at: row.created_at,
  }));

  // Get score
  const { rows: scoreRows } = await sql`
    SELECT id, creator_id, game_count, total_ratings, avg_rating, bayesian_score, calculated_at
    FROM creator_scores
    WHERE creator_id = ${creator.id}
  `;

  const score: CreatorScore | null = scoreRows.length > 0 ? {
    id: scoreRows[0].id,
    creator_id: scoreRows[0].creator_id,
    game_count: scoreRows[0].game_count ?? 0,
    total_ratings: scoreRows[0].total_ratings ?? 0,
    avg_rating: scoreRows[0].avg_rating ? Number(scoreRows[0].avg_rating) : null,
    bayesian_score: scoreRows[0].bayesian_score ? Number(scoreRows[0].bayesian_score) : null,
    calculated_at: scoreRows[0].calculated_at,
  } : null;

  return {
    id: creator.id,
    name: creator.name,
    profile_url: creator.profile_url,
    backfilled: creator.backfilled,
    first_seen: creator.first_seen,
    updated_at: creator.updated_at,
    games,
    score,
  };
}

export async function getTotalCreatorCount(
  filter: LeaderboardFilter = 'qualified'
): Promise<number> {
  const filterCondition = getFilterCondition(filter);

  const { rows } = await sql.query(`
    SELECT COUNT(*) as count
    FROM creators c
    JOIN creator_scores cs ON c.id = cs.creator_id
    WHERE cs.bayesian_score IS NOT NULL
    ${filterCondition}
  `);
  return Number(rows[0].count);
}
