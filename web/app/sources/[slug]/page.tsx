import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiError, api } from "@/lib/api";
import { arCount, NOUNS } from "@/lib/format";
import { KIND, RIGHTS } from "@/lib/labels";
import { ArticleList, Pager } from "@/components/ArticleList";
import { PageHead } from "@/components/PageHead";

export const revalidate = 60;

export default async function SourcePage({ params, searchParams }: { params: Promise<{ slug: string }>; searchParams: Promise<{ page?: string }> }) {
  const [{ slug }, sp] = await Promise.all([params, searchParams]);
  const page = Number(sp.page ?? 1) || 1;
  const sources = await api.sources();
  const src = sources.find((s) => s.slug === slug);
  if (!src) notFound();
  const [list, issues] = await Promise.all([
    api.articles({ source: slug, page }).catch((e) => {
      if (e instanceof ApiError && e.status === 404) notFound();
      throw e;
    }),
    api.issues(slug).catch(() => []),
  ]);
  const rights = RIGHTS[src.rights_level];
  return (
    <>
      <PageHead
        crumbs={[{ href: "/sources", label: "المصادر" }, { label: <bdi>{src.name_ar}</bdi> }]}
        kicker={KIND[src.kind] ?? "مصدر"}
        title={<bdi>{src.name_ar}</bdi>}
        titleEn={src.name}
        lede={src.description_ar || undefined}
        meta={<>{arCount(list.total, NOUNS.item)}<span className="sep" aria-hidden="true">·</span>{rights.letter} · {rights.short}</>}
      />
      <div className="split">
        <section aria-label="المواد">
          {issues.length > 0 && (
            <>
              <h2 className="kicker block-head" style={{ marginBottom: "var(--space-3)" }}>الأعداد</h2>
              <ul className="issues">
                {issues.map((i) => (
                  <li key={`${i.volume}-${i.issue}`}>
                    <Link href={`/sources/${slug}/issues/${i.volume}/${i.issue}`}>المجلد {i.volume}، العدد {i.issue} <span className="count muted">({i.count})</span></Link>
                  </li>
                ))}
              </ul>
              <h2 className="kicker block-head">أحدث المواد</h2>
            </>
          )}
          <ArticleList items={list.items} empty={<><strong>لا مواد منشورة بعد</strong>هذا المصدر قيد الإعداد، وسيظهر هنا ما نرصده منه.</>} />
          <Pager page={page} total={list.total} perPage={list.per_page} base={`/sources/${slug}`} />
        </section>
        <aside className="side-block">
          <h2 className="kicker block-head">عن المصدر</h2>
          <dl className="facts-dl">
            <dt>النوع</dt><dd>{KIND[src.kind] ?? src.kind}</dd>
            <dt>الحقوق</dt><dd>{rights.letter} · {rights.long}</dd>
            {src.license && <><dt>الترخيص</dt><dd><bdi>{src.license}</bdi></dd></>}
            <dt>الحالة</dt><dd>{src.is_active ? "قيد الرصد" : "قيد الإعداد"}</dd>
            <dt>الموقع</dt><dd><a href={src.homepage} rel="noopener" target="_blank" dir="ltr">{src.homepage.replace(/^https?:\/\//, "").replace(/\/$/, "")}</a></dd>
          </dl>
        </aside>
      </div>
    </>
  );
}
