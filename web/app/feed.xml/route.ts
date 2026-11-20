import { api } from "@/lib/api";
import { SITE_NAME, SITE_URL } from "@/lib/format";

export const dynamic = "force-dynamic";

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

export async function GET() {
  const { items } = await api.articles({ per_page: 50 });
  const entries = items.map((a) => `
    <item>
      <title>${esc(a.title_ar)}</title>
      <link>${SITE_URL}/articles/${a.id}</link>
      <guid isPermaLink="true">${SITE_URL}/articles/${a.id}</guid>
      ${a.published_at ? `<pubDate>${new Date(a.published_at).toUTCString()}</pubDate>` : ""}
      <description>${esc(a.dek_ar)}</description>
      <source url="${esc(a.url)}">${esc(a.source.name)}</source>
      ${a.topics.map((t) => `<category>${esc(t.name_ar)}</category>`).join("")}
    </item>`).join("");
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>${esc(SITE_NAME)}</title>
    <link>${SITE_URL}</link>
    <description>الدراسات الاستراتيجية والأمنية بالعربية</description>
    <language>ar</language>${entries}
  </channel>
</rss>`;
  return new Response(xml, { headers: { "content-type": "application/rss+xml; charset=utf-8" } });
}
