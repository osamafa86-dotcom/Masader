import Link from "next/link";
import { editorFetch } from "@/lib/editor";
import type { QueueRow, Stats } from "@/lib/types";
import { arDate } from "@/lib/format";
import { logout } from "./actions";

export const dynamic = "force-dynamic";
export const metadata = { title: "غرفة التحرير", robots: { index: false } };

const TABS: [string, string][] = [
  ["review", "بانتظار المراجعة"], ["processing", "قيد المعالجة"], ["failed", "متعثرة"], ["published", "منشورة"], ["rejected", "مرفوضة"],
];
const STAGE_COUNT: Record<string, string[]> = {
  review: ["review"], processing: ["discovered", "extracted", "classified", "summarized", "translated"],
  failed: ["failed"], published: ["published"], rejected: ["rejected"],
};

export default async function EditorHome({ searchParams }: { searchParams: Promise<{ stage?: string }> }) {
  const stage = (await searchParams).stage ?? "review";
  const [stats, queue] = await Promise.all([
    editorFetch<Stats>("/api/editor/stats"),
    editorFetch<{ items: QueueRow[]; total: number }>(`/api/editor/queue?stage=${encodeURIComponent(stage)}`),
  ]);
  const budgetPct = Math.min(100, Math.round((stats.spent_today_usd / stats.daily_budget_usd) * 100));
  const failing = stats.sources.filter((s) => s.last_error);
  return (
    <div className="with-rail">
      <section>
        {stats.worker.stale && (
          <p className="notice error" role="alert">
            {stats.worker.last_seen ? `توقف العامل عن العمل منذ ${arDate(stats.worker.last_seen)}: لا رصد ولا ترجمة الآن.` : "لم يبدأ العامل بعد: لا رصد ولا ترجمة حتى يعمل."}
          </p>
        )}
        {stats.problems.filter((p) => !p.startsWith("آخر دورة للعامل")).map((p, i) => <p key={i} className="notice">{p}</p>)}
        <h1 className="page-title">{TABS.find(([k]) => k === stage)?.[1] ?? "صف المراجعة"}</h1>
        <nav className="nav" aria-label="المراحل" style={{ margin: "1rem 0 1.5rem" }}>
          {TABS.map(([k, label]) => (
            <Link key={k} href={`/editor?stage=${k}`} aria-current={k === stage ? "page" : undefined}>
              {label} <span className="count">({STAGE_COUNT[k].reduce((n, s) => n + (stats.stages[s] ?? 0), 0)})</span>
            </Link>
          ))}
        </nav>
        {queue.items.length === 0 ? (
          <p className="empty">{stage === "review" ? "لا شيء بانتظار المراجعة الآن. تصل المواد الجديدة تلقائياً بعد كل دورة رصد." : "لا توجد مواد في هذه المرحلة."}</p>
        ) : (
          <table className="glossary-table">
            <thead>
              <tr><th scope="col">المادة</th><th scope="col">الأهمية</th><th scope="col">المستوى</th><th scope="col">الفحص الآلي</th><th scope="col">رُصدت</th></tr>
            </thead>
            <tbody>
              {queue.items.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link href={`/editor/items/${r.id}`}><strong>{r.title_ar ?? r.title_en}</strong></Link>
                    <div className="ui muted">{r.source.name_ar}</div>
                    {r.error && <div className="ui" style={{ color: "var(--bad)" }}>{r.error}</div>}
                  </td>
                  <td className="ui">{r.importance ?? "-"}</td>
                  <td className="ui">{r.max_level === "full" ? "نص كامل" : "ملخص"}</td>
                  <td className="ui">
                    {r.qa_score === null ? "-" : `${r.qa_score}/100`}
                    {r.qa_high > 0 && <div style={{ color: "var(--bad)" }}>{r.qa_high} مشكلة جسيمة</div>}
                    {r.notes > 0 && <div className="muted">{r.notes} ملاحظة من المترجم</div>}
                  </td>
                  <td className="ui muted">{arDate(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <aside className="rail">
        <section>
          <h2>ميزانية اليوم</h2>
          <p className="ui">أُنفق ${stats.spent_today_usd.toFixed(2)} من ${stats.daily_budget_usd.toFixed(2)} ({budgetPct}%).</p>
          {budgetPct >= 100 && <p className="notice error">بلغت الميزانية حدها، فتوقفت الترجمة حتى الغد.</p>}
        </section>
        <section>
          <h2>بانتظار قرارك</h2>
          <ul>
            <li><Link href="/editor/feedback">بلاغات القرّاء</Link><span className="count">{stats.open_feedback}</span></li>
            <li><Link href="/editor/glossary?status=proposed">مصطلحات مقترحة</Link><span className="count">{stats.proposed_terms}</span></li>
          </ul>
        </section>
        <section>
          <h2>صحة المصادر</h2>
          <p className="ui muted">
            {failing.length > 0 ? `${failing.length} مصدر تعذّر رصده في آخر محاولة. مرّر المؤشر فوق المصدر لعرض الخطأ.`
              : stats.sources.some((s) => s.last_success_at) ? "نجحت آخر محاولة رصد لكل المصادر النشطة."
              : "لم تبدأ دورة الرصد بعد. شغّل العامل ليبدأ رصد المصادر."}
          </p>
          <ul>
            {stats.sources.map((s) => (
              <li key={s.slug} title={s.last_error ?? undefined}>
                <span><span className={`status-dot${s.last_error ? "" : s.last_success_at ? "" : " idle"}`} style={s.last_error ? { background: "var(--bad)" } : undefined} aria-hidden="true" />{s.name_ar}</span>
                <span className="count">{s.last_error ? "خطأ" : s.last_success_at ? arDate(s.last_success_at) : "لم يُرصد"}</span>
              </li>
            ))}
          </ul>
        </section>
        <form action={logout}><button className="btn secondary">تسجيل الخروج</button></form>
      </aside>
    </div>
  );
}
