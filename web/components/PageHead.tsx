import Link from "next/link";

type Crumb = { href?: string; label: React.ReactNode };

/** The head every section page shares: trail, accent kicker, display title, lede and a line of facts. */
export function PageHead({ crumbs, kicker, title, titleEn, lede, meta }: {
  crumbs?: Crumb[];
  kicker?: string;
  title: React.ReactNode;
  titleEn?: string;
  lede?: React.ReactNode;
  meta?: React.ReactNode;
}) {
  return (
    <header className="page-head">
      {crumbs && crumbs.length > 0 && (
        <nav className="crumbs" aria-label="مسار التصفّح">
          {crumbs.map((c, i) => (
            <span key={i}>
              {i > 0 && <span className="sep" aria-hidden="true">/</span>}
              {c.href ? <Link href={c.href}>{c.label}</Link> : c.label}
            </span>
          ))}
        </nav>
      )}
      {kicker && <p className="kicker">{kicker}</p>}
      <h1 className="page-title">{title}</h1>
      {titleEn && <bdi className="title-en" lang="en" dir="ltr">{titleEn}</bdi>}
      {lede && <p className="page-lede">{lede}</p>}
      {meta && <p className="page-meta">{meta}</p>}
    </header>
  );
}
