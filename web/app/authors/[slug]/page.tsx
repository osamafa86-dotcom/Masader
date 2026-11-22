import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ApiError, api } from "@/lib/api";
import { arNumber } from "@/lib/format";
import { ArticleList, Pager } from "@/components/ArticleList";
import { PageHead } from "@/components/PageHead";

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
      <PageHead
        kicker="المؤلفون"
        title={<bdi className="latin" dir="ltr" lang="en" style={{ fontWeight: 400 }}>{a.name}</bdi>}
        lede={[a.name_ar, a.affiliation].filter(Boolean).join("، ") || undefined}
        meta={<>المواد المرصودة: {arNumber(a.total)}{a.sources.length > 0 && <><span className="sep" aria-hidden="true">·</span>لدى {a.sources.join("، ")}</>}</>}
      />
      <div style={{ maxWidth: "var(--main)" }}>
        <ArticleList items={a.items} />
        <Pager page={page} total={a.total} perPage={a.per_page} base={`/authors/${slug}`} />
      </div>
    </>
  );
}
