import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiError, api } from "@/lib/api";
import { arMonth } from "@/lib/format";
import { TrendBody } from "@/components/TrendBody";
import { PageHead } from "@/components/PageHead";

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
    <>
      <PageHead kicker="الاتجاهات الشهرية" title={arMonth(month)}
        lede="ما الذي شغل مراكز الفكر والمجلات المحكّمة في هذا الشهر: الأرقام، وقراءة المحرّر حين تُنشر." />
      {months.length > 1 && (
        <nav className="month-nav" aria-label="الأشهر">
          {months.slice(0, 12).map((m) => (
            <Link key={m.month} href={`/trends/${m.month}`} aria-current={m.month === month ? "page" : undefined}>{arMonth(m.month)}</Link>
          ))}
        </nav>
      )}
      {stats.report && (
        <section className="narrative" aria-labelledby="reading">
          <h2 id="reading" className="kicker" style={{ marginBottom: "var(--space-2)" }}>قراءة المحرّر</h2>
          {stats.report.narrative_ar.split(/\n{2,}/).map((p, i) => <p key={i}>{p}</p>)}
        </section>
      )}
      <TrendBody stats={stats} />
    </>
  );
}
