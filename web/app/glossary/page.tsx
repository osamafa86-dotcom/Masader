import { api } from "@/lib/api";
import { arCount, NOUNS } from "@/lib/format";
import { PageHead } from "@/components/PageHead";

export const revalidate = 300;
export const metadata = { title: "مسرد المصطلحات" };

export default async function GlossaryPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const q = ((await searchParams).q ?? "").trim();
  const rows = await api.glossary(q || undefined);
  return (
    <>
      <PageHead kicker="المصطلحات" title="مسرد المصطلحات الاستراتيجية"
        lede="المقابل العربي المعتمد في كل ترجماتنا، وما يشيع في الكتابات العربية بديلاً له. يتّسع المسرد مع كل مادة يراجعها المحرّرون."
        meta={q ? `«${q}»: ${arCount(rows.length, NOUNS.term)}` : arCount(rows.length, NOUNS.term)} />
      <form action="/glossary" className="inline-form" style={{ maxWidth: 640, marginBottom: "var(--space-6)" }}>
        <label htmlFor="gq" className="sr-only">ابحث في المسرد</label>
        <input id="gq" name="q" defaultValue={q} placeholder="مصطلح عربي أو إنجليزي" />
        <button type="submit" className="btn secondary">ابحث في المسرد</button>
      </form>
      {rows.length === 0 ? <p className="empty"><strong>لا يوجد مصطلح مطابق</strong>جرّب الصيغة الإنجليزية، أو اكتب جزءاً من الكلمة.</p> : (
        <table className="glossary-table">
          <thead><tr><th scope="col">المصطلح المعتمد</th><th scope="col">التعريف</th><th scope="col">بدائل شائعة</th><th scope="col">الأصل الإنجليزي</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.en}>
                <td style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "1.1875rem", whiteSpace: "nowrap" }}>{r.ar}</td>
                <td className={r.definition_ar ? undefined : "nil"} style={{ color: "var(--text-secondary)" }}>{r.definition_ar || "—"}</td>
                <td className={`ui muted${r.variants_ar.length ? "" : " nil"}`}>{r.variants_ar.join("، ") || "—"}</td>
                <td className="en" lang="en" dir="ltr">{r.en}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
