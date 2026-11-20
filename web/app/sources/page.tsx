import Link from "next/link";
import { api } from "@/lib/api";
import type { SourceRow } from "@/lib/types";

export const dynamic = "force-dynamic";
export const metadata = { title: "المصادر" };

const RIGHTS: Record<SourceRow["rights_level"], string> = {
  a: "ترخيص مفتوح أو ملك عام: نترجم النص كاملاً",
  b: "بإذن من المصدر: نترجم النص كاملاً",
  c: "حقوق محفوظة: ننشر ملخصاً تحليلياً مع رابط الأصل",
};

function Row({ s }: { s: SourceRow }) {
  return (
    <li className="entry" style={{ gridTemplateColumns: "1fr" }}>
      <article>
        <h2><Link href={`/sources/${s.slug}`}>{s.name_ar}</Link></h2>
        <p className="from"><bdi className="latin">{s.name}</bdi></p>
        {s.description_ar && <p className="dek">{s.description_ar}</p>}
        <div className="badges">
          <span className={`badge${s.rights_level !== "c" ? " full" : ""}`}>{RIGHTS[s.rights_level]}</span>
          {s.license && <span className="badge"><bdi>{s.license}</bdi></span>}
          {s.is_active && <span className="badge">{s.published_count} مادة منشورة</span>}
        </div>
      </article>
    </li>
  );
}

export default async function SourcesPage() {
  const sources = (await api.sources()).filter((s) => !s.slug.startsWith("demo-") || s.published_count > 0);
  const active = sources.filter((s) => s.is_active || s.published_count > 0);
  const pending = sources.filter((s) => !s.is_active && s.published_count === 0);
  return (
    <div className="prose" style={{ maxWidth: 860 }}>
      <h1 className="page-title">المصادر</h1>
      <p className="page-lede">
        نحدد لكل مصدر ما يجوز نشره بحسب ترخيصه أو الإذن الممنوح لنا، ونعرض ذلك هنا بوضوح.
        التفاصيل في <Link href="/methodology">صفحة المنهجية</Link>.
      </p>
      <h2>قيد الرصد</h2>
      <ol className="entries">{active.map((s) => <Row key={s.slug} s={s} />)}</ol>
      <h2>قيد الإعداد</h2>
      <p className="muted">مصادر سننضم إليها بعد تثبيت طريقة الرصد وسياسة الحقوق، ومنها المجلات المحكّمة المدفوعة.</p>
      <ol className="entries">{pending.map((s) => <Row key={s.slug} s={s} />)}</ol>
    </div>
  );
}
