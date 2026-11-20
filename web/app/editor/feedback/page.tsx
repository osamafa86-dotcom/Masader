import Link from "next/link";
import { editorFetch } from "@/lib/editor";
import { arDate } from "@/lib/format";
import { resolveFeedback } from "../actions";

export const dynamic = "force-dynamic";
export const metadata = { title: "بلاغات القرّاء", robots: { index: false } };

type Row = { id: number; document_id: number; paragraph_index: number | null; message: string; created_at: string };

export default async function FeedbackPage() {
  const rows = await editorFetch<Row[]>("/api/editor/feedback");
  return (
    <div className="prose">
      <h1 className="page-title">بلاغات القرّاء</h1>
      {rows.length === 0 ? <p className="empty">لا بلاغات مفتوحة.</p> : (
        <ol className="entries">
          {rows.map((r) => (
            <li key={r.id} className="entry" style={{ gridTemplateColumns: "1fr" }}>
              <div>
                <p className="from">
                  {arDate(r.created_at)}، عن <Link href={`/editor/items/${r.document_id}${r.paragraph_index !== null ? `#p${r.paragraph_index + 1}` : ""}`}>
                    المادة {r.document_id}{r.paragraph_index !== null ? `، الفقرة ${r.paragraph_index + 1}` : ""}
                  </Link>
                </p>
                <p>{r.message}</p>
                <form action={resolveFeedback}><input type="hidden" name="id" value={r.id} /><button className="btn secondary">تمت المعالجة</button></form>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
