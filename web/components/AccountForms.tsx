"use client";
import Link from "next/link";
import { useActionState, useState, useTransition } from "react";
import { requestLink, saveAlerts, toggleSaved, verifyLink, type AccState } from "@/app/account/actions";
import type { AccountMe, TopicRow } from "@/lib/types";

function Note({ state }: { state: AccState }) {
  if (!state) return null;
  return <p className={`notice ${state.ok ? "ok" : "error"}`} role={state.ok ? "status" : "alert"}>{state.message}</p>;
}

export function LoginForm() {
  const [state, action, pending] = useActionState<AccState, FormData>(requestLink, null);
  if (state?.ok) return <Note state={state} />;
  return (
    <form action={action}>
      <div className="field"><label htmlFor="email">بريدك الإلكتروني</label><input id="email" name="email" type="email" required dir="ltr" autoComplete="email" /></div>
      <Note state={state} />
      <p className="ui muted">نحفظ بريدك ومكتبتك فقط، ويمكنك حذفهما متى شئت. <Link href="/privacy">سياسة الخصوصية</Link></p>
      <button className="btn" disabled={pending}>{pending ? "جارٍ الإرسال" : "أرسل رابط الدخول"}</button>
    </form>
  );
}

export function VerifyForm({ token }: { token: string }) {
  const [state, action, pending] = useActionState<AccState, FormData>(verifyLink, null);
  return (
    <form action={action}>
      <input type="hidden" name="token" value={token} />
      <Note state={state} />
      {state && !state.ok ? <Link href="/account/login">اطلب رابطاً جديداً</Link>
        : <button className="btn accent" disabled={pending}>ادخل إلى حسابي</button>}
    </form>
  );
}

export function SaveButton({ docId, initial, signedIn }: { docId: number; initial: boolean; signedIn: boolean }) {
  const [saved, setSaved] = useState(initial);
  const [pending, start] = useTransition();
  if (!signedIn) return <Link className="btn secondary" href="/account/login">ادخل لحفظ المادة في مكتبتك</Link>;
  return (
    <button type="button" className="btn secondary saved-btn" aria-pressed={saved} disabled={pending}
            onClick={() => start(async () => {
              const r = await toggleSaved(docId, !saved);
              if (r.signedOut) window.location.href = "/account/login";
              else setSaved(r.saved);
            })}>
      {saved ? "محفوظة في مكتبتك" : "احفظ في مكتبتي"}
    </button>
  );
}

export function AlertsForm({ me, topics, regions, sources }:
  { me: AccountMe; topics: TopicRow[]; regions: TopicRow[]; sources: { slug: string; name_ar: string }[] }) {
  const [state, action, pending] = useActionState<AccState, FormData>(saveAlerts, null);
  const a = me.alerts;
  return (
    <form action={action}>
      <label className="toggle" style={{ marginBottom: "1rem" }}>
        <input type="checkbox" name="active" defaultChecked={a.active} /> أرسل إليّ النشرة الأسبوعية بالمواد التي تطابق اختياري
      </label>
      <fieldset>
        <legend>الموضوعات والمناطق</legend>
        <div className="checks">{[...topics, ...regions].map((t) => (
          <label key={t.slug}><input type="checkbox" name="topics" value={t.slug} defaultChecked={a.topics.includes(t.slug)} />{t.name_ar}</label>
        ))}</div>
      </fieldset>
      <fieldset>
        <legend>المصادر</legend>
        <div className="checks">{sources.map((s) => (
          <label key={s.slug}><input type="checkbox" name="sources" value={s.slug} defaultChecked={a.sources.includes(s.slug)} />{s.name_ar}</label>
        ))}</div>
      </fieldset>
      <div className="field"><label htmlFor="keywords">كلمات مفتاحية</label><input id="keywords" name="keywords" defaultValue={a.keywords.join("، ")} /></div>
      <Note state={state} />
      <button className="btn" disabled={pending}>حفظ إعدادات التنبيه</button>
    </form>
  );
}
