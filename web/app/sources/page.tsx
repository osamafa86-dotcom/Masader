import Link from "next/link";
import { api } from "@/lib/api";
import type { SourceRow } from "@/lib/types";
import { arCount, NOUNS } from "@/lib/format";
import { PageHead } from "@/components/PageHead";
import { KIND, RIGHTS } from "@/lib/labels";

export const dynamic = "force-dynamic";
export const metadata = { title: "المصادر" };

function Table({ rows, caption }: { rows: SourceRow[]; caption: string }) {
  return (
    <table className="table stack">
      <caption className="sr-only">{caption}</caption>
      <thead><tr><th scope="col">المصدر</th><th scope="col">النوع</th><th scope="col">الحقوق</th><th scope="col" className="n">المواد</th></tr></thead>
      <tbody>
        {rows.map((s) => (
          <tr key={s.slug}>
            <td className="wide">
              <Link className="title" href={`/sources/${s.slug}`}><bdi>{s.name_ar}</bdi></Link>
              <div><bdi className="latin" lang="en">{s.name}</bdi></div>
            </td>
            <td>{KIND[s.kind] ?? s.kind}</td>
            <td><span className="rights-letter" aria-hidden="true">{RIGHTS[s.rights_level].letter}</span> {RIGHTS[s.rights_level].short}{s.license && <> · <bdi>{s.license}</bdi></>}</td>
            <td className="n">{s.published_count}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default async function SourcesPage() {
  const sources = (await api.sources()).filter((s) => !s.slug.startsWith("demo-") || s.published_count > 0);
  const active = sources.filter((s) => s.is_active || s.published_count > 0).sort((a, b) => b.published_count - a.published_count);
  const pending = sources.filter((s) => !s.is_active && s.published_count === 0);
  return (
    <>
      <PageHead kicker="الشفافية" title="المصادر قيد الرصد"
        lede={<>نرصد {arCount(active.length, NOUNS.source)} من مراكز الفكر والمجلات المحكّمة. حقوق كل مصدر تحدّد ما نقدّمه منه، ونذكرها على كل مادة. التفصيل في <Link href="/methodology">صفحة المنهجية</Link>.</>} />
      <dl className="rights-legend">
        {(["a", "b", "c"] as const).map((k) => (
          <div key={k}>
            <dt>
              <span className="rights-letter" aria-hidden="true">{RIGHTS[k].letter}</span>{RIGHTS[k].short}
            </dt>
            <dd>{RIGHTS[k].long}</dd>
          </div>
        ))}
      </dl>
      <Table rows={active} caption="المصادر قيد الرصد" />
      {pending.length > 0 && <>
        <div className="sec-head"><h2>قيد الإعداد</h2><span className="more muted">{arCount(pending.length, NOUNS.source)}</span></div>
        <p className="page-lede">مصادر سننضم إليها بعد تثبيت طريقة الرصد وسياسة الحقوق، ومنها المجلات المحكّمة المدفوعة.</p>
        <Table rows={pending} caption="مصادر قيد الإعداد" />
      </>}
    </>
  );
}
