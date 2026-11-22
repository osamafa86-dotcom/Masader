import Link from "next/link";
import type { TrendRow, TrendStats } from "@/lib/types";
import { arCount, arNumber, NOUNS } from "@/lib/format";
import { BarChart } from "./BarChart";

const bars = (rows: TrendRow[], hrefBase?: string, limit = 12) =>
  rows.filter((r) => r.count > 0).slice(0, limit).map((r) => ({
    key: r.slug, label: r.name_ar, value: r.count, previous: r.previous, href: hrefBase ? `${hrefBase}/${r.slug}` : undefined,
  }));

function change(n: number) {
  // Isolated left-to-right so the sign stays in front of the number in Arabic text.
  return <bdi dir="ltr">{n > 0 ? `+${n}` : `${n}`}</bdi>;
}

function Moves({ title, rows }: { title: string; rows: TrendRow[] }) {
  return (
    <section>
      <h2 className="kicker block-head">{title}</h2>
      <ul className="index-list">
        {rows.map((r) => (
          <li key={r.slug}>
            <Link href={`/topics/${r.slug}`}>{r.name_ar}</Link>
            <span className="count">{arCount(r.count, NOUNS.item)} · متوسط الأشهر الثلاثة {r.avg_3m}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function TrendBody({ stats }: { stats: TrendStats }) {
  if (stats.empty) {
    return <p className="empty"><strong>لا اتجاهات لهذا الشهر</strong>لم نرصد مواد منشورة في هذا الشهر، فلا توجد اتجاهات نعرضها.</p>;
  }
  const max = Math.max(...stats.topics.map((t) => t.count), ...stats.regions.map((t) => t.count), 1);
  return (
    <>
      <div className="stat-line">
        <div><strong>{arNumber(stats.total)}</strong><span>مادة رُصدت هذا الشهر</span></div>
        <div><strong>{change(stats.total - stats.previous_total)}</strong><span>عن الشهر السابق ({arNumber(stats.previous_total)})</span></div>
        <div><strong>{stats.sources.filter((s) => s.count > 0).length}</strong><span>المصادر النشطة</span></div>
      </div>
      {stats.small_sample && <p className="notice">عدد المواد قليل هذا الشهر، فلا تكفي الأرقام لاستنتاج اتجاه.</p>}

      {(stats.rising_topics.length > 0 || stats.falling_topics.length > 0) && (
        <div className="trend-grid" style={{ marginBottom: "var(--space-8)" }}>
          {stats.rising_topics.length > 0 && <Moves title="موضوعات صاعدة" rows={stats.rising_topics} />}
          {stats.falling_topics.length > 0 && <Moves title="موضوعات متراجعة" rows={stats.falling_topics} />}
        </div>
      )}

      <div className="trend-grid">
        <BarChart title="المواد بحسب الموضوع" bars={bars(stats.topics, "/topics")} max={max} />
        <BarChart title="المواد بحسب المنطقة" bars={bars(stats.regions, "/regions")} max={max} />
        <BarChart title="أكثر المصادر نشاطاً" bars={bars(stats.sources, "/sources", 10)} />
        <BarChart title="التوزّع على أسابيع الشهر" unit="مادة"
                  bars={stats.weeks.map((w) => ({ key: String(w.week), label: `الأسبوع ${w.week}`, value: w.count }))} />
      </div>

      {stats.rising_keywords.length > 0 && (
        <section style={{ marginTop: "var(--space-6)" }}>
          <h2 className="kicker block-head" style={{ marginBottom: "var(--space-3)" }}>كلمات مفتاحية متكرّرة</h2>
          <ul className="issues">{stats.rising_keywords.map((k) => (
            <li key={k.keyword}><Link href={`/search?q=${encodeURIComponent(k.keyword)}`}><bdi dir="auto">{k.keyword}</bdi> <span className="muted">({k.count})</span></Link></li>
          ))}</ul>
        </section>
      )}
      {stats.top_items.length > 0 && (
        <section style={{ maxWidth: "var(--main)" }}>
          <h2 className="kicker block-head">أهم مواد الشهر</h2>
          <ol className="ranked">
            {stats.top_items.map((t, i) => (
              <li key={t.id}>
                <span className="rank" aria-hidden="true">{i + 1}</span>
                <span><Link href={`/articles/${t.id}`}>{t.title_ar}</Link><span className="src"><bdi>{t.source}</bdi></span></span>
              </li>
            ))}
          </ol>
        </section>
      )}
      <p className="ui muted" style={{ marginTop: "var(--space-6)" }}>
        تُحسب الأرقام من تاريخ النشر الأصلي لكل مادة رصدناها وصنّفناها، لا من تاريخ نشرها في المرصد.
      </p>
    </>
  );
}
