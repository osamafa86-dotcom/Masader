import Link from "next/link";
import { api } from "@/lib/api";
import { arMonth } from "@/lib/format";
import { editorFetch } from "@/lib/editor";

export const dynamic = "force-dynamic";
export const metadata = { title: "تقارير الاتجاهات", robots: { index: false } };

export default async function EditorTrends() {
  await editorFetch("/api/editor/me");
  const months = await api.trendMonths();
  return (
    <div className="prose">
      <h1 className="page-title">تقارير الاتجاهات</h1>
      <p className="page-lede">يُعدّ النظام مسودة قراءة لكل شهر ينتهي، مبنية على الأرقام وحدها. راجعها وعدّلها ثم انشرها.</p>
      <ul className="issues">{months.map((m) => <li key={m.month}><Link href={`/editor/trends/${m.month}`}>{arMonth(m.month)}{m.report ? " (منشور)" : ""}</Link></li>)}</ul>
    </div>
  );
}
