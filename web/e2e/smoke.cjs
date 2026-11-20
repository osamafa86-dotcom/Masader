// End-to-end smoke test against a running site + engine loaded with `marsad demo`.
// Usage: BASE_URL=http://localhost:3000 EDITOR_EMAIL=... EDITOR_PASSWORD=... node e2e/smoke.cjs
const { chromium } = require("playwright");
const assert = require("node:assert/strict");

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const EMAIL = process.env.EDITOR_EMAIL ?? "admin@example.org";
const PASSWORD = process.env.EDITOR_PASSWORD ?? "demo-password-123";
const FULL = "الردع في المنطقة الرمادية";
const SUMMARY_ONLY = "الإمداد البحري بعد مناورات المحيط الهادئ";

async function step(name, fn) {
  process.stdout.write(`- ${name} ... `);
  await fn();
  console.log("ok");
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.on("dialog", (d) => d.accept("اختبار آلي"));
  let fullUrl, summaryUrl;

  await step("home lists published items, newest first", async () => {
    await page.goto(BASE + "/");
    const titles = await page.locator(".entry h2").allInnerTexts();
    assert.ok(titles.length >= 3, `expected 3 items, got ${titles.length}`);
    fullUrl = await page.getByRole("link", { name: FULL }).getAttribute("href");
    summaryUrl = await page.getByRole("link", { name: SUMMARY_ONLY }).getAttribute("href");
  });

  await step("full-text item shows numbered paragraphs and the parallel view", async () => {
    await page.goto(BASE + fullUrl);
    assert.equal(await page.locator(".para").count(), 7);
    assert.equal(await page.locator(".para .en").count(), 0);
    await page.getByLabel("عرض الأصل الإنجليزي بجوار الترجمة").check();
    assert.equal(await page.locator(".para .en").count(), 7);
  });

  await step("reader can report an error on a paragraph", async () => {
    await page.locator("#p2 .report").click();
    await page.locator("#p2 textarea").fill("الرقم في هذه الفقرة يحتاج تحققاً");
    await page.locator("#p2").getByRole("button", { name: "أرسل البلاغ" }).click();
    await page.locator("#p2").getByText("وصل بلاغك").waitFor();
  });

  await step("summary-only item never shows a body", async () => {
    await page.goto(BASE + summaryUrl);
    assert.equal(await page.locator(".para").count(), 0);
    await page.getByText("ملخص تحليلي بالعربية من إعداد المنصة").first().waitFor();
  });

  await step("Arabic search ignores the definite article and hamza", async () => {
    await page.goto(BASE + "/search?q=" + encodeURIComponent("ردع"));
    await page.getByRole("link", { name: FULL }).waitFor();
  });

  await step("editor login rejects a wrong password", async () => {
    await page.goto(BASE + "/editor");
    await page.waitForURL(/\/editor\/login/);
    await page.getByLabel("البريد الإلكتروني").fill(EMAIL);
    await page.getByLabel("كلمة المرور").fill("wrong-password");
    await page.getByRole("button", { name: "ادخل" }).click();
    await page.getByText("غير صحيحة").waitFor();
  });

  await step("editor takes an item down and publishes it again", async () => {
    await page.getByLabel("كلمة المرور").fill(PASSWORD);
    await page.getByRole("button", { name: "ادخل" }).click();
    await page.waitForURL(BASE + "/editor");
    const id = summaryUrl.split("/").pop();
    await page.goto(`${BASE}/editor/items/${id}`);
    await page.getByRole("button", { name: "إزالة من الموقع" }).click();
    await page.getByText("أُزيلت المادة من الموقع").waitFor();
    const gone = await page.request.get(BASE + summaryUrl);
    assert.equal(gone.status(), 404);

    await page.getByLabel("السطر التعريفي").fill("سطر تعريفي عدّله المحرر في الاختبار");
    await page.getByRole("button", { name: "نشر" }).click();
    await page.getByText("نُشرت المادة").waitFor();
    await page.goto(BASE + summaryUrl);
    await page.getByText("سطر تعريفي عدّله المحرر في الاختبار").waitFor();
    await page.getByText("مراجَعة بشرياً").first().waitFor();
  });

  await step("reader report reaches the editor and can be resolved", async () => {
    await page.goto(BASE + "/editor/feedback");
    const reports = page.locator("li.entry", { hasText: "الرقم في هذه الفقرة يحتاج تحققاً" });
    await reports.first().waitFor();
    const before = await reports.count();
    await reports.first().getByRole("button", { name: "تمت المعالجة" }).click();
    await page.waitForFunction(([n, t]) => [...document.querySelectorAll("li.entry")].filter((e) => e.textContent.includes(t)).length === n - 1,
      [before, "الرقم في هذه الفقرة يحتاج تحققاً"]);
  });

  await browser.close();
  console.log("smoke test passed");
})().catch((e) => {
  console.error("\nFAILED:", e.message);
  process.exit(1);
});
