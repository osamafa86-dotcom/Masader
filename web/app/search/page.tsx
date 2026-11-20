import { api } from "@/lib/api";
import { ArticleList, Pager } from "@/components/ArticleList";

export const dynamic = "force-dynamic";
export const metadata = { title: "البحث" };

function ModeSwitch({ q, mode }: { q: string; mode: string }) {
  return (
    <form action="/search" className="mode-switch">
      <input type="hidden" name="q" value={q} />
      <label><input type="radio" name="mode" value="keyword" defaultChecked={mode !== "semantic"} /> بالكلمات</label>
      <label><input type="radio" name="mode" value="semantic" defaultChecked={mode === "semantic"} /> بالمعنى (يجد المواد القريبة ولو اختلفت ألفاظها)</label>
      <button className="btn secondary" type="submit">أعد البحث</button>
    </form>
  );
}

export default async function SearchPage({ searchParams }: { searchParams: Promise<{ q?: string; page?: string; mode?: string }> }) {
  const sp = await searchParams;
  const q = (sp.q ?? "").trim();
  const page = Number(sp.page ?? 1) || 1;
  const mode = sp.mode === "semantic" ? "semantic" : "keyword";
  if (q.length < 2) {
    return (
      <>
        <h1 className="page-title">البحث</h1>
        <p className="page-lede">اكتب كلمتين على الأقل في مربع البحث. يمكنك البحث بالعربية أو بالإنجليزية أو باسم الكاتب.</p>
      </>
    );
  }
  const res = await api.search(q, page, mode);
  return (
    <>
      <h1 className="page-title">نتائج البحث عن «{q}»</h1>
      <ModeSwitch q={q} mode={mode} />
      {mode === "semantic" && res.mode === "keyword" && (
        <p className="notice">البحث بالمعنى غير متاح الآن، فعرضنا نتائج البحث بالكلمات.</p>
      )}
      <p className="page-lede">
        {res.total
          ? `${res.total} مادة. يتجاهل البحث الهمزات والتشكيل وأداة التعريف، فلا داعي لكتابة أكثر من صيغة.`
          : "لم نجد مواد مطابقة. جرّب كلمة أعم، أو المصطلح الإنجليزي، أو تصفح المسرد."}
      </p>
      <ArticleList items={res.items} />
      <Pager page={page} total={res.total} perPage={res.per_page} base={`/search?q=${encodeURIComponent(q)}&mode=${mode}`} />
    </>
  );
}
