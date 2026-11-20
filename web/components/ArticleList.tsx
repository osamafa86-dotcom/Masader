import Link from "next/link";
import type { ArticleCard } from "@/lib/types";
import { arDate } from "@/lib/format";
import { Ar } from "./Ar";

export function Gauge({ level }: { level: number | null }) {
  const n = level ?? 0;
  return (
    <div className="gauge" data-level={n} role="img" aria-label={`الأهمية ${n} من 5`} title={`الأهمية ${n} من 5`}>
      {[1, 2, 3, 4, 5].map((i) => <span key={i} className={i <= n ? "on" : ""} />)}
    </div>
  );
}

export function Badges({ a }: { a: Pick<ArticleCard, "publish_level" | "human_reviewed" | "doc_type"> }) {
  return (
    <div className="badges">
      {a.publish_level === "full"
        ? <span className="badge full">نص كامل مترجم</span>
        : <span className="badge">ملخص تحليلي</span>}
      {a.human_reviewed
        ? <span className="badge">مراجَعة بشرياً</span>
        : <span className="badge machine">ترجمة آلية دون مراجعة</span>}
      {a.doc_type && <span className="badge">{a.doc_type.name_ar}</span>}
    </div>
  );
}

export function ArticleList({ items, lead = false }: { items: ArticleCard[]; lead?: boolean }) {
  if (!items.length) return <p className="empty">لا توجد مواد منشورة هنا بعد.</p>;
  return (
    <ol className="entries">
      {items.map((a, i) => (
        <li key={a.id} className={`entry${lead && i === 0 ? " entry-lead" : ""}`}>
          <Gauge level={a.importance} />
          <article>
            <div className="from">
              <Link href={`/sources/${a.source.slug}`}>{a.source.name_ar}</Link>
              {a.original_published_at && <>، {arDate(a.original_published_at)}</>}
            </div>
            <h2><Link href={`/articles/${a.id}`}>{a.title_ar}</Link></h2>
            {a.dek_ar && <p className="dek"><Ar text={a.dek_ar} /></p>}
            <Badges a={a} />
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
      {page > 1 && <Link href={`${base}${sep}page=${page - 1}`}>الصفحة السابقة</Link>}
      <span className="muted">صفحة {page} من {pages}</span>
      {page < pages && <Link href={`${base}${sep}page=${page + 1}`}>الصفحة التالية</Link>}
    </nav>
  );
}
