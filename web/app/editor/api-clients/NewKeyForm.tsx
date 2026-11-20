"use client";
import { useActionState } from "react";
import { createApiClient, type KeyState } from "../actions";

export function NewKeyForm() {
  const [state, action, pending] = useActionState<KeyState, FormData>(createApiClient, null);
  return (
    <section className="summary-panel" style={{ maxWidth: 1000 }}>
      <h2 style={{ fontSize: "1rem" }}>إصدار مفتاح لمؤسسة</h2>
      {state?.ok && state.client?.key && (
        <div role="status">
          <p className="notice ok">انسخ المفتاح الآن وأرسله إلى المؤسسة بقناة آمنة. لن يظهر مرة أخرى.</p>
          <p className="key-once">{state.client.key}</p>
        </div>
      )}
      <form action={action} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "0 1rem" }}>
        <div className="field"><label htmlFor="name">اسم الجهة</label><input id="name" name="name" required minLength={2} /></div>
        <div className="field"><label htmlFor="organization">المؤسسة الأم</label><input id="organization" name="organization" /></div>
        <div className="field"><label htmlFor="contact_email">بريد التواصل</label><input id="contact_email" name="contact_email" type="email" dir="ltr" /></div>
        <div className="field"><label htmlFor="rate_limit">الحد في الدقيقة</label><input id="rate_limit" name="rate_limit" type="number" min={1} max={6000} defaultValue={60} /></div>
        {state && !state.ok && <p className="notice error" role="alert">{state.message}</p>}
        <div><button className="btn" disabled={pending}>أصدر المفتاح</button></div>
      </form>
    </section>
  );
}
