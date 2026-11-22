import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiError, api } from "@/lib/api";
import { arCount, arDate, LANG_AR, NOUNS, readingMinutes, RTL_LANGS, SITE_NAME } from "@/lib/format";
import { ArticleList, Badges, Gauge, journalLine } from "@/components/ArticleList";
import { CitationBox } from "@/components/CopyBox";
import { SaveButton } from "@/components/AccountForms";
import { ViewBeacon } from "@/components/ViewBeacon";
import { readerFetch } from "@/lib/reader";
import type { AccountMe, ArticleDetail } from "@/lib/types";
import { Body, FeedbackForm } from "@/components/Body";
import { Ar } from "@/components/Ar";

export const revalidate = 60;

async function load(id: string) {
  const n = Number(id);
  if (!Number.isInteger(n) || n < 1) notFound();
  try {
    return await api.article(n);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const a = await load((await params).id);
  return {
    title: a.title_ar,
    description: a.dek_ar,
    openGraph: { title: a.title_ar, description: a.dek_ar, type: "article", locale: "ar_AR", siteName: SITE_NAME },
  };
}

function rightsLine(a: ArticleDetail): string {
  if (a.publish_level === "summary") return "حقوق محفوظة: ملخص تحليلي ورابط الأصل";
  if (a.source.rights_level === "b") return "ترجمة كاملة بإذن المصدر";
  return a.license ? `ترجمة كاملة بترخيص مفتوح (${a.license})` : "ترجمة كاملة بترخيص مفتوح";
}

function methodLine(a: ArticleDetail): string {
  if (!a.human_reviewed) return "ترجمة آلية لم يراجعها محرر بعد";
  return a.translation.reviewed_at ? `ترجمة آلية راجعها محرر متخصص في ${arDate(a.translation.reviewed_at)}` : "ترجمة آلية راجعها محرر متخصص";
}

function SecHead({ n, id, title }: { n: number; id: string; title: string }) {
  return (
    <div className="sec-head">
      <span className="sec-no" aria-hidden="true">{n}</span>
      <h2 id={id}>{title}</h2>
    </div>
  );
}

export default async function ArticlePage({ params }: { params: Promise<{ id: string }> }) {
  const a = await load((await params).id);
  const [related, me] = await Promise.all([
    api.related(a.id).catch(() => ({ items: [], basis: "tags" as const })),
    readerFetch<AccountMe>("/api/account/me"),
  ]);
  const srcDir = RTL_LANGS.has(a.source_language) ? "rtl" : "ltr";
  const s = a.summary;
  const origin = a.meta.doi ? `https://doi.org/${a.meta.doi}` : a.url;
  const langNote = a.source_language !== "en" ? ` (بـ${LANG_AR[a.source_language] ?? a.source_language})` : "";

  // Numbered sections: the numbers follow what this item actually has.
  const sections: { id: string; title: string }[] = [];
  if (a.basis !== "title") sections.push({ id: "summary", title: "الملخص التحليلي" });
  if (a.body) sections.push({ id: "body", title: "الترجمة الكاملة" });
  sections.push({ id: "cite", title: "للاستشهاد" }, { id: "rights", title: "المصدر والحقوق" });
  if (related.items.length) sections.push({ id: "related", title: "مواد ذات صلة" });
  const no = (id: string) => sections.findIndex((x) => x.id === id) + 1;

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "ScholarlyArticle",
    headline: a.title_ar,
    inLanguage: "ar",
    description: a.dek_ar,
    datePublished: a.published_at,
    translationOfWork: {
      "@type": "CreativeWork", name: a.title_en, url: a.url, inLanguage: a.source_language,
      author: a.authors.map((name) => ({ "@type": "Person", name })),
      publisher: { "@type": "Organization", name: a.source.name },
      datePublished: a.original_published_at,
    },
  };

  return (
    <article className="has-action-bar">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <ViewBeacon docId={a.id} />
      <nav className="crumbs" aria-label="مسار التصفّح">
        <Link href="/">الأحدث</Link><span className="sep" aria-hidden="true">/</span>
        <Link href={`/sources/${a.source.slug}`}><bdi>{a.source.name_ar}</bdi></Link>
        {a.doc_type && <><span className="sep" aria-hidden="true">/</span>{a.doc_type.name_ar}</>}
      </nav>

      <div className="article-grid">
        <header className="article-head">
          <div className="lead-meta">
            <Gauge level={a.importance} />
            {a.importance !== null && <span>أهمية {a.importance} من 5 للباحث المتخصص</span>}
            {a.doc_type && <><span className="sep" aria-hidden="true">·</span>{a.doc_type.name_ar}</>}
            {a.original_published_at && <><span className="sep" aria-hidden="true">·</span>نُشر الأصل في {arDate(a.original_published_at)}</>}
          </div>
          <h1>{a.title_ar}</h1>
          {a.title_en && <bdi className="title-en" lang={a.source_language} dir={srcDir}>{a.title_en}</bdi>}
          {(a.authors.length > 0 || a.meta.volume) && (
            <div className="byline">
              {a.authors_detail.length > 0 ? (
                <span>تأليف{" "}
                  {a.authors_detail.map((au, i) => (
                    <span key={au.slug}>{i > 0 && (i === a.authors_detail.length - 1 ? " و" : "، ")}
                      <Link href={`/authors/${au.slug}`}><bdi>{au.name}</bdi></Link></span>
                  ))}
                </span>
              ) : a.authors.length > 0 && <span>تأليف <bdi className="latin">{a.authors.join("، ")}</bdi></span>}
              {a.meta.volume && <><span className="sep" aria-hidden="true">·</span><span><bdi>{a.meta.journal ?? a.source.name}</bdi>، {journalLine(a.meta)}</span></>}
            </div>
          )}
          {a.dek_ar && <p className="dek-lg"><Ar text={a.dek_ar} /></p>}
          <Badges a={a} withType={false} />
        </header>

        <div className="article-main">
          {a.basis === "abstract" && (
            <p className="notice" style={{ marginTop: "var(--space-6)" }}>
              النص الكامل لهذه الدراسة متاح لدى الناشر للمشتركين، لذلك بُني هذا الملخص على الملخص المنشور للدراسة وحده،
              ولا يتجاوز ما ورد فيه.
            </p>
          )}
          {a.basis === "title" && (
            <p className="notice" style={{ marginTop: "var(--space-6)" }}>
              هذا مدخل من فهرس العدد: ترجمنا العنوان فقط لأن الناشر لا يتيح ملخصاً للمادة. افتح الرابط للاطلاع على الأصل.
            </p>
          )}

          {a.basis !== "title" && (
            <section aria-labelledby="summary">
              <SecHead n={no("summary")} id="summary" title="الملخص التحليلي" />
              <div className="summary-panel">
                {s.thesis_ar && <><h3>الأطروحة</h3><p><Ar text={s.thesis_ar} /></p></>}
                {!!s.key_points_ar?.length && <><h3>أبرز النقاط</h3><ul>{s.key_points_ar.map((p, i) => <li key={i}><Ar text={p} /></li>)}</ul></>}
                {s.evidence_ar && <><h3>الأدلة والمنهج</h3><p><Ar text={s.evidence_ar} /></p></>}
                {!!s.recommendations_ar?.length && <><h3>التوصيات</h3><ul>{s.recommendations_ar.map((p, i) => <li key={i}><Ar text={p} /></li>)}</ul></>}
                {s.significance_ar && <><h3>أهميتها للباحث</h3><p><Ar text={s.significance_ar} /></p></>}
                {!!s.quotes?.length && <>
                  <h3>من النصّ</h3>
                  {s.quotes.map((q, i) => (
                    <blockquote key={i} className="quote"><p>«<Ar text={q.ar} />»<bdi className="en" lang={a.source_language} dir={srcDir}>“{q.en}”</bdi></p></blockquote>
                  ))}
                </>}
              </div>
            </section>
          )}

          {a.body ? (
            <section aria-labelledby="body">
              <SecHead n={no("body")} id="body" title="الترجمة الكاملة" />
              <Body docId={a.id} body={a.body} lang={a.source_language}
                    note={a.source.rights_level === "b" ? "نصّ كامل مترجم بإذن المصدر" : a.license ? `نصّ كامل بترخيص ${a.license}` : undefined} />
            </section>
          ) : (
            <div style={{ marginTop: "var(--space-6)" }}>
              <p className="notice"><Ar text={a.rights_note} /></p>
              <details>
                <summary className="ui">أبلغ عن خطأ في هذا الملخص</summary>
                <FeedbackForm docId={a.id} />
              </details>
            </div>
          )}

          <section aria-labelledby="cite">
            <SecHead n={no("cite")} id="cite" title="للاستشهاد" />
            <CitationBox formats={[
              { key: "apa", label: "APA", text: a.citations.apa, ltr: true },
              { key: "chicago", label: "شيكاغو", text: a.citations.chicago, ltr: true },
              { key: "bibtex", label: "BibTeX", text: a.citations.bibtex, ltr: true },
              { key: "translation", label: "هذه الترجمة", text: a.citations.translation, ltr: false },
            ]} />
          </section>

          <section aria-labelledby="rights">
            <SecHead n={no("rights")} id="rights" title="المصدر والحقوق" />
            <div className="two-col">
              <dl className="facts">
                <dt>المصدر</dt>
                <dd><a href={a.source.homepage} rel="noopener" target="_blank"><bdi>{a.source.name_ar}</bdi></a>، <bdi className="latin">{a.source.name}</bdi></dd>
                {a.license && <><dt>الترخيص</dt><dd><bdi>{a.license}</bdi></dd></>}
                <dt>حقوق النشر</dt><dd><Ar text={a.rights_note} /></dd>
              </dl>
              <dl className="facts">
                <dt>عن هذه الترجمة</dt>
                <dd>{methodLine(a)}، بمسرد المنصة للمصطلحات الاستراتيجية.</dd>
                {a.published_at && <><dt>نُشرت هنا في</dt><dd>{arDate(a.published_at)}</dd></>}
                <dd style={{ marginTop: "var(--space-3)" }}><Link className="more" href="/methodology">كيف نترجم ونراجع ←</Link></dd>
              </dl>
            </div>
          </section>

          {related.items.length > 0 && (
            <section aria-labelledby="related">
              <SecHead n={no("related")} id="related" title="مواد ذات صلة" />
              <ArticleList items={related.items} compact />
            </section>
          )}
        </div>

        <aside className="article-side" aria-label="بطاقة المادة">
          <div className="side-block">
            <h2 className="kicker block-head">بطاقة المادة</h2>
            <dl className="facts-dl">
              <dt className="ph-hide">المصدر</dt><dd className="ph-hide"><Link href={`/sources/${a.source.slug}`}><bdi>{a.source.name_ar}</bdi></Link></dd>
              <dt>النوع</dt>
              <dd>{[a.doc_type?.name_ar, a.word_count > 0 && arCount(a.word_count, NOUNS.word),
                a.word_count > 0 && `قراءة الأصل نحو ${arCount(readingMinutes(a.word_count), NOUNS.minute)}`].filter(Boolean).join(" · ")}</dd>
              <dt className="ph-hide">اللغة الأصلية</dt><dd className="ph-hide">{LANG_AR[a.source_language] ?? a.source_language}</dd>
              <dt>الحقوق</dt><dd>{rightsLine(a)}</dd>
              <dt>طريقة الإعداد</dt><dd>{methodLine(a)}</dd>
              {a.topics.length > 0 && <><dt className="ph-hide">الموضوعات</dt><dd className="ph-hide">{a.topics.map((t, i) => <span key={t.slug}>{i > 0 && " · "}<Link href={`/topics/${t.slug}`}>{t.name_ar}</Link></span>)}</dd></>}
              {a.regions.length > 0 && <><dt className="ph-hide">المنطقة</dt><dd className="ph-hide">{a.regions.map((t, i) => <span key={t.slug}>{i > 0 && " · "}<Link href={`/regions/${t.slug}`}>{t.name_ar}</Link></span>)}</dd></>}
              {a.meta.doi && <><dt>المعرّف</dt><dd><a href={origin} dir="ltr" rel="noopener" target="_blank">{origin}</a></dd></>}
            </dl>
            <div className="side-actions">
              <SaveButton docId={a.id} initial={!!me.data?.saved_ids.includes(a.id)} signedIn={me.status === 200} />
              <a className="btn secondary" href="#cite">استشهد</a>
              <a className="btn secondary origin-btn" href={origin} rel="noopener" target="_blank"><span className="long">اقرأ الأصل لدى <bdi>{a.source.name_ar}</bdi>{langNote}</span><span className="short">الأصل</span></a>
            </div>
          </div>

          {a.glossary.length > 0 && (
            <div className="side-block">
              <h2 className="kicker block-head">مصطلحات في هذه المادة</h2>
              <ul className="term-list">
                {a.glossary.map((g) => <li key={g.en}><span className="ar">{g.ar}</span><bdi className="en" lang="en" dir="ltr">{g.en}</bdi></li>)}
              </ul>
              <Link className="more" href="/glossary">المسرد الكامل ←</Link>
            </div>
          )}

          <div className="side-block toc-block">
            <h2 className="kicker block-head">في هذه الصفحة</h2>
            <ol className="toc">
              {sections.map((x, i) => <li key={x.id}><span className="n">{i + 1}</span><a href={`#${x.id}`}>{x.title}</a></li>)}
            </ol>
          </div>
        </aside>
      </div>
    </article>
  );
}
