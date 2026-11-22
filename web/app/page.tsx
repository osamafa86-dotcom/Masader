import Link from "next/link";
import { api } from "@/lib/api";
import type { ArticleCard, TrendStats } from "@/lib/types";
import { arCount, arDate, arDayMonth, arMonth, arNumber, arWeekdayDate, NOUNS } from "@/lib/format";
import { ArticleList, Badges, Gauge, Pager } from "@/components/ArticleList";
import { Ar } from "@/components/Ar";
import { RIGHTS } from "@/lib/labels";

export const revalidate = 60;


function Lead({ a }: { a: ArticleCard }) {
  return (
    <article className="lead" aria-labelledby="lead-title">
      <div className="lead-meta">
        <Gauge level={a.importance} />
        <Link href={`/sources/${a.source.slug}`}><bdi>{a.source.name_ar}</bdi></Link>
        {a.doc_type && <><span className="sep" aria-hidden="true">·</span>{a.doc_type.name_ar}</>}
        {a.original_published_at && <><span className="sep" aria-hidden="true">·</span>{arDate(a.original_published_at)}</>}
      </div>
      <h2 id="lead-title"><Link href={`/articles/${a.id}`}>{a.title_ar}</Link></h2>
      {a.title_en && <bdi className="title-en" lang={a.source_language} dir="auto">{a.title_en}</bdi>}
      {a.dek_ar && <p className="lead-dek"><Ar text={a.dek_ar} /></p>}
      <div className="lead-foot">
        <Badges a={a} />
        {a.authors.length > 0 && <bdi className="authors-latin" dir="auto">{a.authors.join(" · ")}</bdi>}
      </div>
      <div className="actions">
        <Link className="btn" href={`/articles/${a.id}#summary`}>اقرأ الملخّص التحليلي</Link>
        {a.publish_level === "full" && <Link className="more" href={`/articles/${a.id}#body`}>اقرأ الترجمة الكاملة ←</Link>}
      </div>
    </article>
  );
}

function TrendsBlock({ t }: { t: TrendStats }) {
  const top = t.topics.filter((r) => r.count > 0).slice(0, 6);
  const max = Math.max(1, ...top.map((r) => r.count));
  const change = t.previous_total ? Math.round(((t.total - t.previous_total) / t.previous_total) * 100) : null;
  return (
    <section aria-labelledby="ix-trends">
      <h2 id="ix-trends" className="kicker block-head">اتجاهات {arMonth(t.month)}</h2>
      <div className="stat-big">
        <strong>{arNumber(t.total)}</strong>
        <span>مادة منشورة{change !== null && <><br /><bdi dir="ltr">{change > 0 ? `+${change}٪` : `${change}٪`}</bdi> عن الشهر السابق</>}</span>
      </div>
      {top.length > 0 && (
        <ul className="mini-bars">
          {top.map((r) => (
            <li key={r.slug}>
              <span>{r.name_ar}</span>
              <span className="track" aria-hidden="true"><span className="fill" style={{ width: `${(r.count / max) * 100}%` }} /></span>
              <span className="v">{r.count}</span>
            </li>
          ))}
        </ul>
      )}
      <Link className="more" href={`/trends/${t.month}`}>{t.report ? "قراءة المحرّر لهذا الشهر ←" : "كل أرقام الشهر ←"}</Link>
    </section>
  );
}

export default async function Home({ searchParams }: { searchParams: Promise<{ page?: string }> }) {
  const page = Number((await searchParams).page ?? 1) || 1;
  const [articles, topics, sources, mostRead, dossiers, months] = await Promise.all([
    api.articles({ page }), api.topics(), api.sources(), api.mostRead().catch(() => []),
    api.dossiers().catch(() => []), api.trendMonths().catch(() => []),
  ]);
  const trend = months.length ? await api.trend(months[0].month).catch(() => null) : null;
  const active = sources.filter((s) => s.published_count > 0).sort((a, b) => b.published_count - a.published_count);
  const first = page === 1 && articles.items.length > 0;
  const lead = first ? articles.items[0] : null;
  const rest = first ? articles.items.slice(1) : articles.items;
  const now = new Date();

  return (
    <>
      <div className="folio">
        <span className="date">{arWeekdayDate(now)}</span>
        <span className="stats">
          المواد المنشورة {arNumber(articles.total)}
          <span className="wide"><span className="sep" aria-hidden="true">·</span>المصادر المرصودة {arNumber(active.length)}</span>
          {dossiers.length > 0 && <span className="wide"><span className="sep" aria-hidden="true">·</span>الملفات {arNumber(dossiers.length)}</span>}
        </span>
        <span className="links">
          <a href="/feed.xml">خلاصة RSS</a><span className="sep" aria-hidden="true">·</span>
          <Link href="/subscribe">النشرة الأسبوعية</Link><span className="sep" aria-hidden="true">·</span>
          <Link href="/developers">الواجهة البرمجية</Link>
        </span>
      </div>

      {lead && (
        <div className="home-top">
          <Lead a={lead} />
          {mostRead.length > 0 && (
            <aside aria-labelledby="most-read">
              <h2 id="most-read" className="kicker block-head">الأكثر قراءة هذا الأسبوع</h2>
              <ol className="ranked">
                {mostRead.slice(0, 5).map((a, i) => (
                  <li key={a.id}>
                    <span className="rank" aria-hidden="true">{i + 1}</span>
                    <span><Link href={`/articles/${a.id}`}>{a.title_ar}</Link><span className="src"><bdi>{a.source.name_ar}</bdi></span></span>
                  </li>
                ))}
              </ol>
              <p className="side-note"><Link href="/trends">كل الإحصاءات في «الاتجاهات» ←</Link></p>
            </aside>
          )}
        </div>
      )}

      <section aria-labelledby="latest">
        <div className={`sec-head${lead ? "" : " first"}`}>
          <h2 id="latest">{page === 1 ? "آخر ما رُصد" : `آخر ما رُصد، صفحة ${page}`}</h2>
          <span className="more muted">{arCount(articles.total, NOUNS.item)}</span>
        </div>
        <ArticleList items={rest} />
        <Pager page={page} total={articles.total} perPage={articles.per_page} base="/" />
      </section>

      {page === 1 && (
        <div className="index-grid">
          <section aria-labelledby="ix-topics">
            <h2 id="ix-topics" className="kicker block-head">الموضوعات</h2>
            <ul className="index-list">
              {topics.topic.filter((t) => t.count > 0).map((t) => (
                <li key={t.slug}><Link href={`/topics/${t.slug}`}>{t.name_ar}</Link><span className="count">{t.count}</span></li>
              ))}
            </ul>
          </section>
          <section aria-labelledby="ix-sources">
            <h2 id="ix-sources" className="kicker block-head">المصادر المرصودة</h2>
            <ul className="index-list">
              {active.map((s) => (
                <li key={s.slug}>
                  <span className="rights-letter" title={`مستوى الحقوق ${RIGHTS[s.rights_level].letter}`}>{RIGHTS[s.rights_level].letter}</span>
                  <Link href={`/sources/${s.slug}`}><bdi>{s.name_ar}</bdi></Link>
                  <span className="count">{s.published_count}</span>
                </li>
              ))}
            </ul>
            <p className="legend">أ = ترخيص مفتوح · ب = ترجمة كاملة بإذن · ج = ملخص ورابط فقط. <Link href="/sources">كل المصادر</Link></p>
          </section>
          <div>
            <section aria-labelledby="ix-regions">
              <h2 id="ix-regions" className="kicker block-head">المناطق</h2>
              <ul className="index-list">
                {topics.region.filter((t) => t.count > 0).map((t) => (
                  <li key={t.slug}><Link href={`/regions/${t.slug}`}>{t.name_ar}</Link><span className="count">{t.count}</span></li>
                ))}
              </ul>
            </section>
            {dossiers.length > 0 && (
              <section aria-labelledby="ix-dossiers" style={{ marginTop: "var(--space-8)" }}>
                <h2 id="ix-dossiers" className="kicker block-head">الملفات</h2>
                <ul className="dossier-mini">
                  {dossiers.slice(0, 3).map((d) => (
                    <li key={d.slug}>
                      <Link href={`/dossiers/${d.slug}`}>{d.title_ar}</Link>
                      <span className="from">{arCount(d.item_count, NOUNS.item)}{d.updated_at && <><span className="sep" aria-hidden="true">·</span>حُدِّث في {arDayMonth(d.updated_at)}</>}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
          {trend && !trend.empty ? <TrendsBlock t={trend} /> : <div />}
        </div>
      )}

      <section className="news-band" aria-labelledby="news-title">
        <div>
          <h2 id="news-title">مختارات أسبوعية يراجعها المحرّرون</h2>
          <p>تصلك صباح السبت، بحسب الموضوعات والمصادر التي تختارها. إلغاء الاشتراك بنقرة واحدة.</p>
        </div>
        <form className="inline-form" action="/subscribe">
          <label htmlFor="band-email" className="sr-only">بريدك الإلكتروني</label>
          <input id="band-email" name="email" type="email" dir="ltr" placeholder="name@university.edu" autoComplete="email" required />
          <button className="btn" type="submit">اشترك</button>
        </form>
      </section>
    </>
  );
}
