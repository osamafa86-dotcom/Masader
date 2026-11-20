import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiError, api } from "@/lib/api";
import { ArticleList, Pager } from "@/components/ArticleList";

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
  return (
    <>
      <h1 className="page-title">{src.name_ar}</h1>
      <p className="page-lede">
        <bdi className="latin">{src.name}</bdi>. {src.description_ar}{" "}
        <a href={src.homepage} rel="noopener" target="_blank">موقع المصدر</a>
      </p>
      {issues.length > 0 && (
        <section aria-labelledby="issues-title">
          <h2 id="issues-title" style={{ fontSize: "var(--s1)" }}>الأعداد</h2>
          <ul className="issues">
            {issues.map((i) => (
              <li key={`${i.volume}-${i.issue}`}>
                <Link href={`/sources/${slug}/issues/${i.volume}/${i.issue}`}>المجلد {i.volume}، العدد {i.issue} <span className="count">({i.count})</span></Link>
              </li>
            ))}
          </ul>
          <h2 style={{ fontSize: "var(--s1)" }}>أحدث المواد</h2>
        </section>
      )}
      <ArticleList items={list.items} />
      <Pager page={page} total={list.total} perPage={list.per_page} base={`/sources/${slug}`} />
    </>
  );
}
