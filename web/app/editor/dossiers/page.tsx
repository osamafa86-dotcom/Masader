import Link from "next/link";
import { editorFetch } from "@/lib/editor";
import { arDate } from "@/lib/format";
import { createDossier } from "../actions";

export const dynamic = "force-dynamic";
export const metadata = { title: "الملفات الموضوعية", robots: { index: false } };

type Row = { id: number; slug: string; title_ar: string; item_count: number; status: string; updated_at: string | null };

export default async function EditorDossiers() {
  const rows = await editorFetch<Row[]>("/api/editor/dossiers");
  return (
    <div style={{ maxWidth: 900 }}>
      <h1 className="page-title">الملفات الموضوعية</h1>
      <form action={createDossier} className="search-box" style={{ margin: "1rem 0 2rem", marginInlineStart: 0 }}>
        <label htmlFor="title_ar" className="skip-link">عنوان الملف</label>
        <input id="title_ar" name="title_ar" required minLength={3} placeholder="عنوان ملف جديد" style={{ width: "22rem" }} />
        <button type="submit">أنشئ الملف</button>
      </form>
      {rows.length === 0 ? <p className="empty">لا توجد ملفات بعد.</p> : (
        <table className="glossary-table">
          <thead><tr><th scope="col">الملف</th><th scope="col">المواد</th><th scope="col">الحالة</th><th scope="col">آخر تعديل</th></tr></thead>
          <tbody>{rows.map((d) => (
            <tr key={d.id}>
              <td><Link href={`/editor/dossiers/${d.id}`}>{d.title_ar}</Link></td>
              <td className="ui">{d.item_count}</td>
              <td className="ui">{d.status === "published" ? "منشور" : "مسودة"}</td>
              <td className="ui muted">{arDate(d.updated_at)}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </div>
  );
}
