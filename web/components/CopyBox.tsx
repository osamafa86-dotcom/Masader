"use client";
import { useState } from "react";

type Format = { key: string; label: string; text: string; ltr: boolean };

export function CitationBox({ formats }: { formats: Format[] }) {
  const [active, setActive] = useState(formats[0].key);
  const [copied, setCopied] = useState<string | null>(null);
  const current = formats.find((f) => f.key === active) ?? formats[0];
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(current.text);
      setCopied(current.key);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      setCopied(null);
    }
  };
  return (
    <div>
      <div role="tablist" aria-label="صيغة الاستشهاد" className="tabs">
        {formats.map((f) => (
          <button key={f.key} id={`cite-tab-${f.key}`} role="tab" type="button" aria-selected={f.key === active}
                  aria-controls="cite-panel" className={`tab${f.key === active ? " on" : ""}`} onClick={() => setActive(f.key)}>{f.label}</button>
        ))}
      </div>
      <div className="cite-box" id="cite-panel" role="tabpanel" aria-labelledby={`cite-tab-${current.key}`}>
        <pre className="cite" data-format={current.key} lang={current.ltr ? "en" : "ar"} dir={current.ltr ? "ltr" : "rtl"}>{current.text}</pre>
        <button type="button" className="btn secondary" onClick={copy}>{copied === current.key ? "نُسخ" : "انسخ"}</button>
      </div>
      <p className="sr-only" role="status">{copied ? "نُسخ الاستشهاد" : ""}</p>
    </div>
  );
}
