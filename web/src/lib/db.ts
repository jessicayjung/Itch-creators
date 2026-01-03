import { Pool, PoolClient } from "pg";
import type { RankedCreator, CreatorWithGames, Game, CreatorScore, LeaderboardFilter, LeaderboardSort } from "./types";

// Module-level pool variable (initialized lazily)
let _pool: Pool | null = null;

// Get or create the connection pool
function getPool(): Pool {
  if (_pool === null) {
    _pool = new Pool({
      connectionString: process.env.POSTGRES_URL,
      min: 1,
      max: 5,
    });
  }
  return _pool;
}

// Get a connection from the pool
async function getConnection(): Promise<PoolClient> {
  const pool = getPool();
  return pool.connect();
}

// Close the pool (for cleanup)
export async function closePool(): Promise<void> {
  if (_pool !== null) {
    await _pool.end();
    _pool = null;
  }
}

// Build filter condition for leaderboard queries
function getFilterCondition(filter: LeaderboardFilter): string {
  switch (filter) {
    case 'multi-game':
      return 'AND cs.game_count >= 2';
    case 'well-rated':
      return 'AND cs.total_ratings >= 10';
    case 'rising':
      // Creators with highly rated games (4.0+) published in 2025 or later
      return `AND EXISTS (
        SELECT 1 FROM games g
        WHERE g.creator_id = c.id
          AND g.publish_date >= '2025-01-01'
          AND g.rating >= 4.0
      )`;
    case 'all':
    default:
      return '';
  }
}

// Build ORDER BY clause based on sort option
// Weights higher game count over perfect ratings with fewer games
function getSortOrder(sort: LeaderboardSort): string {
  switch (sort) {
    case 'games':
      return `cs.game_count DESC, cs.bayesian_score DESC NULLS LAST, cs.total_ratings DESC, c.id`;
    case 'ratings':
      return `cs.total_ratings DESC, cs.game_count DESC, cs.bayesian_score DESC NULLS LAST, c.id`;
    case 'avg':
      return `cs.avg_rating DESC NULLS LAST, cs.game_count DESC, cs.total_ratings DESC, c.id`;
    case 'score':
    default:
      // Default: Bayesian score with game count as strong tiebreaker
      return `cs.bayesian_score DESC NULLS LAST, cs.game_count DESC, cs.total_ratings DESC, c.id`;
  }
}

export async function getRankedCreators(
  limit = 50,
  offset = 0,
  filter: LeaderboardFilter = 'all',
  sort: LeaderboardSort = 'score'
): Promise<RankedCreator[]> {
  const filterCondition = getFilterCondition(filter);
  const sortOrder = getSortOrder(sort);
  const client = await getConnection();

  try {
    // Use raw query to allow dynamic filter and sort conditions
    const { rows } = await client.query(`
      SELECT
        ROW_NUMBER() OVER (
          ORDER BY ${sortOrder}
        ) as rank,
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
      ORDER BY ${sortOrder}
      LIMIT $1 OFFSET $2
    `, [limit, offset]);

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
  } finally {
    client.release();
  }
}

export async function getCreatorByName(name: string): Promise<CreatorWithGames | null> {
  const client = await getConnection();

  try {
    // Get creator
    const { rows: creatorRows } = await client.query(
      `SELECT id, name, profile_url, backfilled, first_seen, updated_at
       FROM creators
       WHERE name = $1`,
      [name]
    );

    if (creatorRows.length === 0) {
      return null;
    }

    const creator = creatorRows[0];

    // Get games
    const { rows: gameRows } = await client.query(
      `SELECT id, itch_id, title, creator_id, url, publish_date, rating, rating_count, comment_count, description, scraped_at, created_at
       FROM games
       WHERE creator_id = $1
       ORDER BY publish_date DESC NULLS LAST`,
      [creator.id]
    );

    const games: Game[] = gameRows.map((row) => ({
      id: row.id,
      itch_id: row.itch_id,
      title: row.title,
      creator_id: row.creator_id,
      url: row.url,
      publish_date: row.publish_date,
      rating: row.rating ? Number(row.rating) : null,
      rating_count: row.rating_count ?? 0,
      comment_count: row.comment_count ?? 0,
      description: row.description ?? null,
      scraped_at: row.scraped_at,
      created_at: row.created_at,
    }));

    // Get score
    const { rows: scoreRows } = await client.query(
      `SELECT id, creator_id, game_count, total_ratings, avg_rating, bayesian_score, calculated_at
       FROM creator_scores
       WHERE creator_id = $1`,
      [creator.id]
    );

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
  } finally {
    client.release();
  }
}

export async function getTotalCreatorCount(
  filter: LeaderboardFilter = 'all'
): Promise<number> {
  const filterCondition = getFilterCondition(filter);
  const client = await getConnection();

  try {
    const { rows } = await client.query(`
      SELECT COUNT(*) as count
      FROM creators c
      JOIN creator_scores cs ON c.id = cs.creator_id
      WHERE cs.bayesian_score IS NOT NULL
      ${filterCondition}
    `);
    return Number(rows[0].count);
  } finally {
    client.release();
  }
}
