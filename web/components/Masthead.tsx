"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { SITE_NAME } from "@/lib/format";

const LINKS = [
  { href: "/", label: "الأحدث" },
  { href: "/topics", label: "الموضوعات" },
  { href: "/topics#regions", label: "المناطق", match: "/regions" },
  { href: "/sources", label: "المصادر" },
  { href: "/dossiers", label: "الملفات" },
  { href: "/trends", label: "الاتجاهات" },
  { href: "/glossary", label: "المسرد" },
];

function isCurrent(path: string, l: (typeof LINKS)[number]): boolean {
  if (l.href === "/") return path === "/";
  if (l.match) return path.startsWith(l.match);
  return path.startsWith(l.href.split("#")[0]);
}

export function Masthead() {
  const path = usePathname();
  if (path.startsWith("/editor")) return <EditorBar />;
  const links = LINKS.map((l) => (
    <Link key={l.href} href={l.href} aria-current={isCurrent(path, l) ? "page" : undefined}>{l.label}</Link>
  ));
  return (
    <header className="masthead">
      <div className="wrap mast-row">
        <Link href="/" className="wordmark">
          <span>{SITE_NAME}</span>
          <small>الدراسات الاستراتيجية بالعربية</small>
        </Link>
        <nav className="nav" aria-label="الأقسام">{links}</nav>
        <div className="mast-tools">
          <form className="search-box" action="/search" role="search">
            <label htmlFor="q" className="sr-only">ابحث في الموقع</label>
            <input id="q" name="q" type="search" placeholder="ابحث بالعربية أو الإنجليزية" minLength={2} required />
            <button type="submit">بحث</button>
          </form>
          <Link href="/account" className="mast-account">حسابي</Link>
          <div className="mast-phone">
            <Link href="/search">بحث</Link>
            <details className="mast-menu" key={path}>
              <summary aria-label="القائمة"><span aria-hidden="true">≡</span></summary>
              <nav aria-label="القائمة">
                {links}
                <Link href="/account">حسابي</Link>
                <Link href="/methodology">المنهجية</Link>
              </nav>
            </details>
          </div>
        </div>
      </div>
    </header>
  );
}

function EditorBar() {
  return (
    <header className="masthead">
      <div className="wrap mast-row">
        <Link href="/editor" className="wordmark"><span>{SITE_NAME}</span><small>غرفة التحرير</small></Link>
        <nav className="nav" aria-label="أقسام التحرير">
          <Link href="/editor">صف المراجعة</Link>
          <Link href="/editor?stage=failed">المتعثرة</Link>
          <Link href="/editor?stage=published">المنشورة</Link>
          <Link href="/editor/import">استيراد</Link>
          <Link href="/editor/newsletter">النشرة</Link>
          <Link href="/editor/dossiers">الملفات</Link>
          <Link href="/editor/trends">الاتجاهات</Link>
          <Link href="/editor/api-clients">مفاتيح الواجهة</Link>
          <Link href="/editor/security">الأمان</Link>
          <Link href="/editor/glossary">المسرد</Link>
          <Link href="/editor/feedback">بلاغات القرّاء</Link>
          <Link href="/" target="_blank">الموقع العام</Link>
        </nav>
        <div />
      </div>
    </header>
  );
}
