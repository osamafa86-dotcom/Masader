import Link from "next/link";
import { redirect } from "next/navigation";
import { api } from "@/lib/api";
import { arMonth } from "@/lib/format";

export const dynamic = "force-dynamic";
export const metadata = { title: "الاتجاهات الشهرية" };

export default async function TrendsIndex({ searchParams }: { searchParams: Promise<{ all?: string }> }) {
  const months = await api.trendMonths();
  if (months.length && !(await searchParams).all) redirect(`/trends/${months[0].month}`);
  return (
    <div className="prose">
      <p className="kicker">الاتجاهات</p>
      <h1 className="page-title">الاتجاهات الشهرية</h1>
      {months.length === 0 ? <p className="empty"><strong>لا بيانات كافية بعد</strong>تظهر الاتجاهات بعد أول شهر من الرصد.</p> : (
        <ul className="issues">{months.map((m) => <li key={m.month}><Link href={`/trends/${m.month}`}>{arMonth(m.month)}{m.report ? "، مع قراءة تحليلية" : ""}</Link></li>)}</ul>
      )}
    </div>
  );
}
