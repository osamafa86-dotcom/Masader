// Accessibility audit (axe-core, WCAG 2.1 A/AA rules) of the main public pages in light and dark mode.
// Usage: BASE_URL=http://localhost:3000 node e2e/a11y.cjs
const { chromium } = require("playwright");
const axeSource = require("fs").readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const PAGES = ["/", "/articles/1", "/articles/4", "/sources", "/topics", "/search?q=%D8%B1%D8%AF%D8%B9", "/glossary",
  "/methodology", "/dossiers", "/developers", "/subscribe", "/account/login", "/privacy", "/terms", "/editor/login"];

(async () => {
  const browser = await chromium.launch();
  let total = 0;
  for (const scheme of ["light", "dark"]) {
    const page = await browser.newPage({ colorScheme: scheme });
    for (const path of [...PAGES, "/trends"]) {
      await page.goto(BASE + path, { waitUntil: "networkidle" });
      await page.addScriptTag({ content: axeSource });
      const res = await page.evaluate(async () =>
        // eslint-disable-next-line no-undef
        await axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] } }));
      for (const v of res.violations) {
        total += v.nodes.length;
        console.log(`[${scheme}] ${path}  ${v.impact}  ${v.id}: ${v.help} (${v.nodes.length})`);
        for (const n of v.nodes.slice(0, 2)) console.log(`      ${n.target.join(" ")}  ${(n.failureSummary || "").split("\n")[1] ?? ""}`);
      }
    }
    await page.close();
  }
  await browser.close();
  console.log(total === 0 ? "a11y: no violations" : `a11y: ${total} violating nodes`);
  process.exit(total === 0 ? 0 : 1);
})();
