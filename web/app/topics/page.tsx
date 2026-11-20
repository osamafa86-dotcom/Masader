import Link from "next/link";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";
export const metadata = { title: "الموضوعات والمناطق" };

export default async function TopicsPage() {
  const t = await api.topics();
  return (
    <div className="with-rail">
      <section className="rail">
        <h1 className="page-title">الموضوعات</h1>
        <p className="page-lede">يُصنَّف كل ما نرصده آلياً في موضوع إلى ثلاثة موضوعات، ثم يراجع المحرر التصنيف.</p>
        <section>
          <ul>
            {t.topic.map((x) => (
              <li key={x.slug}><Link href={`/topics/${x.slug}`}>{x.name_ar}</Link><span className="count">{x.count}</span></li>
            ))}
          </ul>
        </section>
      </section>
      <aside className="rail">
        <section>
          <h2>المناطق</h2>
          <ul>
            {t.region.map((x) => (
              <li key={x.slug}><Link href={`/regions/${x.slug}`}>{x.name_ar}</Link><span className="count">{x.count}</span></li>
            ))}
          </ul>
        </section>
      </aside>
    </div>
  );
}
