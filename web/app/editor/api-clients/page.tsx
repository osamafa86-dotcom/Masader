import { editorFetch } from "@/lib/editor";
import { arDate } from "@/lib/format";
import type { ApiClientRow } from "@/lib/types";
import { setApiClientActive } from "../actions";
import { NewKeyForm } from "./NewKeyForm";

export const dynamic = "force-dynamic";
export const metadata = { title: "مفاتيح الواجهة البرمجية", robots: { index: false } };

export default async function ApiClients() {
  const rows = await editorFetch<ApiClientRow[]>("/api/editor/api-clients").catch((e: Error) => {
    if (e.message.includes("للمدير")) return null;
    throw e;
  });
  if (rows === null) return <p className="notice error">إدارة المفاتيح متاحة للمدير فقط.</p>;
  return (
    <div style={{ maxWidth: 1000 }}>
      <h1 className="page-title">مفاتيح الواجهة البرمجية</h1>
      <NewKeyForm />
      {rows.length === 0 ? <p className="empty">لم يصدر أي مفتاح بعد.</p> : (
        <table className="glossary-table" style={{ marginTop: "2rem" }}>
          <thead><tr><th scope="col">المؤسسة</th><th scope="col">المفتاح</th><th scope="col">الحد في الدقيقة</th><th scope="col">طلبات 30 يوماً</th><th scope="col">آخر استخدام</th><th scope="col">الحالة</th></tr></thead>
          <tbody>{rows.map((c) => (
            <tr key={c.id}>
              <td><strong>{c.name}</strong><div className="ui muted">{c.organization} <bdi dir="ltr">{c.contact_email}</bdi></div></td>
              <td className="en" dir="ltr">{c.key_prefix}…</td>
              <td className="ui">{c.rate_limit_per_minute}</td>
              <td className="ui">{c.requests_30d}</td>
              <td className="ui muted">{c.last_used_at ? arDate(c.last_used_at) : "-"}</td>
              <td>
                <form action={setApiClientActive.bind(null, c.id, !c.is_active)}>
                  <button className={`btn ${c.is_active ? "danger" : "secondary"}`}>{c.is_active ? "إيقاف المفتاح" : "إعادة تفعيله"}</button>
                </form>
              </td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </div>
  );
}
