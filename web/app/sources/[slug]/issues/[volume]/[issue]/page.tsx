import { notFound } from "next/navigation";
import { ApiError, api } from "@/lib/api";
import { arCount, NOUNS } from "@/lib/format";
import { ArticleList } from "@/components/ArticleList";
import { PageHead } from "@/components/PageHead";

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
      <PageHead
        crumbs={[{ href: "/sources", label: "المصادر" }, { href: `/sources/${slug}`, label: <bdi>{src.name_ar}</bdi> }, { label: `المجلد ${volume}، العدد ${issue}` }]}
        kicker="فهرس العدد"
        title={`المجلد ${volume}، العدد ${issue}`}
        lede="فهرس العدد مترجماً، مرتباً بحسب الصفحات. لكل دراسة ملخص عربي مبني على ملخصها المنشور، ورابط إلى نصها لدى الناشر."
        meta={arCount(toc.items.length, NOUNS.item)}
      />
      <div style={{ maxWidth: "var(--main)" }}><ArticleList items={toc.items} /></div>
    </>
  );
}
