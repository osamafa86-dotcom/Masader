import Link from "next/link";
import { api } from "@/lib/api";
import { ArticleList, Pager } from "@/components/ArticleList";

export const revalidate = 60;

export default async function Home({ searchParams }: { searchParams: Promise<{ page?: string }> }) {
  const page = Number((await searchParams).page ?? 1) || 1;
  const [articles, topics, sources] = await Promise.all([api.articles({ page }), api.topics(), api.sources()]);
  const active = sources.filter((s) => s.is_active);
  return (
    <div className="with-rail">
      <section aria-labelledby="latest">
        <h1 id="latest" className="page-title">آخر ما رُصد</h1>
        <p className="page-lede">
          ملخصات تحليلية وترجمات عربية لأحدث ما تنشره مراكز الفكر والمجلات المحكّمة في الدراسات الاستراتيجية والأمنية.
          يُرتَّب الأحدث أولاً، ويشير المؤشر بجانب كل مادة إلى أهميتها للباحث المتخصص.
        </p>
        <ArticleList items={articles.items} lead={page === 1} />
        <Pager page={page} total={articles.total} perPage={articles.per_page} base="/" />
      </section>
      <aside className="rail">
        <section className="subscribe-cta">
          <p>مختارات أسبوعية يراجعها المحررون، بحسب الموضوعات التي تختارها.</p>
          <Link className="btn accent" href="/subscribe">اشترك في النشرة</Link>
        </section>
        <section>
          <h2>المصادر المرصودة</h2>
          <ul>
            {active.map((s) => (
              <li key={s.slug}>
                <span>
                  <span className={`status-dot${s.published_count ? "" : " idle"}`} aria-hidden="true" />
                  <Link href={`/sources/${s.slug}`}>{s.name_ar}</Link>
                </span>
                <span className="count">{s.published_count}</span>
              </li>
            ))}
          </ul>
          <p className="ui muted" style={{ marginTop: "0.6rem" }}>
            {sources.length - active.length} مصدراً إضافياً قيد الإعداد. <Link href="/sources">كل المصادر</Link>
          </p>
        </section>
        <section>
          <h2>الموضوعات</h2>
          <ul>
            {topics.topic.filter((t) => t.count > 0).map((t) => (
              <li key={t.slug}><Link href={`/topics/${t.slug}`}>{t.name_ar}</Link><span className="count">{t.count}</span></li>
            ))}
          </ul>
        </section>
        <section>
          <h2>المناطق</h2>
          <ul>
            {topics.region.filter((t) => t.count > 0).map((t) => (
              <li key={t.slug}><Link href={`/regions/${t.slug}`}>{t.name_ar}</Link><span className="count">{t.count}</span></li>
            ))}
          </ul>
        </section>
      </aside>
    </div>
  );
}
