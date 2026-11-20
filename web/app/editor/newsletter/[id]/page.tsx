import Link from "next/link";
import { editorFetch } from "@/lib/editor";
import type { DigestRow } from "@/lib/types";
import { saveDigest, sendDigest } from "../../actions";

export const dynamic = "force-dynamic";
export const metadata = { title: "مراجعة النشرة", robots: { index: false } };

export default async function DigestPage({ params }: { params: Promise<{ id: string }> }) {
  const id = Number((await params).id);
  const d = await editorFetch<DigestRow>(`/api/editor/digests/${id}`);
  const draft = d.status === "draft";
  return (
    <div style={{ maxWidth: 900 }}>
      <p className="ui"><Link href="/editor/newsletter">كل النشرات</Link></p>
      <h1 className="page-title">{draft ? "مراجعة مسودة النشرة" : d.subject_ar}</h1>
      <form action={saveDigest.bind(null, id)}>
        <div className="field"><label htmlFor="subject_ar">عنوان الرسالة</label><input id="subject_ar" name="subject_ar" defaultValue={d.subject_ar} disabled={!draft} /></div>
        <div className="field"><label htmlFor="intro_ar">مقدمة المحرر</label><textarea id="intro_ar" name="intro_ar" rows={4} defaultValue={d.intro_ar} disabled={!draft} /></div>
        <fieldset>
          <legend>المواد ({d.items?.length ?? 0})، أزل علامة ما لا تريد إرساله</legend>
          {(d.items ?? []).map((it) => (
            <label key={it.id} className="ui" style={{ display: "flex", gap: "0.5rem", padding: "0.4rem 0", borderBottom: "1px solid var(--rule)" }}>
              <input type="checkbox" name="document_ids" value={it.id} defaultChecked disabled={!draft} />
              <span><strong>{it.title_ar}</strong> <span className="muted">، {it.source.name_ar}، الأهمية {it.importance ?? "-"}</span></span>
            </label>
          ))}
        </fieldset>
        {draft && <button className="btn secondary">حفظ التعديلات</button>}
      </form>
      {draft && (
        <form action={sendDigest.bind(null, id)} style={{ marginTop: "1.5rem" }}>
          <p className="notice">يصل كل مشترك ما يطابق اختياراته فقط، ولا يُرسل شيء لمن لا تطابقه أي مادة. احفظ تعديلاتك قبل الإرسال.</p>
          <button className="btn accent">أرسل النشرة</button>
        </form>
      )}
    </div>
  );
}
