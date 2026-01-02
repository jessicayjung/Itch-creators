import Link from "next/link";
import { getRankedCreators, getTotalCreatorCount } from "@/lib/db";

export const dynamic = "force-dynamic"; // Always render on request

export default async function Home() {
  const [creators, totalCount] = await Promise.all([
    getRankedCreators(100),
    getTotalCreatorCount(),
  ]);

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

      <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/50">
              <th className="px-4 py-3 text-left text-sm font-semibold text-zinc-900 dark:text-zinc-100 w-16">
                Rank
              </th>
              <th className="px-4 py-3 text-left text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                Creator
              </th>
              <th className="px-4 py-3 text-right text-sm font-semibold text-zinc-900 dark:text-zinc-100 w-24">
                Games
              </th>
              <th className="px-4 py-3 text-right text-sm font-semibold text-zinc-900 dark:text-zinc-100 w-28">
                Ratings
              </th>
              <th className="px-4 py-3 text-right text-sm font-semibold text-zinc-900 dark:text-zinc-100 w-24">
                Avg
              </th>
              <th className="px-4 py-3 text-right text-sm font-semibold text-zinc-900 dark:text-zinc-100 w-24">
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
                  {creator.bayesian_score?.toFixed(4) ?? "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {creators.length === 0 && (
        <div className="text-center py-12 text-zinc-500 dark:text-zinc-400">
          No creators found. Run the scraper to populate data.
        </div>
      )}
    </div>
  );
}
