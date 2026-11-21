import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ApiError, api } from "@/lib/api";
import { ArticleList, Pager } from "@/components/ArticleList";

export const revalidate = 60;

async function load(slug: string, page: number) {
  try {
    return await api.author(slug, page);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const a = await load((await params).slug, 1);
  return { title: a.name, description: `أعمال ${a.name} المترجمة والملخصة بالعربية` };
}

export default async function AuthorPage({ params, searchParams }: { params: Promise<{ slug: string }>; searchParams: Promise<{ page?: string }> }) {
  const [{ slug }, sp] = await Promise.all([params, searchParams]);
  const page = Number(sp.page ?? 1) || 1;
  const a = await load(slug, page);
  return (
    <>
      <h1 className="page-title"><bdi dir="ltr" lang="en">{a.name}</bdi></h1>
      <p className="page-lede">
        {a.total} مادة رصدناها لهذا الكاتب{a.sources.length > 0 && <>، منشورة لدى {a.sources.join("، ")}</>}.
      </p>
      <ArticleList items={a.items} />
      <Pager page={page} total={a.total} perPage={a.per_page} base={`/authors/${slug}`} />
    </>
  );
}
