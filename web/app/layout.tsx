import "@fontsource/amiri/700.css";
import "@fontsource/scheherazade-new/400.css";
import "@fontsource/scheherazade-new/700.css";
import "@fontsource/noto-sans-arabic/400.css";
import "@fontsource/noto-sans-arabic/500.css";
import "@fontsource/noto-sans-arabic/600.css";
import "@fontsource/source-serif-4/400.css";
import "@fontsource/source-serif-4/400-italic.css";
import "@fontsource/ibm-plex-mono/400.css";
import "./globals.css";
import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { Masthead } from "@/components/Masthead";
import { CONTACT_EMAIL, SITE_NAME, SITE_URL } from "@/lib/format";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: `${SITE_NAME}: الدراسات الاستراتيجية بالعربية`, template: `%s | ${SITE_NAME}` },
  description: "منصة عربية ترصد أبرز مراكز الفكر والمجلات المحكّمة في الدراسات الاستراتيجية والأمنية، وتقدّم ملخصاتها وترجماتها للباحث العربي.",
  alternates: { types: { "application/rss+xml": "/feed.xml" } },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fbfaf7" },
    { media: "(prefers-color-scheme: dark)", color: "#171512" },
  ],
};

const SECTIONS = [
  { href: "/", label: "الأحدث" },
  { href: "/topics", label: "الموضوعات والمناطق" },
  { href: "/sources", label: "المصادر" },
  { href: "/dossiers", label: "الملفات" },
  { href: "/trends", label: "الاتجاهات الشهرية" },
  { href: "/glossary", label: "المسرد" },
];
const PLATFORM = [
  { href: "/methodology", label: "المنهجية وسياسة الحقوق" },
  { href: "/subscribe", label: "النشرة الأسبوعية" },
  { href: "/feed.xml", label: "خلاصة RSS" },
  { href: "/developers", label: "الواجهة البرمجية للمؤسسات" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl">
      <body>
        <a className="skip-link" href="#content">انتقل إلى المحتوى</a>
        <Masthead />
        <main id="content" className="wrap">{children}</main>
        <footer className="footer">
          <div className="wrap">
            <div>
              <Link href="/" className="brand">{SITE_NAME}</Link>
              <p className="about">
                منصة عربية ترصد مراكز الفكر والمجلات المحكّمة في الدراسات الاستراتيجية والأمنية،
                وتقدّم ملخصاتها وترجماتها للباحث العربي مع احترام حقوق أصحابها.
              </p>
            </div>
            <nav className="cols" aria-labelledby="ft-sections">
              <h2 id="ft-sections">الأقسام</h2>
              <ul>{SECTIONS.map((l) => <li key={l.href}><Link href={l.href}>{l.label}</Link></li>)}</ul>
            </nav>
            <nav className="cols" aria-labelledby="ft-platform">
              <h2 id="ft-platform">المنصة</h2>
              <ul>{PLATFORM.map((l) => <li key={l.href}><a href={l.href}>{l.label}</a></li>)}</ul>
            </nav>
            <nav className="cols" aria-labelledby="ft-legal">
              <h2 id="ft-legal">قانوني</h2>
              <ul>
                <li><Link href="/privacy">الخصوصية</Link></li>
                <li><Link href="/terms">شروط الاستخدام</Link></li>
                <li><Link href="/methodology#takedown">طلبات أصحاب الحقوق</Link></li>
                <li><a href={`mailto:${CONTACT_EMAIL}`}><bdi dir="ltr">{CONTACT_EMAIL}</bdi></a></li>
              </ul>
            </nav>
            <nav className="flat" aria-label="روابط الموقع">
              <Link href="/subscribe">النشرة</Link>
              <a href="/feed.xml">RSS</a>
              <Link href="/developers">الواجهة البرمجية</Link>
              <Link href="/privacy">الخصوصية</Link>
              <Link href="/terms">الشروط</Link>
              <Link href="/methodology">المنهجية</Link>
            </nav>
          </div>
        </footer>
      </body>
    </html>
  );
}
