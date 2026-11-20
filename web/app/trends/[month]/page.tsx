import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiError, api } from "@/lib/api";
import { arMonth } from "@/lib/format";
import { TrendBody } from "@/components/TrendBody";

export const revalidate = 300;

export async function generateMetadata({ params }: { params: Promise<{ month: string }> }): Promise<Metadata> {
  const { month } = await params;
  return { title: /^\d{4}-\d{2}$/.test(month) ? `اتجاهات ${arMonth(month)}` : "الاتجاهات" };
}

export default async function TrendMonth({ params }: { params: Promise<{ month: string }> }) {
  const { month } = await params;
  const [stats, months] = await Promise.all([
    api.trend(month).catch((e) => { if (e instanceof ApiError && (e.status === 422 || e.status === 404)) notFound(); throw e; }),
    api.trendMonths(),
  ]);
  return (
    <div>
      <h1 className="page-title">اتجاهات {arMonth(month)}</h1>
      <nav className="issues" aria-label="الأشهر" style={{ margin: "0.75rem 0 1.5rem" }}>
        {months.slice(0, 12).map((m) => (
          <Link key={m.month} href={`/trends/${m.month}`} aria-current={m.month === month ? "page" : undefined}>{arMonth(m.month)}</Link>
        ))}
      </nav>
      {stats.report && (
        <section className="narrative" aria-labelledby="reading">
          <h2 id="reading" style={{ fontSize: "var(--s1)" }}>قراءة المحرر</h2>
          {stats.report.narrative_ar.split(/\n{2,}/).map((p, i) => <p key={i}>{p}</p>)}
        </section>
      )}
      <TrendBody stats={stats} />
    </div>
  );
}

