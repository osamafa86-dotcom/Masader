"use client";
import Link from "next/link";
import { useState, useTransition } from "react";
import type { EditorDossier, QueueRow } from "@/lib/types";
import { dossierAction, dossierSuggestions, saveDossier } from "../../actions";

type Item = { id: number; title: string; source: string; note_ar: string };

export function DossierEditor({ initial }: { initial: EditorDossier }) {
  const [d, setD] = useState(initial);
  const [title, setTitle] = useState(initial.title_ar);
  const [intro, setIntro] = useState(initial.intro_ar);
  const [items, setItems] = useState<Item[]>(initial.items.map((i) => ({ id: i.id, title: i.title_ar ?? i.title_en, source: i.source.name_ar, note_ar: i.note_ar })));
  const [q, setQ] = useState("");
  const [sugs, setSugs] = useState<QueueRow[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; message: string } | null>(null);
  const [pending, start] = useTransition();

  const apply = (r: { ok: boolean; message: string; dossier?: EditorDossier }) => {
    setMsg(r);
    if (r.dossier) {
      setD(r.dossier);
      setIntro(r.dossier.intro_ar);
      setItems(r.dossier.items.map((i) => ({ id: i.id, title: i.title_ar ?? i.title_en, source: i.source.name_ar, note_ar: i.note_ar })));
    }
  };
  const save = () => start(async () => apply(await saveDossier(d.id, {
    title_ar: title, intro_ar: intro, items: items.map((i) => ({ document_id: i.id, note_ar: i.note_ar })),
  })));
  const move = (idx: number, delta: number) => {
    const next = [...items];
    const [it] = next.splice(idx, 1);
    next.splice(Math.max(0, Math.min(next.length, idx + delta)), 0, it);
    setItems(next);
  };
  const find = () => start(async () => setSugs(await dossierSuggestions(d.id, q)));

  return (
    <div style={{ maxWidth: 1000 }}>
      <p className="ui"><Link href="/editor/dossiers">كل الملفات</Link>{d.status === "published" && <> ، <Link href={`/dossiers/${d.slug}`} target="_blank">عرض في الموقع</Link></>}</p>
      <div className="field"><label htmlFor="title">عنوان الملف</label><input id="title" value={title} onChange={(e) => setTitle(e.target.value)} /></div>
      <div className="field">
        <label htmlFor="intro">المقدمة {d.intro_is_draft && <span className="muted">(مقترحة من النموذج: راجعها ثم احفظ)</span>}</label>
        <textarea id="intro" rows={8} value={intro} onChange={(e) => setIntro(e.target.value)} />
      </div>
      <div className="badges" style={{ marginBottom: "1.5rem" }}>
        <button className="btn" onClick={save} disabled={pending}>حفظ</button>
        <button className="btn secondary" onClick={() => start(async () => apply(await dossierAction(d.id, "draft-intro")))} disabled={pending || items.length === 0}>اقترح مقدمة من ملخصات المواد</button>
        {d.status === "draft"
          ? <button className="btn accent" onClick={() => start(async () => apply(await dossierAction(d.id, "publish")))} disabled={pending}>نشر الملف</button>
          : <button className="btn danger" onClick={() => start(async () => apply(await dossierAction(d.id, "unpublish")))} disabled={pending}>إخفاء من الموقع</button>}
        {msg && <span className={`notice ${msg.ok ? "ok" : "error"}`} role="status" style={{ margin: 0 }}>{msg.message}</span>}
      </div>

      <h2 style={{ fontSize: "var(--s1)" }}>مواد الملف ({items.length})</h2>
      {items.length === 0 && <p className="empty">ابحث أدناه عن مواد وأضفها.</p>}
      <ol style={{ paddingInlineStart: "1.5rem" }}>
        {items.map((it, i) => (
          <li key={it.id} style={{ marginBottom: "1rem" }}>
            <strong>{it.title}</strong> <span className="ui muted">، {it.source}</span>
            <div className="field" style={{ margin: "0.3rem 0" }}>
              <label htmlFor={`note-${it.id}`} className="skip-link">ملاحظة على المادة</label>
              <input id={`note-${it.id}`} placeholder="ملاحظة المحرر على هذه المادة (اختيارية)" value={it.note_ar}
                     onChange={(e) => setItems(items.map((x) => (x.id === it.id ? { ...x, note_ar: e.target.value } : x)))} />
            </div>
            <div className="badges">
              <button type="button" className="tab" onClick={() => move(i, -1)} disabled={i === 0}>أعلى</button>
              <button type="button" className="tab" onClick={() => move(i, 1)} disabled={i === items.length - 1}>أسفل</button>
              <button type="button" className="tab" onClick={() => setItems(items.filter((x) => x.id !== it.id))}>إزالة</button>
            </div>
          </li>
        ))}
      </ol>

      <section className="summary-panel" style={{ maxWidth: 1000 }}>
        <h2 style={{ fontSize: "1rem" }}>اقتراح مواد</h2>
        <p className="ui muted">بحسب كلمات البحث، وبحسب قرب المواد من مواد الملف الحالية. احفظ بعد الإضافة.</p>
        <div className="search-box" style={{ marginInlineStart: 0, marginBottom: "1rem" }}>
          <label htmlFor="sq" className="skip-link">كلمات البحث</label>
          <input id="sq" value={q} onChange={(e) => setQ(e.target.value)} placeholder="كلمات البحث (اختيارية)" />
          <button type="button" onClick={find} disabled={pending}>اقترح</button>
        </div>
        <ul style={{ listStyle: "none", padding: 0 }}>
          {sugs.filter((s) => !items.some((i) => i.id === s.id)).map((s) => (
            <li key={s.id} className="ui" style={{ display: "flex", justifyContent: "space-between", gap: "1rem", padding: "0.4rem 0", borderBottom: "1px solid var(--rule)" }}>
              <span>{s.title_ar ?? s.title_en} <span className="muted">، {s.source.name_ar}</span></span>
              <button type="button" className="tab" onClick={() => setItems([...items, { id: s.id, title: s.title_ar ?? s.title_en, source: s.source.name_ar, note_ar: "" }])}>أضف</button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
