import { api } from "@/lib/api";
import { arCount, NOUNS } from "@/lib/format";
import { ArticleList, Pager } from "@/components/ArticleList";
import { PageHead } from "@/components/PageHead";

export const dynamic = "force-dynamic";
export const metadata = { title: "البحث" };

function SearchForm({ q, mode }: { q: string; mode: string }) {
  return (
    <form action="/search" role="search" style={{ maxWidth: "var(--main)" }}>
      <div className="inline-form">
        <label htmlFor="sq" className="sr-only">ابحث في المواد المرصودة</label>
        <input id="sq" name="q" type="search" defaultValue={q} minLength={2} required placeholder="كلمة أو عبارة، بالعربية أو بلغة الأصل، أو اسم كاتب" />
        <button className="btn" type="submit">ابحث</button>
      </div>
      <fieldset className="mode-switch" style={{ border: 0, padding: 0 }}>
        <legend className="sr-only">طريقة البحث</legend>
        <label><input type="radio" name="mode" value="keyword" defaultChecked={mode !== "semantic"} /> بالكلمات</label>
        <label><input type="radio" name="mode" value="semantic" defaultChecked={mode === "semantic"} /> بالمعنى، يجد المواد القريبة ولو اختلفت ألفاظها</label>
      </fieldset>
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
        <PageHead kicker="البحث" title="ابحث في المرصد"
          lede="اكتب كلمتين على الأقل. يمكنك البحث بالعربية أو بلغة الأصل أو باسم الكاتب، ويتجاهل البحث الهمزات والتشكيل وأداة التعريف." />
        <SearchForm q="" mode={mode} />
      </>
    );
  }
  const res = await api.search(q, page, mode);
  return (
    <>
      <PageHead kicker="البحث" title={<>نتائج البحث عن «{q}»</>}
        meta={res.total ? `${arCount(res.total, NOUNS.result)}، الأحدث أولاً` : undefined} />
      <SearchForm q={q} mode={mode} />
      {mode === "semantic" && res.mode === "keyword" && (
        <p className="notice" style={{ maxWidth: "var(--main)" }}>البحث بالمعنى غير متاح الآن، فعرضنا نتائج البحث بالكلمات.</p>
      )}
      <div style={{ maxWidth: "var(--main)" }}>
        <ArticleList items={res.items}
          empty={<><strong>لم نجد مواد مطابقة</strong>جرّب كلمة أعمّ، أو المصطلح بلغة الأصل، أو البحث بالمعنى، أو تصفّح <a href="/glossary">المسرد</a>.</>} />
        <Pager page={page} total={res.total} perPage={res.per_page} base={`/search?q=${encodeURIComponent(q)}&mode=${mode}`} />
      </div>
    </>
  );
}
