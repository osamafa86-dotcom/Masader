"use client";
import { useActionState, useState } from "react";
import { login, type ActionResult } from "../actions";

export function LoginForm() {
  const [state, action, pending] = useActionState<ActionResult, FormData>(login, null);
  // Controlled fields keep what the editor typed when the server asks for the second step.
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const needCode = !!state?.otp;
  return (
    <form action={action}>
      <div className="field"><label htmlFor="email">البريد الإلكتروني</label><input id="email" name="email" type="email" required autoComplete="username" dir="ltr" value={email} onChange={(e) => setEmail(e.target.value)} /></div>
      <div className="field"><label htmlFor="password">كلمة المرور</label><input id="password" name="password" type="password" required autoComplete="current-password" dir="ltr" value={password} onChange={(e) => setPassword(e.target.value)} /></div>
      {needCode && (
        <div className="field">
          <label htmlFor="code">رمز التحقق من تطبيق المصادقة</label>
          <input id="code" name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required autoFocus dir="ltr" />
        </div>
      )}
      {state && !state.ok && <p className="notice error" role="alert">{state.message}</p>}
      <button className="btn" disabled={pending}>{pending ? "جارٍ الدخول" : "ادخل"}</button>
    </form>
  );
}
