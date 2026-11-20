import Link from "next/link";
import { editorFetch } from "@/lib/editor";
import { arDate } from "@/lib/format";
import type { DigestRow } from "@/lib/types";
import { createDigest } from "../actions";

export const dynamic = "force-dynamic";
export const metadata = { title: "النشرة البريدية", robots: { index: false } };

const STATUS = { draft: "مسودة بانتظار المراجعة", sending: "قيد الإرسال", sent: "أُرسلت" };

export default async function NewsletterAdmin({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const error = (await searchParams).error;
  const data = await editorFetch<{ active_subscribers: number; digests: DigestRow[] }>("/api/editor/digests");
  return (
    <div style={{ maxWidth: 900 }}>
      <h1 className="page-title">النشرة البريدية</h1>
      <p className="page-lede">
        {data.active_subscribers} مشتركاً مؤكداً. يُعدّ النظام مسودة كل أسبوع، ولا يُرسل شيء قبل أن تراجعها وتضغط «أرسل».
      </p>
      {error && <p className="notice error">{error}</p>}
      <form action={createDigest} style={{ marginBottom: "1.5rem" }}><button className="btn secondary">أعدّ مسودة الآن</button></form>
      {data.digests.length === 0 ? <p className="empty">لم تُعدّ أي نشرة بعد.</p> : (
        <table className="glossary-table">
          <thead><tr><th scope="col">النشرة</th><th scope="col">الحالة</th><th scope="col">المواد</th><th scope="col">التسليم</th></tr></thead>
          <tbody>
            {data.digests.map((d) => (
              <tr key={d.id}>
                <td><Link href={`/editor/newsletter/${d.id}`}>{d.subject_ar}</Link><div className="ui muted">حتى {arDate(d.period_end)}</div></td>
                <td className="ui">{STATUS[d.status]}</td>
                <td className="ui">{d.document_ids.length}</td>
                <td className="ui">{d.deliveries.sent ?? 0} أُرسلت{d.deliveries.skipped ? `، ${d.deliveries.skipped} بلا مواد مطابقة` : ""}{d.deliveries.failed ? `، ${d.deliveries.failed} فشلت` : ""}{d.deliveries.pending ? `، ${d.deliveries.pending} في الانتظار` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
