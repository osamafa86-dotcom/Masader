import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ApiError, api } from "@/lib/api";
import { arCount, arDate, NOUNS } from "@/lib/format";
import { Ar } from "@/components/Ar";
import { ArticleList } from "@/components/ArticleList";
import { PageHead } from "@/components/PageHead";

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
  const notes = Object.fromEntries(d.items.filter((a) => a.note_ar).map((a) => [a.id, a.note_ar]));
  return (
    <>
      <PageHead
        crumbs={[{ href: "/dossiers", label: "الملفات" }, { label: d.title_ar }]}
        kicker="ملف"
        title={d.title_ar}
        meta={<>{arCount(d.item_count, NOUNS.item)}{d.updated_at && <><span className="sep" aria-hidden="true">·</span>آخر تحديث {arDate(d.updated_at)}</>}</>}
      />
      <section className="narrative" aria-label="مقدّمة المحرّر">
        {d.intro_ar.split(/\n{2,}/).map((p, i) => <p key={i}><Ar text={p} /></p>)}
      </section>
      <div style={{ maxWidth: "var(--main)" }}>
        <div className="sec-head first"><h2>مواد الملف</h2><span className="more muted">بترتيب المحرّر</span></div>
        <ArticleList items={d.items} notes={notes} />
      </div>
    </>
  );
}
