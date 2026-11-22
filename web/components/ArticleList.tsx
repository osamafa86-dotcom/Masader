import Link from "next/link";
import type { ArticleCard } from "@/lib/types";
import { arDayMonth, importanceLabel } from "@/lib/format";
import { levelBadge, reviewBadge } from "@/lib/badges";
import { Ar } from "./Ar";

/** Five bars and an N/5 label; 4–5 in the accent, the empty bars visible at low contrast. */
export function Gauge({ level }: { level: number | null }) {
  const n = level ?? 0;
  const label = importanceLabel(level);
  return (
    <span className="gauge" data-level={n} role="img" aria-label={label.long} title={label.long}>
      <span className="bars" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((i) => <i key={i} className={i <= n ? "on" : undefined} />)}
      </span>
      <span className="n" aria-hidden="true">{label.short}</span>
    </span>
  );
}

export function journalLine(m: ArticleCard["meta"]): string {
  const parts = [m.volume && `المجلد ${m.volume}`, m.issue && `العدد ${m.issue}`,
    // U+2066/U+2069 isolate the range left-to-right, otherwise "412-435" displays as "435-412" in Arabic text.
    m.start_page && (m.end_page && m.end_page !== m.start_page ? `الصفحات ⁦${m.start_page}–${m.end_page}⁩` : `الصفحة ${m.start_page}`)];
  return parts.filter(Boolean).join("، ");
}

/** Where and when, for list margins: the journal issue for journals, the day and month otherwise. */
export function whenLine(a: Pick<ArticleCard, "meta" | "original_published_at" | "doc_type">): string {
  const when = a.meta.volume ? [a.meta.volume && `المجلد ${a.meta.volume}`, a.meta.issue && `العدد ${a.meta.issue}`].filter(Boolean).join("، ")
    : arDayMonth(a.original_published_at);
  return [when, a.doc_type?.name_ar].filter(Boolean).join(" · ");
}

export function Badges({ a, withType = false }: {
  a: Pick<ArticleCard, "publish_level" | "human_reviewed" | "doc_type" | "basis" | "meta" | "source">;
  withType?: boolean;
}) {
  const level = levelBadge({ publish_level: a.publish_level, basis: a.basis, rights_level: a.source.rights_level });
  const review = reviewBadge(a.human_reviewed);
  return (
    <div className="badges">
      <span className={`badge${level.full ? " full" : ""}`}>{level.text}</span>
      <span className={`badge${review.machine ? " machine" : ""}`}>{review.text}</span>
      {a.meta.open_access && <span className="badge">وصول مفتوح لدى الناشر</span>}
      {withType && a.doc_type && <span className="badge">{a.doc_type.name_ar}</span>}
    </div>
  );
}

function EntryMargin({ a }: { a: ArticleCard }) {
  return (
    <div className="entry-margin">
      <Link className="entry-source" href={`/sources/${a.source.slug}`}><bdi>{a.source.name_ar}</bdi></Link>
      <span>{whenLine(a)}</span>
      <Gauge level={a.importance} />
    </div>
  );
}

export function ArticleList({ items, notes, compact = false, headingLevel = 2, empty }: {
  items: ArticleCard[];
  notes?: Record<number, string>;
  compact?: boolean;
  headingLevel?: 2 | 3;
  empty?: React.ReactNode;
}) {
  if (!items.length) return <p className="empty">{empty ?? "لا توجد مواد منشورة هنا بعد."}</p>;
  const H = compact ? "h3" : (`h${headingLevel}` as "h2" | "h3");
  return (
    <ol className={`entries${compact ? " compact" : ""}`}>
      {items.map((a) => (
        <li key={a.id} className="entry">
          <EntryMargin a={a} />
          <article>
            <H><Link href={`/articles/${a.id}`}>{a.title_ar}</Link></H>
            {!compact && a.dek_ar && <p className="dek"><Ar text={a.dek_ar} /></p>}
            {!compact && notes?.[a.id] && <div className="note"><span className="kicker">ملاحظة المحرّر</span><p><Ar text={notes[a.id]} /></p></div>}
            {!compact && <Badges a={a} />}
          </article>
        </li>
      ))}
    </ol>
  );
}

export function Pager({ page, total, perPage, base }: { page: number; total: number; perPage: number; base: string }) {
  const pages = Math.ceil(total / perPage);
  if (pages <= 1) return null;
  const sep = base.includes("?") ? "&" : "?";
  return (
    <nav className="pager" aria-label="الصفحات">
      {page > 1 && <Link className="prev" href={`${base}${sep}page=${page - 1}`}>→ الصفحة السابقة</Link>}
      <span className="where">صفحة {page} من {pages}</span>
      {page < pages && <Link className="next" href={`${base}${sep}page=${page + 1}`}>الصفحة التالية ←</Link>}
    </nav>
  );
}
