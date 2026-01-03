import Link from "next/link";
import { getRankedCreators, getTotalCreatorCount } from "@/lib/db";
import type { LeaderboardFilter, LeaderboardSort } from "@/lib/types";
import PageJumpInput from "@/components/PageJumpInput";

export const dynamic = "force-dynamic"; // Always render on request

interface PageProps {
  searchParams: Promise<{ filter?: string; page?: string; sort?: string }>;
}

const PAGE_SIZE = 50;

const FILTERS: { value: LeaderboardFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'multi-game', label: '2+ Games' },
  { value: 'well-rated', label: '10+ Ratings' },
  { value: 'rising', label: 'Rising' },
];

const SORTS: { value: LeaderboardSort; label: string }[] = [
  { value: 'score', label: 'Score' },
  { value: 'games', label: 'Games' },
  { value: 'ratings', label: 'Ratings' },
  { value: 'avg', label: 'Avg Rating' },
];

export default async function Home({ searchParams }: PageProps) {
  const params = await searchParams;
  const filter = (params.filter as LeaderboardFilter) || 'all';
  const sort = (params.sort as LeaderboardSort) || 'score';
  const page = Math.max(1, parseInt(params.page || '1', 10));
  const offset = (page - 1) * PAGE_SIZE;

  const [creators, totalCount] = await Promise.all([
    getRankedCreators(PAGE_SIZE, offset, filter, sort),
    getTotalCreatorCount(filter),
  ]);

  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">
          Top Creators
        </h1>
        <p className="text-zinc-600 dark:text-zinc-400">
          {totalCount} creators ranked by Bayesian score based on game ratings
        </p>
      </div>

      {/* Filter and Sort Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex gap-2">
            {FILTERS.map((f) => {
              const href = new URLSearchParams();
              if (f.value !== 'all') href.set('filter', f.value);
              if (sort !== 'score') href.set('sort', sort);
              const query = href.toString();
              return (
                <Link
                  key={f.value}
                  href={query ? `/?${query}` : '/'}
                  className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                    filter === f.value
                      ? 'bg-slate-800 text-white'
                      : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700'
                  }`}
                >
                  {f.label}
                </Link>
              );
            })}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-zinc-500 dark:text-zinc-400">Sort:</span>
            <div className="flex gap-1">
              {SORTS.map((s) => {
                const href = new URLSearchParams();
                if (filter !== 'all') href.set('filter', filter);
                if (s.value !== 'score') href.set('sort', s.value);
                const query = href.toString();
                return (
                  <Link
                    key={s.value}
                    href={query ? `/?${query}` : '/'}
                    className={`px-3 py-1 text-sm font-medium rounded transition-colors ${
                      sort === s.value
                        ? 'bg-slate-600 text-white'
                        : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700'
                    }`}
                  >
                    {s.label}
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
        {/* Top Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-zinc-500 dark:text-zinc-400">
              Page {page}/{totalPages}
            </span>
            <div className="flex gap-1">
              {page > 1 && (
                <Link
                  href={`/?${new URLSearchParams({ ...(filter !== 'all' && { filter }), ...(sort !== 'score' && { sort }), page: String(page - 1) }).toString()}`}
                  className="px-3 py-1 text-sm font-medium rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700"
                >
                  Prev
                </Link>
              )}
              {page < totalPages && (
                <Link
                  href={`/?${new URLSearchParams({ ...(filter !== 'all' && { filter }), ...(sort !== 'score' && { sort }), page: String(page + 1) }).toString()}`}
                  className="px-3 py-1 text-sm font-medium rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700"
                >
                  Next
                </Link>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
          <thead>
            <tr className="border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/50">
              <th className="px-4 py-3 text-left text-sm font-semibold text-zinc-900 dark:text-zinc-100 w-16">
                Rank
              </th>
              <th className="px-4 py-3 text-left text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                Creator
              </th>
              <th className="px-4 py-3 text-left text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                Latest Game
              </th>
              <th className="px-4 py-3 text-right text-sm font-semibold text-zinc-900 dark:text-zinc-100 w-20">
                Games
              </th>
              <th className="px-4 py-3 text-right text-sm font-semibold text-zinc-900 dark:text-zinc-100 w-24">
                Ratings
              </th>
              <th className="px-4 py-3 text-right text-sm font-semibold text-zinc-900 dark:text-zinc-100 w-20">
                Avg
              </th>
              <th className="px-4 py-3 text-right text-sm font-semibold text-zinc-900 dark:text-zinc-100 w-20">
                Score
              </th>
            </tr>
          </thead>
          <tbody>
            {creators.map((creator) => (
              <tr
                key={creator.id}
                className="border-b border-zinc-100 dark:border-zinc-800 last:border-0 hover:bg-zinc-50 dark:hover:bg-zinc-800/30 transition-colors"
              >
                <td className="px-4 py-3 text-sm text-zinc-500 dark:text-zinc-400 font-mono">
                  #{creator.rank}
                </td>
                <td className="px-4 py-3">
                  <Link
                    href={`/creator/${encodeURIComponent(creator.name)}`}
                    className="text-sm font-medium text-zinc-900 dark:text-zinc-100 hover:text-blue-600 dark:hover:text-blue-400"
                  >
                    {creator.name}
                  </Link>
                  <a
                    href={creator.profile_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-2 text-xs text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
                  >
                    itch.io
                  </a>
                </td>
                <td className="px-4 py-3">
                  {(creator.latest_game_title || creator.latest_game_date) ? (
                    <div className="text-sm">
                      <span className="text-zinc-700 dark:text-zinc-300">
                        {creator.latest_game_title || '(title pending)'}
                      </span>
                      {creator.latest_game_date && (
                        <span className="ml-2 text-xs text-zinc-400">
                          {new Date(creator.latest_game_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                        </span>
                      )}
                    </div>
                  ) : (
                    <span className="text-sm text-zinc-400">-</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right text-sm text-zinc-600 dark:text-zinc-400 font-mono">
                  {creator.game_count}
                </td>
                <td className="px-4 py-3 text-right text-sm text-zinc-600 dark:text-zinc-400 font-mono">
                  {creator.total_ratings.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right text-sm text-zinc-600 dark:text-zinc-400 font-mono">
                  {creator.avg_rating?.toFixed(2) ?? "-"}
                </td>
                <td className="px-4 py-3 text-right text-sm font-medium text-zinc-900 dark:text-zinc-100 font-mono">
                  {creator.bayesian_score?.toFixed(2) ?? "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      {creators.length === 0 && (
        <div className="text-center py-12 text-zinc-500 dark:text-zinc-400">
          No creators found matching this filter.
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-6">
          <div className="flex items-center gap-4">
            <div className="text-sm text-zinc-500 dark:text-zinc-400">
              Page {page} of {totalPages} ({totalCount} creators)
            </div>
            <PageJumpInput currentPage={page} totalPages={totalPages} filter={filter} sort={sort} />
          </div>
          <div className="flex gap-2">
            {page > 1 && (
              <Link
                href={`/?${new URLSearchParams({ ...(filter !== 'all' && { filter }), ...(sort !== 'score' && { sort }), page: String(page - 1) }).toString()}`}
                className="px-4 py-2 text-sm font-medium rounded-lg bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors"
              >
                Previous
              </Link>
            )}
            {/* Page numbers */}
            <div className="flex gap-1">
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let pageNum: number;
                if (totalPages <= 5) {
                  pageNum = i + 1;
                } else if (page <= 3) {
                  pageNum = i + 1;
                } else if (page >= totalPages - 2) {
                  pageNum = totalPages - 4 + i;
                } else {
                  pageNum = page - 2 + i;
                }
                return (
                  <Link
                    key={pageNum}
                    href={`/?${new URLSearchParams({ ...(filter !== 'all' && { filter }), ...(sort !== 'score' && { sort }), page: String(pageNum) }).toString()}`}
                    className={`w-10 h-10 flex items-center justify-center text-sm font-medium rounded-lg transition-colors ${
                      page === pageNum
                        ? 'bg-slate-800 text-white'
                        : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700'
                    }`}
                  >
                    {pageNum}
                  </Link>
                );
              })}
            </div>
            {page < totalPages && (
              <Link
                href={`/?${new URLSearchParams({ ...(filter !== 'all' && { filter }), ...(sort !== 'score' && { sort }), page: String(page + 1) }).toString()}`}
                className="px-4 py-2 text-sm font-medium rounded-lg bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors"
              >
                Next
              </Link>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
