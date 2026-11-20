"use client";
import { useActionState, useState } from "react";
import { sendFeedback, type FeedbackState } from "@/app/actions";
import { Ar } from "./Ar";

type Para = { en: string; ar: string };

export function Body({ docId, body }: { docId: number; body: Para[] }) {
  const [parallel, setParallel] = useState(false);
  const [reporting, setReporting] = useState<number | null>(null);
  return (
    <section aria-labelledby="body-title">
      <div className="body-head">
        <h2 id="body-title">النص الكامل مترجماً</h2>
        <label className="toggle">
          <input type="checkbox" checked={parallel} onChange={(e) => setParallel(e.target.checked)} />
          عرض الأصل الإنجليزي بجوار الترجمة
        </label>
      </div>
      {body.map((p, i) => (
        <div key={i} id={`p${i + 1}`} className={`para${parallel ? " parallel" : ""}`}>
          <a className="num" href={`#p${i + 1}`} aria-label={`الفقرة ${i + 1}`}>{i + 1}</a>
          <div className="ar">
            <p><Ar text={p.ar} /></p>
            <button type="button" className="report" onClick={() => setReporting(reporting === i ? null : i)}
                    aria-expanded={reporting === i}>
              أبلغ عن خطأ في ترجمة هذه الفقرة
            </button>
            {reporting === i && <FeedbackForm docId={docId} paragraph={i} />}
          </div>
          {parallel && <div className="en" lang="en" dir="ltr"><p>{p.en}</p></div>}
        </div>
      ))}
    </section>
  );
}

export function FeedbackForm({ docId, paragraph }: { docId: number; paragraph?: number }) {
  const [state, action, pending] = useActionState<FeedbackState, FormData>(sendFeedback, null);
  if (state?.ok) return <p className="notice ok" role="status">{state.message}</p>;
  return (
    <form action={action} className="feedback-form">
      <input type="hidden" name="document_id" value={docId} />
      {paragraph !== undefined && <input type="hidden" name="paragraph_index" value={paragraph} />}
      <label className="ui" htmlFor={`fb-${paragraph ?? "all"}`}>ما الخطأ الذي لاحظته؟</label>
      <textarea id={`fb-${paragraph ?? "all"}`} name="message" required minLength={3} maxLength={2000} />
      {state && !state.ok && <p className="notice error" role="alert">{state.message}</p>}
      <div><button className="btn secondary" disabled={pending}>{pending ? "جارٍ الإرسال" : "أرسل البلاغ"}</button></div>
    </form>
  );
}
