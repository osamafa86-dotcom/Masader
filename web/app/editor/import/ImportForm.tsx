"use client";
import { useActionState } from "react";
import { importItem, type ActionResult } from "../actions";

export function ImportForm({ sources }: { sources: { slug: string; name_ar: string }[] }) {
  const [state, action, pending] = useActionState<ActionResult, FormData>(importItem, null);
  return (
    <form action={action}>
      <div className="field"><label htmlFor="url">الرابط</label><input id="url" name="url" type="url" required dir="ltr" placeholder="https://" /></div>
      <div className="field">
        <label htmlFor="source_slug">المصدر</label>
        <select id="source_slug" name="source_slug" required defaultValue="studies-in-intelligence">
          {sources.map((s) => <option key={s.slug} value={s.slug}>{s.name_ar}</option>)}
        </select>
      </div>
      <div className="field"><label htmlFor="title">العنوان الأصلي (اختياري)</label><input id="title" name="title" dir="ltr" /></div>
      {state && !state.ok && <p className="notice error" role="alert">{state.message}</p>}
      <button className="btn" disabled={pending}>{pending ? "جارٍ الاستيراد" : "استورد المادة"}</button>
    </form>
  );
}
