"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { SITE_NAME } from "@/lib/format";

const LINKS = [
  { href: "/", label: "الأحدث" },
  { href: "/topics", label: "الموضوعات" },
  { href: "/dossiers", label: "الملفات" },
  { href: "/trends", label: "الاتجاهات" },
  { href: "/sources", label: "المصادر" },
  { href: "/glossary", label: "المسرد" },
  { href: "/methodology", label: "المنهجية" },
];

export function Masthead() {
  const path = usePathname();
  if (path.startsWith("/editor")) return <EditorBar />;
  return (
    <header className="masthead">
      <div className="wrap">
        <Link href="/" className="wordmark">{SITE_NAME}<small>الدراسات الاستراتيجية بالعربية</small></Link>
        <nav className="nav" aria-label="الأقسام">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} aria-current={(l.href === "/" ? path === "/" : path.startsWith(l.href)) ? "page" : undefined}>
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="mast-tools">
        <form className="search-box" action="/search" role="search">
          <label htmlFor="q" className="skip-link">ابحث في الموقع</label>
          <input id="q" name="q" type="search" placeholder="ابحث بالعربية أو الإنجليزية" minLength={2} required />
          <button type="submit">بحث</button>
        </form>
        <Link href="/account" className="ui">حسابي</Link>
        </div>
      </div>
    </header>
  );
}

function EditorBar() {
  return (
    <header className="masthead">
      <div className="wrap">
        <Link href="/editor" className="wordmark">{SITE_NAME}<small>غرفة التحرير</small></Link>
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
      </div>
    </header>
  );
}
