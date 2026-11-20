"use client";
import { useActionState } from "react";
import { login, type ActionResult } from "../actions";

export function LoginForm() {
  const [state, action, pending] = useActionState<ActionResult, FormData>(login, null);
  return (
    <form action={action}>
      <div className="field"><label htmlFor="email">البريد الإلكتروني</label><input id="email" name="email" type="email" required autoComplete="username" dir="ltr" defaultValue={state?.email} key={state?.email ?? ""} /></div>
      <div className="field"><label htmlFor="password">كلمة المرور</label><input id="password" name="password" type="password" required autoComplete="current-password" dir="ltr" /></div>
      {state && !state.ok && <p className="notice error" role="alert">{state.message}</p>}
      <button className="btn" disabled={pending}>{pending ? "جارٍ الدخول" : "ادخل"}</button>
    </form>
  );
}
