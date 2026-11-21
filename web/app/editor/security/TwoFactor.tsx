"use client";
import { useState, useTransition } from "react";
import { disableTwoFactor, enableTwoFactor, startTwoFactor } from "../actions";

export function TwoFactor({ enabled: initial }: { enabled: boolean }) {
  const [enabled, setEnabled] = useState(initial);
  const [setup, setSetup] = useState<{ secret: string; qr_svg: string } | null>(null);
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; message: string } | null>(null);
  const [pending, start] = useTransition();

  if (enabled) {
    return (
      <div>
        <p className="notice ok">التحقق بخطوتين مفعّل لحسابك.</p>
        <div className="field"><label htmlFor="off">لتعطيله أدخل رمزاً حالياً من التطبيق</label>
          <input id="off" value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" maxLength={6} dir="ltr" /></div>
        {msg && !msg.ok && <p className="notice error" role="alert">{msg.message}</p>}
        <button className="btn danger" disabled={pending || code.length !== 6} onClick={() => start(async () => {
          const r = await disableTwoFactor(code);
          setMsg(r); if (r.ok) { setEnabled(false); setCode(""); }
        })}>عطّل التحقق بخطوتين</button>
      </div>
    );
  }
  return (
    <div>
      {!setup ? (
        <button className="btn" disabled={pending} onClick={() => start(async () => {
          const r = await startTwoFactor();
          if (r.ok && r.data) setSetup(r.data); else setMsg(r);
        })}>ابدأ الإعداد</button>
      ) : (
        <div>
          <p>امسح الرمز بتطبيق المصادقة، أو أدخل المفتاح يدوياً:</p>
          <div style={{ background: "#fff", display: "inline-block", padding: 8, borderRadius: 4 }} dangerouslySetInnerHTML={{ __html: setup.qr_svg }} />
          <p className="key-once">{setup.secret}</p>
          <div className="field"><label htmlFor="on">الرمز الذي يظهر في التطبيق</label>
            <input id="on" value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" maxLength={6} dir="ltr" autoComplete="one-time-code" /></div>
          <button className="btn accent" disabled={pending || code.length !== 6} onClick={() => start(async () => {
            const r = await enableTwoFactor(code);
            setMsg(r); if (r.ok) { setEnabled(true); setSetup(null); setCode(""); }
          })}>فعّل</button>
        </div>
      )}
      {msg && <p className={`notice ${msg.ok ? "ok" : "error"}`} role="status">{msg.message}</p>}
    </div>
  );
}
