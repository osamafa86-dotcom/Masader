import Link from "next/link";
import type { TrendRow, TrendStats } from "@/lib/types";
import { BarChart } from "./BarChart";

const bars = (rows: TrendRow[], hrefBase?: string, limit = 12) =>
  rows.filter((r) => r.count > 0).slice(0, limit).map((r) => ({
    key: r.slug, label: r.name_ar, value: r.count, previous: r.previous, href: hrefBase ? `${hrefBase}/${r.slug}` : undefined,
  }));

function change(n: number) {
  // Isolated left-to-right so the sign stays in front of the number in Arabic text.
  return <bdi dir="ltr">{n > 0 ? `+${n}` : `${n}`}</bdi>;
}

export function TrendBody({ stats }: { stats: TrendStats }) {
  if (stats.empty) {
    return <p className="empty">لم نرصد مواد منشورة في هذا الشهر، فلا توجد اتجاهات نعرضها.</p>;
  }
  const max = Math.max(...stats.topics.map((t) => t.count), ...stats.regions.map((t) => t.count), 1);
  return (
    <>
      <div className="stat-line">
        <div><strong>{stats.total}</strong><span>مادة رُصدت هذا الشهر</span></div>
        <div><strong>{change(stats.total - stats.previous_total)}</strong><span>مقارنة بالشهر السابق ({stats.previous_total})</span></div>
        <div><strong>{stats.sources.filter((s) => s.count > 0).length}</strong><span>مصدراً نشطاً</span></div>
      </div>
      {stats.small_sample && <p className="notice">عدد المواد قليل هذا الشهر، فلا تكفي الأرقام لاستنتاج اتجاه.</p>}

      {(stats.rising_topics.length > 0 || stats.falling_topics.length > 0) && (
        <section className="trend-grid" style={{ marginBottom: "2rem" }}>
          {stats.rising_topics.length > 0 && <div>
            <h2 style={{ fontSize: "1rem" }}>موضوعات صاعدة</h2>
            <ul className="ui" style={{ paddingInlineStart: "1.2rem" }}>
              {stats.rising_topics.map((r) => <li key={r.slug}><Link href={`/topics/${r.slug}`}>{r.name_ar}</Link>: {r.count} مادة، ومتوسط الأشهر الثلاثة السابقة {r.avg_3m}</li>)}
            </ul>
          </div>}
          {stats.falling_topics.length > 0 && <div>
            <h2 style={{ fontSize: "1rem" }}>موضوعات متراجعة</h2>
            <ul className="ui" style={{ paddingInlineStart: "1.2rem" }}>
              {stats.falling_topics.map((r) => <li key={r.slug}><Link href={`/topics/${r.slug}`}>{r.name_ar}</Link>: {r.count} مادة، ومتوسط الأشهر الثلاثة السابقة {r.avg_3m}</li>)}
            </ul>
          </div>}
        </section>
      )}

      <div className="trend-grid">
        <BarChart title="المواد بحسب الموضوع" bars={bars(stats.topics, "/topics")} max={max} />
        <BarChart title="المواد بحسب المنطقة" bars={bars(stats.regions, "/regions")} max={max} />
        <BarChart title="أكثر المصادر نشاطاً" bars={bars(stats.sources, "/sources", 10)} />
        <BarChart title="التوزع على أسابيع الشهر" unit="مادة"
                  bars={stats.weeks.map((w) => ({ key: String(w.week), label: `الأسبوع ${w.week}`, value: w.count }))} />
      </div>

      {stats.rising_keywords.length > 0 && (
        <section>
          <h2 style={{ fontSize: "1rem" }}>كلمات مفتاحية متكررة</h2>
          <ul className="issues">{stats.rising_keywords.map((k) => (
            <li key={k.keyword}><Link href={`/search?q=${encodeURIComponent(k.keyword)}`}><bdi dir="auto">{k.keyword}</bdi> ({k.count})</Link></li>
          ))}</ul>
        </section>
      )}
      {stats.top_items.length > 0 && (
        <section>
          <h2 style={{ fontSize: "1rem" }}>أهم مواد الشهر</h2>
          <ol className="ui" style={{ paddingInlineStart: "1.2rem", lineHeight: 2 }}>
            {stats.top_items.map((t) => <li key={t.id}><Link href={`/articles/${t.id}`}>{t.title_ar}</Link> <span className="muted">، {t.source}</span></li>)}
          </ol>
        </section>
      )}
      <p className="ui muted" style={{ marginTop: "2rem" }}>
        تُحسب الأرقام من تاريخ النشر الأصلي لكل مادة رصدناها وصنّفناها، لا من تاريخ نشرها في المرصد.
      </p>
    </>
  );
}
