import Link from "next/link";
import { editorFetch } from "@/lib/editor";
import { deleteTerm, upsertTerm } from "../actions";

export const dynamic = "force-dynamic";
export const metadata = { title: "إدارة المسرد", robots: { index: false } };

type Row = { id: number; term_en: string; term_ar: string; variants_ar: string[]; definition_ar: string; domain: string; status: string; proposal_count: number; example_document_id: number | null };

export default async function EditorGlossary({ searchParams }: { searchParams: Promise<{ status?: string }> }) {
  const status = (await searchParams).status ?? "proposed";
  const rows = await editorFetch<Row[]>(`/api/editor/glossary?status=${status}`);
  return (
    <div>
      <h1 className="page-title">إدارة المسرد</h1>
      <nav className="nav" style={{ margin: "1rem 0 1.5rem" }}>
        <Link href="/editor/glossary?status=proposed" aria-current={status === "proposed" ? "page" : undefined}>مقترحة من النموذج</Link>
        <Link href="/editor/glossary?status=approved" aria-current={status === "approved" ? "page" : undefined}>معتمدة</Link>
      </nav>
      <section className="summary-panel" style={{ maxWidth: 900 }}>
        <h2>إضافة مصطلح أو تعديله</h2>
        <form action={upsertTerm} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "0 1rem" }}>
          <div className="field"><label htmlFor="term_en">المصطلح الإنجليزي</label><input id="term_en" name="term_en" required dir="ltr" /></div>
          <div className="field"><label htmlFor="term_ar">المقابل المعتمد</label><input id="term_ar" name="term_ar" required /></div>
          <div className="field"><label htmlFor="variants_ar">بدائل شائعة</label><input id="variants_ar" name="variants_ar" placeholder="افصل بينها بفاصلة" /></div>
          <div className="field"><label htmlFor="definition_ar">تعريف موجز</label><input id="definition_ar" name="definition_ar" /></div>
          <input type="hidden" name="status" value="approved" />
          <div><button className="btn">اعتماد المصطلح</button></div>
        </form>
      </section>
      {rows.length === 0 ? <p className="empty">لا توجد مصطلحات في هذه القائمة.</p> : (
        <table className="glossary-table">
          <thead><tr><th scope="col">الإنجليزي</th><th scope="col">العربي</th><th scope="col">بدائل</th>{status === "proposed" && <th scope="col">مرات الاقتراح</th>}<th scope="col">إجراء</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="en" dir="ltr">{r.term_en}</td>
                <td><strong>{r.term_ar}</strong></td>
                <td className="muted">{r.variants_ar.join("، ")}</td>
                {status === "proposed" && (
                  <td className="ui">{r.proposal_count}{r.example_document_id && <> <Link href={`/editor/items/${r.example_document_id}`}>مثال</Link></>}</td>
                )}
                <td>
                  <div className="badges">
                    {r.status === "proposed" && (
                      <form action={upsertTerm}>
                        <input type="hidden" name="term_en" value={r.term_en} />
                        <input type="hidden" name="term_ar" value={r.term_ar} />
                        <input type="hidden" name="variants_ar" value={r.variants_ar.join("،")} />
                        <input type="hidden" name="status" value="approved" />
                        <button className="btn secondary">اعتماد</button>
                      </form>
                    )}
                    <form action={deleteTerm}><input type="hidden" name="id" value={r.id} /><button className="btn danger">حذف</button></form>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
