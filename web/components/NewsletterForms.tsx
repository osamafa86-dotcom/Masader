"use client";
import { useActionState } from "react";
import {
  confirmAction, savePrefsAction, subscribeAction, unsubscribeAction, type NlState,
} from "@/app/newsletter-actions";
import type { Subscription, TopicRow } from "@/lib/types";

type Choices = { topics: TopicRow[]; regions: TopicRow[]; sources: { slug: string; name_ar: string }[] };

function Note({ state }: { state: NlState }) {
  if (!state || !state.message) return null;
  return <p className={`notice ${state.ok ? "ok" : "error"}`} role={state.ok ? "status" : "alert"}>{state.message}</p>;
}

function Preferences({ choices, current }: { choices: Choices; current?: Subscription }) {
  const has = (list: string[] | undefined, v: string) => !!list?.includes(v);
  return (
    <>
      <fieldset>
        <legend>الموضوعات والمناطق التي تهمك</legend>
        <p className="ui muted" style={{ margin: 0 }}>اتركها كلها فارغة لتصلك النشرة كاملة.</p>
        <div className="checks">
          {[...choices.topics, ...choices.regions].map((t) => (
            <label key={t.slug}><input type="checkbox" name="topics" value={t.slug} defaultChecked={has(current?.topics, t.slug)} />{t.name_ar}</label>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend>مصادر بعينها</legend>
        <div className="checks">
          {choices.sources.map((s) => (
            <label key={s.slug}><input type="checkbox" name="sources" value={s.slug} defaultChecked={has(current?.sources, s.slug)} />{s.name_ar}</label>
          ))}
        </div>
      </fieldset>
      <div className="field">
        <label htmlFor="keywords">كلمات مفتاحية للتنبيه</label>
        <input id="keywords" name="keywords" placeholder="مثل: الردع، القطب الشمالي، Taiwan" defaultValue={current?.keywords.join("، ")} />
      </div>
    </>
  );
}

export function SubscribeForm({ choices }: { choices: Choices }) {
  const [state, action, pending] = useActionState<NlState, FormData>(subscribeAction, null);
  if (state?.ok) return <Note state={state} />;
  return (
    <form action={action}>
      <div className="field">
        <label htmlFor="email">بريدك الإلكتروني</label>
        <input id="email" name="email" type="email" required dir="ltr" autoComplete="email" />
      </div>
      <details style={{ marginBottom: "1rem" }}>
        <summary className="ui">خصّص النشرة (اختياري)</summary>
        <div style={{ marginTop: "1rem" }}><Preferences choices={choices} /></div>
      </details>
      <Note state={state} />
      <button className="btn accent" disabled={pending}>{pending ? "جارٍ الإرسال" : "اشترك"}</button>
    </form>
  );
}

export function ConfirmForm({ token }: { token: string }) {
  const [state, action, pending] = useActionState<NlState, FormData>(confirmAction, null);
  if (state?.ok) return <><Note state={state} /><a href={`/subscribe/manage?token=${encodeURIComponent(token)}`}>اختر الموضوعات التي تهمك</a></>;
  return (
    <form action={action}>
      <input type="hidden" name="token" value={token} />
      <Note state={state} />
      <button className="btn accent" disabled={pending}>تأكيد الاشتراك</button>
    </form>
  );
}

export function ManageForm({ token, sub, choices }: { token: string; sub: Subscription; choices: Choices }) {
  const [state, action, pending] = useActionState<NlState, FormData>(savePrefsAction, null);
  return (
    <form action={action}>
      <input type="hidden" name="token" value={token} />
      <Preferences choices={choices} current={state?.sub ?? sub} />
      <Note state={state} />
      <button className="btn" disabled={pending}>حفظ اختياراتي</button>
    </form>
  );
}

export function UnsubscribeForm({ token }: { token: string }) {
  const [state, action, pending] = useActionState<NlState, FormData>(unsubscribeAction, null);
  if (state?.ok) return <Note state={state} />;
  return (
    <form action={action}>
      <input type="hidden" name="token" value={token} />
      <Note state={state} />
      <button className="btn danger" disabled={pending}>ألغِ اشتراكي</button>
    </form>
  );
}
