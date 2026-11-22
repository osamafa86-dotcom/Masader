import Link from "next/link";
import { redirect } from "next/navigation";
import { readerFetch } from "@/lib/reader";
import { newsletterChoices } from "@/lib/choices";
import { arCount, arDate, NOUNS } from "@/lib/format";
import { AlertsForm } from "@/components/AccountForms";
import type { AccountMe, LibraryRow } from "@/lib/types";
import { deleteAccount, logout, removeSaved, saveNote } from "./actions";

export const dynamic = "force-dynamic";
export const metadata = { title: "حسابي", robots: { index: false } };

export default async function Account() {
  const [me, lib] = await Promise.all([readerFetch<AccountMe>("/api/account/me"), readerFetch<LibraryRow[]>("/api/account/library")]);
  if (me.status === 401 || !me.data) redirect("/account/login");
  const choices = await newsletterChoices();
  const rows = lib.data ?? [];
  return (
    <div className="with-rail">
      <section>
        <p className="kicker">حسابي</p>
        <h1 className="page-title">مكتبتي</h1>
        <p className="page-lede">{rows.length ? `في مكتبتك ${arCount(rows.length, NOUNS.item)}.` : "لم تحفظ شيئاً بعد. استخدم زر «احفظ في مكتبتي» في صفحة أي مادة."}</p>
        <ol className="entries">
          {rows.map((r) => (
            <li key={r.document_id} className="entry" style={{ gridTemplateColumns: "1fr" }}>
              <article>
                <div className="from">حُفظت في {arDate(r.saved_at)}{r.article && <>، {r.article.source.name_ar}</>}</div>
                {r.article ? <h2><Link href={`/articles/${r.document_id}`}>{r.article.title_ar}</Link></h2>
                  : <h2 className="muted">مادة لم تعد متاحة على الموقع</h2>}
                <form action={saveNote.bind(null, r.document_id)} className="feedback-form">
                  <label className="ui" htmlFor={`note-${r.document_id}`}>ملاحظتي</label>
                  <textarea id={`note-${r.document_id}`} name="note" defaultValue={r.note} rows={2} />
                  <div className="badges">
                    <button className="btn secondary">حفظ الملاحظة</button>
                    <button className="btn danger" formAction={removeSaved.bind(null, r.document_id)}>إزالة من المكتبة</button>
                  </div>
                </form>
              </article>
            </li>
          ))}
        </ol>
      </section>
      <aside className="rail">
        <section>
          <h2>التنبيهات</h2>
          <AlertsForm me={me.data} {...choices} />
        </section>
        <section>
          <h2>الحساب</h2>
          <p className="ui"><bdi dir="ltr">{me.data.email}</bdi>، منذ {arDate(me.data.created_at)}</p>
          <form action={logout}><button className="btn secondary">تسجيل الخروج</button></form>
          <details style={{ marginTop: "1rem" }}>
            <summary className="ui">حذف الحساب</summary>
            <p className="ui">يحذف الحساب ومكتبتك وملاحظاتك واشتراكك في النشرة نهائياً.</p>
            <form action={deleteAccount}><button className="btn danger">احذف حسابي وبياناتي</button></form>
          </details>
        </section>
      </aside>
    </div>
  );
}
