import { editorFetch } from "@/lib/editor";
import { arMonth } from "@/lib/format";
import type { TrendStats } from "@/lib/types";
import { TrendBody } from "@/components/TrendBody";
import { draftTrend, publishTrend, saveTrend } from "../../actions";

export const dynamic = "force-dynamic";
export const metadata = { title: "تقرير الشهر", robots: { index: false } };

export default async function EditorTrend({ params, searchParams }: { params: Promise<{ month: string }>; searchParams: Promise<{ error?: string }> }) {
  const [{ month }, { error }] = await Promise.all([params, searchParams]);
  const s = await editorFetch<TrendStats>(`/api/editor/trends/${month}`);
  const r = s.report;
  return (
    <div>
      <h1 className="page-title">تقرير {arMonth(month)}</h1>
      {error && <p className="notice error">{error}</p>}
      {!s.empty && (
        <section className="narrative">
          {r ? (
            <form action={saveTrend.bind(null, month)}>
              <div className="field">
                <label htmlFor="narrative_ar">القراءة التحليلية {r.narrative_is_draft && <span className="muted">(مقترحة من النموذج: قارنها بالأرقام أدناه ثم احفظ)</span>}</label>
                <textarea id="narrative_ar" name="narrative_ar" rows={10} defaultValue={r.narrative_ar} />
              </div>
              <div className="badges">
                <button className="btn">حفظ القراءة</button>
                <button className="btn secondary" formAction={draftTrend.bind(null, month)}>أعد صياغتها من الأرقام الحالية</button>
                {r.status !== "published" && <button className="btn accent" formAction={publishTrend.bind(null, month)}>نشر التقرير</button>}
                {r.status === "published" && <span className="badge full">منشور</span>}
              </div>
            </form>
          ) : (
            <form action={draftTrend.bind(null, month)}><button className="btn">أعدّ مسودة القراءة من أرقام الشهر</button></form>
          )}
        </section>
      )}
      <TrendBody stats={s} />
    </div>
  );
}
