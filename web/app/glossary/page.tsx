import { api } from "@/lib/api";

export const revalidate = 300;
export const metadata = { title: "مسرد المصطلحات" };

export default async function GlossaryPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const q = ((await searchParams).q ?? "").trim();
  const rows = await api.glossary(q || undefined);
  return (
    <div style={{ maxWidth: 900 }}>
      <h1 className="page-title">مسرد المصطلحات</h1>
      <p className="page-lede">
        المقابلات العربية التي نلتزم بها في كل ترجماتنا. يتسع المسرد مع كل مادة يراجعها المحررون،
        ونعتمد الصيغة الأولى ونذكر البدائل الشائعة.
      </p>
      <form action="/glossary" className="search-box" style={{ margin: "1.5rem 0", marginInlineStart: 0 }}>
        <label htmlFor="gq" className="skip-link">ابحث في المسرد</label>
        <input id="gq" name="q" defaultValue={q} placeholder="مصطلح عربي أو إنجليزي" />
        <button type="submit">بحث في المسرد</button>
      </form>
      {rows.length === 0 ? <p className="empty">لا يوجد مصطلح مطابق.</p> : (
        <table className="glossary-table">
          <thead><tr><th scope="col">المصطلح المعتمد</th><th scope="col">بدائل شائعة</th><th scope="col">الأصل الإنجليزي</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.en}>
                <td><strong>{r.ar}</strong>{r.definition_ar && <div className="muted">{r.definition_ar}</div>}</td>
                <td className="muted">{r.variants_ar.join("، ")}</td>
                <td className="en" lang="en" dir="ltr">{r.en}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
