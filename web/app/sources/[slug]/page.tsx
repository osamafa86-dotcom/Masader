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
  const list = await api.articles({ source: slug, page }).catch((e) => {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  });
  return (
    <>
      <h1 className="page-title">{src.name_ar}</h1>
      <p className="page-lede">
        <bdi className="latin">{src.name}</bdi>. {src.description_ar}{" "}
        <a href={src.homepage} rel="noopener" target="_blank">موقع المصدر</a>
      </p>
      <ArticleList items={list.items} />
      <Pager page={page} total={list.total} perPage={list.per_page} base={`/sources/${slug}`} />
    </>
  );
}
