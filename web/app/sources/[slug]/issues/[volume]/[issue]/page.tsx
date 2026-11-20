import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiError, api } from "@/lib/api";
import { ArticleList } from "@/components/ArticleList";

export const revalidate = 60;

export default async function IssuePage({ params }: { params: Promise<{ slug: string; volume: string; issue: string }> }) {
  const { slug, volume, issue } = await params;
  const [sources, toc] = await Promise.all([
    api.sources(),
    api.issue(slug, volume, issue).catch((e) => {
      if (e instanceof ApiError && e.status === 404) notFound();
      throw e;
    }),
  ]);
  const src = sources.find((s) => s.slug === slug);
  if (!src) notFound();
  return (
    <>
      <div className="ui"><Link href={`/sources/${slug}`}>{src.name_ar}</Link></div>
      <h1 className="page-title">المجلد {volume}، العدد {issue}</h1>
      <p className="page-lede">
        فهرس العدد مترجماً، مرتباً بحسب الصفحات. لكل دراسة ملخص عربي مبني على ملخصها المنشور، ورابط إلى نصها لدى الناشر.
      </p>
      <ArticleList items={toc.items} />
    </>
  );
}
