import type { Metadata } from "next";
import Link from "next/link";
import { BudgetBar } from "@/components/BudgetBar";
import { getIndex } from "@/lib/data";
import "./globals.css";

export const metadata: Metadata = {
  title: "RAG Eval Lab",
  description: "Versioned, hypothesis-driven evaluation and regression testing for RAG systems.",
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const index = await getIndex();
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <header className="border-b border-line bg-surface">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
            <Link href="/" className="font-semibold tracking-tight">RAG Eval Lab</Link>
            <nav className="flex gap-4 text-sm text-ink-2">
              <Link href="/" className="hover:text-ink">Experiments</Link>
              {index.datasets.map((d) => (
                <Link key={d} href={`/datasets/${d}/`} className="hover:text-ink">Dataset: {d}</Link>
              ))}
            </nav>
            <div className="ml-auto"><BudgetBar spent={index.budget.spent} total={index.budget.total} /></div>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
