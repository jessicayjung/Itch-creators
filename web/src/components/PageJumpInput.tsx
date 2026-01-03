"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface PageJumpInputProps {
  currentPage: number;
  totalPages: number;
  filter: string;
  sort: string;
}

export default function PageJumpInput({ currentPage, totalPages, filter, sort }: PageJumpInputProps) {
  const [value, setValue] = useState("");
  const router = useRouter();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const pageNum = parseInt(value, 10);
    if (pageNum >= 1 && pageNum <= totalPages) {
      const params = new URLSearchParams();
      if (filter !== "all") params.set("filter", filter);
      if (sort !== "score") params.set("sort", sort);
      params.set("page", String(pageNum));
      router.push(`/?${params.toString()}`);
      setValue("");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <span className="text-sm text-zinc-500 dark:text-zinc-400">Go to:</span>
      <input
        type="number"
        min={1}
        max={totalPages}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="#"
        className="w-16 px-2 py-1 text-sm text-center rounded border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-slate-500"
      />
      <button
        type="submit"
        className="px-2 py-1 text-sm font-medium rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors"
      >
        Go
      </button>
    </form>
  );
}
