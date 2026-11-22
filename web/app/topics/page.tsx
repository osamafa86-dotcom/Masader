import Link from "next/link";
import { api } from "@/lib/api";
import type { TopicRow } from "@/lib/types";
import { PageHead } from "@/components/PageHead";

export const dynamic = "force-dynamic";
export const metadata = { title: "الموضوعات والمناطق" };

function Column({ id, title, rows, base }: { id: string; title: string; rows: TopicRow[]; base?: string }) {
  return (
    <section aria-labelledby={id} id={id === "ix-regions" ? "regions" : undefined}>
      <h2 id={id} className="kicker block-head">{title}</h2>
      <ul className="index-list">
        {rows.map((x) => (
          <li key={x.slug}>
            {base && x.count > 0 ? <Link href={`${base}/${x.slug}`}>{x.name_ar}</Link> : <span>{x.name_ar}</span>}
            <bdi className="latin muted" lang="en" style={{ fontSize: "0.8125rem" }}>{x.name_en}</bdi>
            <span className="count">{x.count}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default async function TopicsPage() {
  const t = await api.topics();
  return (
    <>
      <PageHead kicker="الفهرس" title="الموضوعات والمناطق"
        lede="يُصنَّف كل ما نرصده آلياً في موضوع أو أكثر وفي منطقة، ثم يراجع المحرّر التصنيف. الرقم بجانب كل بند عدد المواد المنشورة فيه." />
      <div className="index-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", marginTop: 0 }}>
        <Column id="ix-topics" title="الموضوعات" rows={t.topic} base="/topics" />
        <Column id="ix-regions" title="المناطق" rows={t.region} base="/regions" />
        {t.doc_type.length > 0 && <Column id="ix-types" title="أنواع المواد" rows={t.doc_type} />}
      </div>
    </>
  );
}
