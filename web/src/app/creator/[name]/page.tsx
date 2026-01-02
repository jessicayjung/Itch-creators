import { notFound } from "next/navigation";
import Link from "next/link";
import { getCreatorByName } from "@/lib/db";

export const dynamic = "force-dynamic"; // Always render on request

interface Props {
  params: Promise<{ name: string }>;
}

export async function generateMetadata({ params }: Props) {
  const { name } = await params;
  const decodedName = decodeURIComponent(name);
  return {
    title: `${decodedName} - itch.io Creator Rankings`,
  };
}

export default async function CreatorPage({ params }: Props) {
  const { name } = await params;
  const decodedName = decodeURIComponent(name);
  const creator = await getCreatorByName(decodedName);

  if (!creator) {
    notFound();
  }

  const ratedGames = creator.games.filter((g) => g.rating !== null);
  const unratedGames = creator.games.filter((g) => g.rating === null);

  return (
    <div>
      <div className="mb-2">
        <Link
          href="/"
          className="text-sm text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-300"
        >
          &larr; Back to rankings
        </Link>
      </div>

      <div className="mb-8">
        <div className="flex items-center gap-4 mb-4">
          <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100">
            {creator.name}
          </h1>
          <a
            href={creator.profile_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
          >
            View on itch.io &rarr;
          </a>
        </div>

        {creator.score && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-4">
              <div className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 font-mono">
                {creator.score.bayesian_score?.toFixed(4) ?? "-"}
              </div>
              <div className="text-sm text-zinc-500 dark:text-zinc-400">
                Bayesian Score
              </div>
            </div>
            <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-4">
              <div className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 font-mono">
                {creator.score.game_count}
              </div>
              <div className="text-sm text-zinc-500 dark:text-zinc-400">
                Total Games
              </div>
            </div>
            <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-4">
              <div className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 font-mono">
                {creator.score.total_ratings.toLocaleString()}
              </div>
              <div className="text-sm text-zinc-500 dark:text-zinc-400">
                Total Ratings
              </div>
            </div>
            <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-4">
              <div className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 font-mono">
                {creator.score.avg_rating?.toFixed(2) ?? "-"}
              </div>
              <div className="text-sm text-zinc-500 dark:text-zinc-400">
                Average Rating
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="mb-8">
        <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100 mb-4">
          Games ({creator.games.length})
        </h2>

        {ratedGames.length > 0 && (
          <div className="mb-6">
            <h3 className="text-sm font-medium text-zinc-500 dark:text-zinc-400 mb-3">
              Rated Games ({ratedGames.length})
            </h3>
            <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                <thead>
                  <tr className="border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/50">
                    <th className="px-4 py-3 text-left text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                      Title
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                      Description & Stats
                    </th>
                    <th className="px-4 py-3 text-right text-sm font-semibold text-zinc-900 dark:text-zinc-100 w-32">
                      Published
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {ratedGames.map((game) => (
                    <tr
                      key={game.id}
                      className="border-b border-zinc-100 dark:border-zinc-800 last:border-0"
                    >
                      <td className="px-4 py-3">
                        <a
                          href={game.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-medium text-zinc-900 dark:text-zinc-100 hover:text-blue-600 dark:hover:text-blue-400"
                        >
                          {game.title || game.url.split('/').pop() || 'Untitled'}
                        </a>
                        {!game.title && (
                          <span className="ml-2 text-xs text-zinc-400">(title pending)</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {game.description && (
                          <div className="text-sm text-zinc-600 dark:text-zinc-400 mb-2">
                            {game.description.length > 150
                              ? game.description.slice(0, 150) + '...'
                              : game.description}
                          </div>
                        )}
                        <div className="flex gap-4 text-xs text-zinc-500 dark:text-zinc-500">
                          <div className="flex items-center gap-1">
                            <span className="font-medium text-zinc-900 dark:text-zinc-100 font-mono">
                              {game.rating?.toFixed(2)}
                            </span>
                            <span>({game.rating_count.toLocaleString()} ratings)</span>
                          </div>
                          {game.comment_count > 0 && (
                            <div>
                              {game.comment_count.toLocaleString()} comments
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right text-sm text-zinc-600 dark:text-zinc-400">
                        {game.publish_date
                          ? new Date(game.publish_date).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
                          : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </div>
          </div>
        )}

        {unratedGames.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-zinc-500 dark:text-zinc-400 mb-3">
              Unrated Games ({unratedGames.length})
            </h3>
            <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                <thead>
                  <tr className="border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/50">
                    <th className="px-4 py-3 text-left text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                      Title
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                      Description & Stats
                    </th>
                    <th className="px-4 py-3 text-right text-sm font-semibold text-zinc-900 dark:text-zinc-100 w-32">
                      Published
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {unratedGames.map((game) => (
                    <tr
                      key={game.id}
                      className="border-b border-zinc-100 dark:border-zinc-800 last:border-0"
                    >
                      <td className="px-4 py-3">
                        <a
                          href={game.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-zinc-600 dark:text-zinc-400 hover:text-blue-600 dark:hover:text-blue-400"
                        >
                          {game.title || game.url.split('/').pop() || 'Untitled'}
                        </a>
                        {!game.title && (
                          <span className="ml-2 text-xs text-zinc-400">(title pending)</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {game.description && (
                          <div className="text-sm text-zinc-600 dark:text-zinc-400 mb-2">
                            {game.description.length > 150
                              ? game.description.slice(0, 150) + '...'
                              : game.description}
                          </div>
                        )}
                        {game.comment_count > 0 && (
                          <div className="text-xs text-zinc-500 dark:text-zinc-500">
                            {game.comment_count.toLocaleString()} comments
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right text-sm text-zinc-600 dark:text-zinc-400">
                        {game.publish_date
                          ? new Date(game.publish_date).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
                          : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </div>
          </div>
        )}

        {creator.games.length === 0 && (
          <div className="text-center py-12 text-zinc-500 dark:text-zinc-400">
            No games found for this creator.
          </div>
        )}
      </div>
    </div>
  );
}
