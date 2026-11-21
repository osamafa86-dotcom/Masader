import "@fontsource/noto-kufi-arabic/400.css";
import "@fontsource/noto-kufi-arabic/600.css";
import "@fontsource/noto-kufi-arabic/800.css";
import "@fontsource/noto-naskh-arabic/400.css";
import "@fontsource/noto-naskh-arabic/700.css";
import "./globals.css";
import type { Metadata } from "next";
import { Masthead } from "@/components/Masthead";
import { SITE_NAME, SITE_URL } from "@/lib/format";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: `${SITE_NAME}: الدراسات الاستراتيجية بالعربية`, template: `%s | ${SITE_NAME}` },
  description: "منصة عربية ترصد أبرز مراكز الفكر والمجلات المحكّمة في الدراسات الاستراتيجية والأمنية، وتقدّم ملخصاتها وترجماتها للباحث العربي.",
  alternates: { types: { "application/rss+xml": "/feed.xml" } },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl">
      <body>
        <a className="skip-link" href="#content">انتقل إلى المحتوى</a>
        <Masthead />
        <main id="content" className="wrap">{children}</main>
        <footer className="footer">
          <div className="wrap">
            <span>{SITE_NAME}: رصد الدراسات الاستراتيجية والأمنية وتقديمها بالعربية.</span>
            <nav aria-label="روابط الموقع">
              <a href="/methodology">المنهجية وسياسة الحقوق</a>
              <a href="/subscribe">النشرة الأسبوعية</a>
              <a href="/feed.xml">خلاصة RSS</a>
              <a href="/developers">الواجهة البرمجية</a>
              <a href="/privacy">الخصوصية</a>
              <a href="/terms">شروط الاستخدام</a>
              <a href="/editor">غرفة التحرير</a>
            </nav>
          </div>
        </footer>
      </body>
    </html>
  );
}
