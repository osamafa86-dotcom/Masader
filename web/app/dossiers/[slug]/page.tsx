import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ApiError, api } from "@/lib/api";
import { arDate } from "@/lib/format";
import { Ar } from "@/components/Ar";
import { Badges } from "@/components/ArticleList";
import Link from "next/link";

export const revalidate = 60;

async function load(slug: string) {
  try {
    return await api.dossier(slug);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const d = await load((await params).slug);
  return { title: d.title_ar, description: d.excerpt_ar };
}

export default async function DossierPage({ params }: { params: Promise<{ slug: string }> }) {
  const d = await load((await params).slug);
  return (
    <article>
      <header className="article-head">
        <div className="ui"><Link href="/dossiers">الملفات الموضوعية</Link></div>
        <h1>{d.title_ar}</h1>
        <div className="byline"><span>{d.item_count} مواد</span>{d.updated_at && <span>آخر تحديث {arDate(d.updated_at)}</span>}</div>
      </header>
      <section className="narrative">
        {d.intro_ar.split(/\n{2,}/).map((p, i) => <p key={i}><Ar text={p} /></p>)}
      </section>
      <ol className="entries" style={{ maxWidth: 860 }}>
        {d.items.map((a, i) => (
          <li key={a.id} className="entry">
            <span className="num ui muted" style={{ paddingTop: "0.3rem" }}>[{i + 1}]</span>
            <article>
              <div className="from">{a.source.name_ar}{a.original_published_at && <>، {arDate(a.original_published_at)}</>}</div>
              <h2><Link href={`/articles/${a.id}`}>{a.title_ar}</Link></h2>
              {a.dek_ar && <p className="dek"><Ar text={a.dek_ar} /></p>}
              {a.note_ar && <p className="notice" style={{ margin: "0.5rem 0" }}>ملاحظة المحرر: {a.note_ar}</p>}
              <Badges a={a} />
            </article>
          </li>
        ))}
      </ol>
    </article>
  );
}
