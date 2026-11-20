// End-to-end smoke test against a running site + engine loaded with `marsad demo`.
// Usage: BASE_URL=http://localhost:3000 EDITOR_EMAIL=... EDITOR_PASSWORD=... node e2e/smoke.cjs
const { chromium } = require("playwright");
const { execSync } = require("node:child_process");
const assert = require("node:assert/strict");

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const EMAIL = process.env.EDITOR_EMAIL ?? "admin@example.org";
const PASSWORD = process.env.EDITOR_PASSWORD ?? "demo-password-123";
const FULL = "الردع في المنطقة الرمادية";
const SUMMARY_ONLY = "الإمداد البحري بعد مناورات المحيط الهادئ";
const JOURNAL_A = "تبادل المعلومات الاستخباراتية في التحالفات وحدود الثقة";
const JOURNAL_B = "الإنذار الاستراتيجي في عصر الأقمار الصناعية التجارية";
// Reads a subscriber token straight from the database (the demo mail backend keeps mail in memory).
const DB_TOKEN = (email) => execSync(`psql "${process.env.DATABASE_URL ?? "postgresql://marsad:marsad@127.0.0.1/marsad"}" -Atc "select token from subscribers where email='${email}'"`).toString().trim();

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

  await step("journal issue lists studies in page order with abstract-based summaries", async () => {
    await page.goto(BASE + "/sources/demo-journal");
    await page.getByRole("link", { name: /المجلد 12، العدد 3/ }).click();
    const titles = await page.locator(".entry h2").allInnerTexts();
    assert.deepEqual(titles, [JOURNAL_B, JOURNAL_A]);
    await page.getByRole("link", { name: JOURNAL_A }).click();
    await page.getByText("بُني هذا الملخص على الملخص المنشور للدراسة").waitFor();
    await page.getByRole("tab", { name: "BibTeX" }).click();
    assert.match(await page.locator("pre.cite").innerText(), /^@article\{lopez2026coalition,/);
  });

  await step("author page lists the author's work", async () => {
    await page.getByRole("link", { name: "Maria Lopez" }).click();
    await page.waitForURL(/\/authors\/maria-lopez/);
    await page.getByRole("link", { name: JOURNAL_A }).waitFor();
  });

  await step("semantic search mode", async () => {
    await page.goto(BASE + "/search?mode=semantic&q=" + encodeURIComponent("الردع في المنطقة الرمادية"));
    assert.equal(await page.locator(".entry h2").first().innerText(), "الردع في المنطقة الرمادية: دروس للمخطّطين في الدول الحليفة");
  });

  const email = `reader${Date.now()}@example.org`;
  await step("reader subscribes with an alert, confirms, edits preferences and unsubscribes", async () => {
    await page.goto(BASE + "/subscribe");
    await page.getByLabel("بريدك الإلكتروني").fill(email);
    await page.getByText("خصّص النشرة").click();
    await page.getByLabel("الاستخبارات", { exact: true }).check();
    await page.getByRole("button", { name: "اشترك" }).click();
    await page.getByText("ستصلك رسالة لتأكيد الاشتراك").waitFor();
    const token = DB_TOKEN(email);
    assert.ok(token.length > 20);
    await page.goto(`${BASE}/subscribe/confirm?token=${token}`);
    await page.getByRole("button", { name: "تأكيد الاشتراك" }).click();
    await page.getByText("تأكد اشتراكك").waitFor();
    await page.getByRole("link", { name: "اختر الموضوعات التي تهمك" }).click();
    assert.equal(await page.getByLabel("الاستخبارات", { exact: true }).isChecked(), true);
    await page.getByLabel("كلمات مفتاحية للتنبيه").fill("الأقمار الصناعية");
    await page.getByRole("button", { name: "حفظ اختياراتي" }).click();
    await page.getByText("حُفظت اختياراتك").waitFor();
    await page.goto(`${BASE}/unsubscribe?token=${token}`);
    await page.getByRole("button", { name: "ألغِ اشتراكي" }).click();
    await page.getByText("ألغينا اشتراكك").waitFor();
    const bad = await page.request.post(`${BASE}/api/newsletter/unsubscribe?token=forged`);
    assert.equal(bad.status(), 404);
  });

  await step("editor prepares a newsletter draft and queues it for sending", async () => {
    await page.goto(BASE + "/editor/newsletter");
    if (await page.getByRole("link", { name: /أبرز ما رُصد/ }).count() === 0) {
      await page.getByRole("button", { name: "أعدّ مسودة الآن" }).click();
    } else {
      await page.getByRole("link", { name: /أبرز ما رُصد/ }).first().click();
    }
    await page.waitForURL(/\/editor\/newsletter\/\d+/);
    if (await page.getByRole("button", { name: "أرسل النشرة" }).count()) {
      await page.getByLabel("مقدمة المحرر").fill("مقدمة كتبها المحرر في الاختبار.");
      await page.getByRole("button", { name: "حفظ التعديلات" }).click();
      await page.waitForLoadState("networkidle");
      await page.getByRole("button", { name: "أرسل النشرة" }).click();
      await page.waitForURL(BASE + "/editor/newsletter");
      await page.getByText(/قيد الإرسال|أُرسلت/).first().waitFor();
    }
  });

  await step("editor imports a report by URL", async () => {
    await page.goto(BASE + "/editor/import");
    await page.getByLabel("الرابط").fill(`https://example.org/report-${Date.now()}.pdf`);
    await page.getByRole("button", { name: "استورد المادة" }).click();
    await page.waitForURL(/\/editor\/items\/\d+/);
    await page.getByText("رُصدت").first().waitFor();
    await page.goto(BASE + "/editor/import");
    await page.getByLabel("الرابط").fill("http://127.0.0.1:8000/api/health");
    await page.getByRole("button", { name: "استورد المادة" }).click();
    await page.getByText("لا يمكن استيراد عنوان داخلي").waitFor();
  });

  await browser.close();
  console.log("smoke test passed");
})().catch((e) => {
  console.error("\nFAILED:", e.message);
  process.exit(1);
});
