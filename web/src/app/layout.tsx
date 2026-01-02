import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "itch.io Creator Rankings",
  description: "Discover top itch.io game creators ranked by game quality and ratings",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-zinc-50 dark:bg-zinc-950`}
      >
        <div className="min-h-screen">
          <header className="border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
            <div className="max-w-6xl mx-auto px-4 py-4">
              <a href="/" className="text-xl font-bold text-zinc-900 dark:text-zinc-100">
                itch.io Creator Rankings
              </a>
            </div>
          </header>
          <main className="max-w-6xl mx-auto px-4 py-8">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
