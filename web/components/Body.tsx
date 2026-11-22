"use client";
import { useActionState, useState } from "react";
import { sendFeedback, type FeedbackState } from "@/app/actions";
import { arCount, NOUNS } from "@/lib/format";
import { Ar } from "./Ar";

type Para = { en: string; ar: string };

const LANG_NAMES: Record<string, string> = { en: "الإنجليزي", fr: "الفرنسي", ru: "الروسي", he: "العبري", zh: "الصيني", de: "الألماني", es: "الإسباني" };

/** The translated text, paragraph by paragraph, with a text switch to set the original beside it. */
export function Body({ docId, body, lang = "en", note }: { docId: number; body: Para[]; lang?: string; note?: string }) {
  const dir = lang === "he" || lang === "ar" ? "rtl" : "ltr";
  const [parallel, setParallel] = useState(false);
  const [reporting, setReporting] = useState<number | null>(null);
  return (
    <>
      <div className="switcher">
        <fieldset className="switch">
          <legend className="sr-only">طريقة عرض النص</legend>
          <label><input type="radio" name="body-view" checked={!parallel} onChange={() => setParallel(false)} />بالعربية وحدها</label>
          <label><input type="radio" name="body-view" checked={parallel} onChange={() => setParallel(true)} />مع الأصل {LANG_NAMES[lang] ?? ""}</label>
        </fieldset>
        <span className="switch-meta">{note && <>{note}<span className="sep" aria-hidden="true">·</span></>}{arCount(body.length, NOUNS.paragraph)}</span>
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
          {parallel && <div className="en" lang={lang} dir={dir}><p>{p.en}</p></div>}
        </div>
      ))}
      <p className="body-foot">الفقرات مرقّمة كما في الأصل، وتحت كل فقرة رابط للإبلاغ عن خطأ يصل إلى المحرّر مباشرة.</p>
    </>
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
