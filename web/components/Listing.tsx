import { notFound } from "next/navigation";
import { api, type ArticleFilters } from "@/lib/api";
import { ArticleList, Pager } from "@/components/ArticleList";

export async function TaxonomyListing({ kind, slug, page }: { kind: "topic" | "region"; slug: string; page: number }) {
  const topics = await api.topics();
  const term = topics[kind].find((t) => t.slug === slug);
  if (!term) notFound();
  const filters: ArticleFilters = { [kind]: slug, page };
  const list = await api.articles(filters);
  return (
    <>
      <h1 className="page-title">{term.name_ar}</h1>
      <p className="page-lede"><bdi className="latin">{term.name_en}</bdi>. {list.total} مادة منشورة.</p>
      <ArticleList items={list.items} />
      <Pager page={page} total={list.total} perPage={list.per_page} base={`/${kind === "topic" ? "topics" : "regions"}/${slug}`} />
    </>
  );
}
