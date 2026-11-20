import Link from "next/link";
import { api } from "@/lib/api";
import { arDate } from "@/lib/format";

export const revalidate = 60;
export const metadata = { title: "الملفات الموضوعية" };

export default async function DossiersPage() {
  const rows = await api.dossiers();
  return (
    <div className="prose" style={{ maxWidth: 860 }}>
      <h1 className="page-title">الملفات الموضوعية</h1>
      <p className="page-lede">يجمع المحررون في كل ملف أهم ما رُصد حول قضية واحدة، مع مقدمة تربط بين المواد وملاحظة على كل منها.</p>
      {rows.length === 0 ? <p className="empty">لا توجد ملفات منشورة بعد.</p> : (
        <ol className="entries">
          {rows.map((d) => (
            <li key={d.slug} className="entry" style={{ gridTemplateColumns: "1fr" }}>
              <article>
                <div className="from">{d.item_count} مواد{d.updated_at && <>، حُدّث في {arDate(d.updated_at)}</>}</div>
                <h2><Link href={`/dossiers/${d.slug}`}>{d.title_ar}</Link></h2>
                <p className="dek">{d.excerpt_ar}{d.excerpt_ar.length >= 280 ? "…" : ""}</p>
              </article>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
