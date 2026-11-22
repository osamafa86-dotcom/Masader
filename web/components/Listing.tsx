import Link from "next/link";
import { notFound } from "next/navigation";
import { api, type ArticleFilters } from "@/lib/api";
import { arCount, NOUNS } from "@/lib/format";
import { ArticleList, Pager } from "@/components/ArticleList";
import { PageHead } from "@/components/PageHead";

/** A topic or region page: its items newest first, with the neighbouring terms beside them. */
export async function TaxonomyListing({ kind, slug, page }: { kind: "topic" | "region"; slug: string; page: number }) {
  const topics = await api.topics();
  const terms = topics[kind];
  const term = terms.find((t) => t.slug === slug);
  if (!term) notFound();
  const filters: ArticleFilters = { [kind]: slug, page };
  const list = await api.articles(filters);
  const base = kind === "topic" ? "/topics" : "/regions";
  const others = terms.filter((t) => t.slug !== slug && t.count > 0);
  return (
    <>
      <PageHead
        crumbs={[{ href: "/topics", label: kind === "topic" ? "الموضوعات" : "المناطق" }, { label: term.name_ar }]}
        kicker={kind === "topic" ? "موضوع" : "منطقة"}
        title={term.name_ar}
        titleEn={term.name_en}
        meta={arCount(list.total, NOUNS.item)}
      />
      <div className="split">
        <section aria-label="المواد">
          <ArticleList items={list.items} empty={<><strong>لا مواد هنا بعد</strong>سنعرض هنا ما نرصده في {term.name_ar} حين يُنشر.</>} />
          <Pager page={page} total={list.total} perPage={list.per_page} base={`${base}/${slug}`} />
        </section>
        {others.length > 0 && (
          <aside className="side-block">
            <h2 className="kicker block-head">{kind === "topic" ? "موضوعات أخرى" : "مناطق أخرى"}</h2>
            <ul className="index-list">
              {others.map((t) => <li key={t.slug}><Link href={`${base}/${t.slug}`}>{t.name_ar}</Link><span className="count">{t.count}</span></li>)}
            </ul>
          </aside>
        )}
      </div>
    </>
  );
}
