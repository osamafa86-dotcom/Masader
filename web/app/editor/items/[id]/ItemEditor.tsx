"use client";
import Link from "next/link";
import { useMemo, useState, useTransition } from "react";
import type { EditorItem, QAIssue } from "@/lib/types";
import { arDate } from "@/lib/format";
import { itemAction, retranslate, saveItem, type ActionResult } from "../../actions";

const STAGE_AR: Record<string, string> = {
  discovered: "رُصدت", extracted: "استُخرج النص", classified: "صُنّفت", summarized: "لُخّصت", translated: "تُرجمت",
  review: "بانتظار المراجعة", published: "منشورة", rejected: "مرفوضة", failed: "متعثرة",
};
const SEVERITY_AR = { high: "جسيمة", medium: "متوسطة", low: "طفيفة" };
const lines = (v: string) => v.split("\n").map((s) => s.trim()).filter(Boolean);

export function ItemEditor({ initial }: { initial: EditorItem }) {
  const [item, setItem] = useState(initial);
  const tr = item.translation;
  const [title, setTitle] = useState(tr?.title_ar ?? "");
  const [summary, setSummary] = useState(() => ({
    dek_ar: tr?.summary.dek_ar ?? "",
    thesis_ar: tr?.summary.thesis_ar ?? "",
    key_points_ar: (tr?.summary.key_points_ar ?? []).join("\n"),
    evidence_ar: tr?.summary.evidence_ar ?? "",
    recommendations_ar: (tr?.summary.recommendations_ar ?? []).join("\n"),
    significance_ar: tr?.summary.significance_ar ?? "",
  }));
  const [paras, setParas] = useState<string[]>(tr?.paragraphs_ar ?? []);
  const [suggestions, setSuggestions] = useState<Record<number, string>>({});
  const [result, setResult] = useState<ActionResult>(null);
  const [pending, start] = useTransition();

  const issuesBy = useMemo(() => {
    const m = new Map<number, QAIssue[]>();
    for (const i of tr?.qa_report.issues ?? []) m.set(i.paragraph_id, [...(m.get(i.paragraph_id) ?? []), i]);
    return m;
  }, [tr]);
  const notesBy = useMemo(() => new Map((tr?.notes ?? []).map((n) => [n.id, n.note_ar])), [tr]);

  const patch = () => {
    const p: Record<string, unknown> = {};
    if (!tr) return p;
    if (title !== tr.title_ar) p.title_ar = title;
    const s = {
      ...summary,
      key_points_ar: lines(summary.key_points_ar),
      recommendations_ar: lines(summary.recommendations_ar),
    };
    const changedSummary = Object.fromEntries(Object.entries(s).filter(([k, v]) => JSON.stringify(v) !== JSON.stringify(tr.summary[k] ?? (Array.isArray(v) ? [] : ""))));
    if (Object.keys(changedSummary).length) p.summary = changedSummary;
    const changedParas = Object.fromEntries(paras.map((t, i) => [i, t]).filter(([i, t]) => t !== tr.paragraphs_ar?.[i as number]));
    if (Object.keys(changedParas).length) p.paragraphs = changedParas;
    return p;
  };
  const dirty = Object.keys(patch()).length > 0;

  const apply = (r: ActionResult) => {
    setResult(r);
    if (r?.ok && r.item) setItem(r.item);
  };
  const save = () => start(async () => apply(await saveItem(item.id, patch(), item.stage === "published")));
  const act = (a: "publish" | "reject" | "unpublish" | "retry") => start(async () => {
    let reason = "";
    if (a === "reject" || a === "unpublish") {
      reason = window.prompt(a === "reject" ? "سبب الرفض (اختياري)" : "سبب الإزالة، مثل طلب صاحب الحقوق") ?? "";
    }
    if (a === "publish" && dirty) {
      const saved = await saveItem(item.id, patch(), false);
      if (!saved?.ok) return apply(saved);
    }
    apply(await itemAction(item.id, a, reason));
  });
  const suggest = (i: number) => start(async () => {
    const r = await retranslate(item.id, i);
    if (r.ok && r.ar) setSuggestions((s) => ({ ...s, [i]: r.ar! }));
    else setResult({ ok: false, message: r.message ?? "تعذّرت إعادة الترجمة." });
  });

  const field = (key: keyof typeof summary, label: string, rows = 3, hint?: string) => (
    <div className="field">
      <label htmlFor={key}>{label}{hint && <span className="muted"> ({hint})</span>}</label>
      <textarea id={key} rows={rows} value={summary[key]} onChange={(e) => setSummary({ ...summary, [key]: e.target.value })} />
    </div>
  );

  return (
    <div>
      <p className="ui"><Link href="/editor">العودة إلى الصف</Link></p>
      <header className="article-head">
        <div className="ui muted">
          {item.source.name_ar}، رُصدت في {arDate(item.created_at)}. الحالة: <strong>{STAGE_AR[item.stage] ?? item.stage}</strong>
        </div>
        <h1 style={{ fontSize: "var(--s2)" }}>{tr?.title_ar || item.title_en}</h1>
        <bdi className="title-en" lang="en" dir="ltr">{item.title_en}</bdi>
        <div className="badges">
          <span className={`badge${item.max_level === "full" ? " full" : ""}`}>
            {item.max_level === "full" ? "الحقوق تسمح بالنص الكامل" : "الحقوق تسمح بالملخص فقط"}
          </span>
          <span className="badge">حقوق المصدر: {item.source.rights_level.toUpperCase()}{item.source.license ? `، ${item.source.license}` : ""}</span>
          {item.importance && <span className="badge">الأهمية {item.importance} من 5</span>}
          {tr && <span className="badge">الفحص الآلي {tr.qa_report.score ?? "-"}/100</span>}
          {tr && <span className="badge">التكلفة ${tr.cost_usd.toFixed(3)}</span>}
        </div>
        <a className="origin-link" href={item.url} target="_blank" rel="noopener">فتح الأصل</a>
        {item.error && <p className="notice error">{item.error}</p>}
      </header>

      <div className="badges" style={{ position: "sticky", top: 0, background: "var(--paper)", padding: "0.75rem 0", zIndex: 2, borderBottom: "1px solid var(--rule)", marginBottom: "1.5rem" }}>
        {tr && <button className="btn secondary" onClick={save} disabled={pending || !dirty}>حفظ التعديلات</button>}
        {tr && item.stage === "review" && <button className="btn accent" onClick={() => act("publish")} disabled={pending}>نشر</button>}
        {item.stage === "published" && <button className="btn danger" onClick={() => act("unpublish")} disabled={pending}>إزالة من الموقع</button>}
        {["review", "published"].includes(item.stage) && <button className="btn danger" onClick={() => act("reject")} disabled={pending}>رفض</button>}
        {["failed", "rejected"].includes(item.stage) && <button className="btn" onClick={() => act("retry")} disabled={pending}>إعادة المعالجة</button>}
        {item.stage === "published" && <Link className="btn secondary" href={`/articles/${item.id}`} target="_blank">عرض في الموقع</Link>}
        {result && <span className={`notice ${result.ok ? "ok" : "error"}`} role="status" style={{ margin: 0 }}>{result.message}</span>}
      </div>

      {!tr ? <p className="empty">لم تُعدّ الترجمة بعد. ستظهر هنا بعد مرور المادة على خط المعالجة.</p> : (
        <>
          <section className="summary-panel" style={{ maxWidth: 1100 }}>
            <h2>الملخص التحليلي</h2>
            <div className="field"><label htmlFor="title_ar">العنوان العربي</label><input id="title_ar" value={title} onChange={(e) => setTitle(e.target.value)} /></div>
            {field("dek_ar", "السطر التعريفي", 2)}
            {field("thesis_ar", "الأطروحة", 5)}
            {field("key_points_ar", "أبرز النقاط", 6, "نقطة في كل سطر")}
            {field("evidence_ar", "الأدلة والمنهج", 3)}
            {field("recommendations_ar", "التوصيات", 4, "توصية في كل سطر")}
            {field("significance_ar", "أهميتها للباحث", 3)}
            {item.abstract_en && <details><summary className="ui">الملخص الأصلي</summary><p className="latin" lang="en" dir="ltr">{item.abstract_en}</p></details>}
          </section>

          {issuesBy.get(-1)?.map((i, k) => <p key={k} className="notice error">{i.detail_ar}</p>)}

          {paras.length > 0 ? (
            <section>
              <div className="body-head"><h2>النص المترجم</h2><span className="ui muted">{paras.length} فقرة</span></div>
              {item.paragraphs_en.map((en, i) => (
                <div key={i} className="para parallel" id={`p${i + 1}`}>
                  <span className="num">{i + 1}</span>
                  <div className="ar">
                    <label htmlFor={`para-${i}`} className="skip-link">ترجمة الفقرة {i + 1}</label>
                    <textarea id={`para-${i}`} value={paras[i] ?? ""} rows={Math.max(4, Math.ceil((paras[i] ?? "").length / 70))}
                      onChange={(e) => setParas(paras.map((p, j) => (j === i ? e.target.value : p)))}
                      style={{ width: "100%", font: "inherit", padding: "0.6rem", border: `1px solid ${paras[i] !== tr.paragraphs_ar?.[i] ? "var(--magenta)" : "var(--rule)"}`, borderRadius: 4, background: "var(--surface)", color: "var(--ink)" }} />
                    {issuesBy.get(i)?.map((iss, k) => (
                      <p key={k} className={`notice ${iss.severity === "high" ? "error" : ""}`} style={{ margin: "0.4rem 0" }}>
                        مشكلة {SEVERITY_AR[iss.severity]}: {iss.detail_ar}
                      </p>
                    ))}
                    {notesBy.get(i) && <p className="notice" style={{ margin: "0.4rem 0" }}>ملاحظة المترجم: {notesBy.get(i)}</p>}
                    {suggestions[i] && (
                      <div className="notice ok" style={{ margin: "0.4rem 0" }}>
                        <p style={{ fontFamily: "var(--font-naskh)" }}>{suggestions[i]}</p>
                        <button className="btn secondary" onClick={() => { setParas(paras.map((p, j) => (j === i ? suggestions[i] : p))); setSuggestions(({ [i]: _, ...rest }) => rest); }}>استخدم هذا الاقتراح</button>
                      </div>
                    )}
                    <button type="button" className="report" onClick={() => suggest(i)} disabled={pending}>اقترح ترجمة بديلة</button>
                  </div>
                  <div className="en" lang="en" dir="ltr"><p>{en}</p></div>
                </div>
              ))}
            </section>
          ) : (
            <p className="notice">هذه المادة من مصدر محفوظ الحقوق، فيُنشر ملخصها التحليلي فقط ولا يُترجم نصها.</p>
          )}
        </>
      )}
    </div>
  );
}
