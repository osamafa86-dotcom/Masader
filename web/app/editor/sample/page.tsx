import Link from "next/link";
import { editorFetch } from "@/lib/editor";
import type { QueueRow } from "@/lib/types";
import { markSample } from "../actions";

export const dynamic = "force-dynamic";
export const metadata = { title: "عينة الأسبوع", robots: { index: false } };

export default async function Sample() {
  const rows = await editorFetch<QueueRow[]>("/api/editor/sample");
  return (
    <div className="prose" style={{ maxWidth: 900 }}>
      <h1 className="page-title">عينة الأسبوع</h1>
      <p className="page-lede">
        عُشر المواد التي نُشرت هذا الأسبوع دون مراجعة بشرية، مختارة عشوائياً. افتح كل مادة، صحّح ما يلزم، ثم سجّل النتيجة.
        نسبة المواد التي تحتاج تعديلاً هي المؤشر على صلاحية النشر الآلي.
      </p>
      {rows.length === 0 ? <p className="empty">لا مواد في عينة هذا الأسبوع، أو فُحصت كلها.</p> : (
        <ol className="entries">{rows.map((r) => (
          <li key={r.id} className="entry" style={{ gridTemplateColumns: "1fr" }}>
            <div>
              <h2><Link href={`/editor/items/${r.id}`}>{r.title_ar ?? r.title_en}</Link></h2>
              <p className="from">{r.source.name_ar}، الفحص الآلي {r.qa_score ?? "-"}/100</p>
              <div className="badges">
                <form action={markSample.bind(null, r.id, "ok")}><button className="btn secondary">سليمة</button></form>
                <form action={markSample.bind(null, r.id, "fixed")}><button className="btn secondary">احتاجت تعديلاً وعدّلتها</button></form>
              </div>
            </div>
          </li>
        ))}</ol>
      )}
    </div>
  );
}
