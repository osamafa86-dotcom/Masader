import Link from "next/link";
import { api } from "@/lib/api";
import { arCount, arDate, NOUNS } from "@/lib/format";
import { PageHead } from "@/components/PageHead";

export const dynamic = "force-dynamic";
export const metadata = { title: "الملفات الموضوعية" };

export default async function DossiersPage() {
  const rows = await api.dossiers();
  return (
    <>
      <PageHead kicker="القراءة المركّزة" title="الملفات"
        lede="يجمع المحرّرون في كل ملف أهم ما رُصد حول سؤال واحد من مصادر مختلفة، بترتيب زمني ومقدّمة تربط بين المواد وملاحظة على كل منها."
        meta={arCount(rows.length, NOUNS.dossier)} />
      {rows.length === 0 ? <p className="empty"><strong>لا ملفات منشورة بعد</strong>يُنشر الملف حين يكتمل ويراجع المحرّر مقدّمته.</p> : (
        <ol className="dossier-cards" style={{ maxWidth: "var(--main)" }}>
          {rows.map((d) => (
            <li key={d.slug}>
              <div className="entry-margin">
                <span className="entry-source">{arCount(d.item_count, NOUNS.item)}</span>
                {d.updated_at && <span>حُدِّث في {arDate(d.updated_at)}</span>}
              </div>
              <article>
                <h2><Link href={`/dossiers/${d.slug}`}>{d.title_ar}</Link></h2>
                <p>{d.excerpt_ar}{d.excerpt_ar.length >= 280 ? "…" : ""}</p>
              </article>
            </li>
          ))}
        </ol>
      )}
    </>
  );
}
