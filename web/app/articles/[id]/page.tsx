import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiError, api } from "@/lib/api";
import { arDate, authorsLine, readingMinutes, SITE_NAME } from "@/lib/format";
import { ArticleList, Badges, journalLine } from "@/components/ArticleList";
import { CitationBox } from "@/components/CopyBox";
import { SaveButton } from "@/components/AccountForms";
import { readerFetch } from "@/lib/reader";
import type { AccountMe } from "@/lib/types";
import { LANG_AR, RTL_LANGS } from "@/lib/format";
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

export default async function ArticlePage({ params }: { params: Promise<{ id: string }> }) {
  const a = await load((await params).id);
  const [related, me] = await Promise.all([
    api.related(a.id).catch(() => ({ items: [], basis: "tags" as const })),
    readerFetch<AccountMe>("/api/account/me"),
  ]);
  const srcDir = RTL_LANGS.has(a.source_language) ? "rtl" : "ltr";
  const s = a.summary;
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "ScholarlyArticle",
    headline: a.title_ar,
    inLanguage: "ar",
    description: a.dek_ar,
    datePublished: a.published_at,
    translationOfWork: {
      "@type": "CreativeWork", name: a.title_en, url: a.url, inLanguage: "en",
      author: a.authors.map((name) => ({ "@type": "Person", name })),
      publisher: { "@type": "Organization", name: a.source.name },
      datePublished: a.original_published_at,
    },
  };
  return (
    <article>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <header className="article-head">
        <div className="ui"><Link href={`/sources/${a.source.slug}`}>{a.source.name_ar}</Link></div>
        <h1>{a.title_ar}</h1>
        <bdi className="title-en" lang={a.source_language} dir={srcDir}>{a.title_en}</bdi>
        <div className="byline">
          {a.authors_detail.length > 0 && (
            <span>تأليف{" "}
              {a.authors_detail.map((au, i) => (
                <span key={au.slug}>{i > 0 && (i === a.authors_detail.length - 1 ? " و" : "، ")}
                  <Link href={`/authors/${au.slug}`}><strong><bdi>{au.name}</bdi></strong></Link></span>
              ))}
            </span>
          )}
          {a.authors_detail.length === 0 && a.authors.length > 0 && <span>تأليف <strong><bdi>{authorsLine(a.authors)}</bdi></strong></span>}
          {a.meta.volume && <span>{a.meta.journal ?? a.source.name}، {journalLine(a.meta)}</span>}
          {a.original_published_at && <span>نُشر الأصل في {arDate(a.original_published_at)}</span>}
          {a.word_count > 0 && <span>قراءة الأصل نحو {readingMinutes(a.word_count)} دقيقة</span>}
        </div>
        <Badges a={a} />
        {a.dek_ar && <p className="dek-lg"><Ar text={a.dek_ar} /></p>}
        <div className="badges" style={{ alignItems: "center", marginTop: "1rem" }}>
          <a className="origin-link" style={{ marginTop: 0 }} href={a.meta.doi ? `https://doi.org/${a.meta.doi}` : a.url} rel="noopener" target="_blank">
            اقرأ النص الأصلي لدى {a.source.name_ar}{a.source_language !== "en" && <> (بـ{LANG_AR[a.source_language] ?? a.source_language})</>}
          </a>
          <SaveButton docId={a.id} initial={!!me.data?.saved_ids.includes(a.id)} signedIn={me.status === 200} />
        </div>
        {a.meta.doi && <div className="ui muted">المعرّف الرقمي <bdi className="latin" dir="ltr">doi:{a.meta.doi}</bdi></div>}
      </header>

      {a.basis === "abstract" && (
        <p className="notice" style={{ maxWidth: 860 }}>
          النص الكامل لهذه الدراسة متاح لدى الناشر للمشتركين، لذلك بُني هذا الملخص على الملخص المنشور للدراسة وحده،
          ولا يتجاوز ما ورد فيه.
        </p>
      )}
      {a.basis === "title" && (
        <p className="notice" style={{ maxWidth: 860 }}>
          هذا مدخل من فهرس العدد: ترجمنا العنوان فقط لأن الناشر لا يتيح ملخصاً للمادة. افتح الرابط للاطلاع على الأصل.
        </p>
      )}

      {a.basis !== "title" && <section className="summary-panel" aria-labelledby="summary-title">
        <h2 id="summary-title">الملخص التحليلي</h2>
        {s.thesis_ar && <><h3>الأطروحة</h3><p><Ar text={s.thesis_ar} /></p></>}
        {!!s.key_points_ar?.length && <><h3>أبرز النقاط</h3><ul>{s.key_points_ar.map((p, i) => <li key={i}><Ar text={p} /></li>)}</ul></>}
        {s.evidence_ar && <><h3>الأدلة والمنهج</h3><p><Ar text={s.evidence_ar} /></p></>}
        {!!s.recommendations_ar?.length && <><h3>التوصيات</h3><ul>{s.recommendations_ar.map((p, i) => <li key={i}><Ar text={p} /></li>)}</ul></>}
        {s.significance_ar && <><h3>أهميتها للباحث</h3><p><Ar text={s.significance_ar} /></p></>}
        {!!s.quotes?.length && <>
          <h3>من النص</h3>
          {s.quotes.map((q, i) => (
            <blockquote key={i} className="quote"><p>«<Ar text={q.ar} />»<bdi className="en" lang="en" dir="ltr">“{q.en}”</bdi></p></blockquote>
          ))}
        </>}
      </section>}

      {a.body ? <Body docId={a.id} body={a.body} lang={a.source_language} /> : (
        <section className="prose">
          <p className="notice"><Ar text={a.rights_note} /></p>
          <details>
            <summary className="ui">أبلغ عن خطأ في هذا الملخص</summary>
            <FeedbackForm docId={a.id} />
          </details>
        </section>
      )}

      <div className="facts">
        <section>
          <h2>المصدر والحقوق</h2>
          <dl>
            <dt>المصدر</dt><dd><a href={a.source.homepage} rel="noopener" target="_blank">{a.source.name_ar}</a></dd>
            {a.license && <><dt>الترخيص</dt><dd><bdi>{a.license}</bdi></dd></>}
            <dt>حقوق النشر</dt><dd><Ar text={a.rights_note} /></dd>
          </dl>
        </section>
        <section>
          <h2>عن هذه الترجمة</h2>
          <dl>
            <dt>طريقة الإعداد</dt>
            <dd>{a.human_reviewed ? "ترجمة آلية راجعها محرر متخصص" : "ترجمة آلية لم يراجعها محرر بعد"}</dd>
            {a.translation.reviewed_at && <><dt>تاريخ المراجعة</dt><dd>{arDate(a.translation.reviewed_at)}</dd></>}
            {a.published_at && <><dt>نُشرت هنا في</dt><dd>{arDate(a.published_at)}</dd></>}
            <dt>المنهجية</dt><dd><Link href="/methodology">كيف نترجم ونراجع</Link></dd>
          </dl>
        </section>
        <section className="wide">
          <h2>للاستشهاد</h2>
          <CitationBox formats={[
            { key: "apa", label: "APA", text: a.citations.apa, ltr: true },
            { key: "chicago", label: "شيكاغو", text: a.citations.chicago, ltr: true },
            { key: "bibtex", label: "BibTeX", text: a.citations.bibtex, ltr: true },
            { key: "translation", label: "هذه الترجمة", text: a.citations.translation, ltr: false },
          ]} />
        </section>
        {a.glossary.length > 0 && (
          <section>
            <h2>مصطلحات في هذه المادة</h2>
            <ul className="ui" style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {a.glossary.map((g) => <li key={g.en}>{g.ar} <bdi className="latin muted" lang="en">{g.en}</bdi></li>)}
            </ul>
          </section>
        )}
      </div>

      {related.items.length > 0 && (
        <section className="related" aria-labelledby="related-title">
          <h2 id="related-title">مواد ذات صلة</h2>
          <ArticleList items={related.items} />
        </section>
      )}
    </article>
  );
}
