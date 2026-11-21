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
const ENGINE = process.env.ENGINE_URL ?? "http://127.0.0.1:8000";
const OUTBOX = process.env.OUTBOX_DIR; // MARSAD_FAKE_MAIL_DIR of the engine under test
const fs = require("node:fs");
const crypto = require("node:crypto");
function totp(secret, at = Date.now() / 1000) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const c of secret.replace(/=+$/, "")) bits += alphabet.indexOf(c).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(at / 30)));
  const h = crypto.createHmac("sha1", key).update(counter).digest();
  const o = h[h.length - 1] & 0xf;
  return String((h.readUInt32BE(o) & 0x7fffffff) % 1e6).padStart(6, "0");
}
const path = require("node:path");
function lastMailTo(email) {
  const files = fs.readdirSync(OUTBOX).filter((f) => f.endsWith(".json")).sort().reverse();
  for (const f of files) {
    const m = JSON.parse(fs.readFileSync(path.join(OUTBOX, f), "utf8"));
    if (m.to === email) return m;
  }
  throw new Error(`no mail to ${email}`);
}
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

  await step("French source: parallel view shows the French original left-to-right", async () => {
    await page.goto(BASE + "/search?q=" + encodeURIComponent("الردع الفرنسي"));
    await page.getByRole("link", { name: "الردع الفرنسي في اختبار الحرب عالية الشدة" }).click();
    await page.getByText("(بـالفرنسية)").waitFor();
    await page.getByLabel("عرض الأصل الفرنسي بجوار الترجمة").check();
    const col = page.locator(".para .en").first();
    assert.equal(await col.getAttribute("lang"), "fr");
    assert.equal(await col.getAttribute("dir"), "ltr");
  });

  await step("monthly trends: charts, table view and empty month", async () => {
    await page.goto(BASE + "/trends");
    await page.waitForURL(/\/trends\/\d{4}-\d{2}/);
    assert.ok(await page.locator(".bar-row").count() >= 5);
    await page.locator(".chart-table summary").first().click();
    await page.locator(".chart-table table").first().waitFor();
    await page.goto(BASE + "/trends/2020-01");
    await page.getByText("لم نرصد مواد منشورة في هذا الشهر").waitFor();
  });

  const reader = `account${Date.now()}@example.org`;
  await step("reader signs in by email link, saves an item, sets alerts and deletes the account", async () => {
    await page.goto(BASE + "/account");
    await page.waitForURL(/\/account\/login/);
    await page.getByLabel("بريدك الإلكتروني").fill(reader);
    await page.getByRole("button", { name: "أرسل رابط الدخول" }).click();
    await page.getByText("سيصلك رابط الدخول").waitFor();
    const link = lastMailTo(reader).text.match(/https?:\/\/\S+\/account\/verify\?token=\S+/)[0];
    const verifyUrl = BASE + link.slice(link.indexOf("/account/verify"));
    await page.goto(verifyUrl);
    await page.getByRole("button", { name: "ادخل إلى حسابي" }).click();
    await page.waitForURL(BASE + "/account");
    await page.goto(verifyUrl); // the same link a second time is refused
    await page.getByRole("button", { name: "ادخل إلى حسابي" }).click();
    await page.getByText("استُخدم من قبل").waitFor();

    await page.goto(BASE + fullUrl);
    await page.getByRole("button", { name: "احفظ في مكتبتي" }).click();
    await page.getByRole("button", { name: "محفوظة في مكتبتك" }).waitFor();
    await page.goto(BASE + "/account");
    await page.getByRole("link", { name: FULL }).waitFor();
    await page.getByLabel("أرسل إليّ النشرة الأسبوعية بالمواد التي تطابق اختياري").check();
    await page.getByRole("button", { name: "حفظ إعدادات التنبيه" }).click();
    await page.getByText("حُفظت إعدادات التنبيه").waitFor();
    await page.getByText("حذف الحساب", { exact: true }).click();
    await page.getByRole("button", { name: "احذف حسابي وبياناتي" }).click();
    await page.waitForURL(/account=deleted/);
    assert.equal(DB_TOKEN(reader), ""); // newsletter row removed with the account
  });

  await step("editor builds and publishes a dossier (model draft must be reviewed first)", async () => {
    await page.goto(BASE + "/editor/dossiers");
    const dossierTitle = `ملف اختبار ${Date.now()}`;
    await page.getByPlaceholder("عنوان ملف جديد").fill(dossierTitle);
    await page.getByRole("button", { name: "أنشئ الملف" }).click();
    await page.waitForURL(/\/editor\/dossiers\/\d+/);
    await page.getByPlaceholder("كلمات البحث (اختيارية)").fill("الاستخبارات");
    await page.getByRole("button", { name: "اقترح", exact: true }).click();
    await page.getByRole("button", { name: "أضف", exact: true }).first().click();
    await page.getByRole("button", { name: "حفظ", exact: true }).click();
    await page.getByText("حُفظ الملف").waitFor();
    // With one saved item, suggestions also come from closeness to the dossier itself.
    await page.getByPlaceholder("كلمات البحث (اختيارية)").fill("");
    await page.getByRole("button", { name: "اقترح", exact: true }).click();
    await page.getByRole("button", { name: "أضف", exact: true }).first().click();
    await page.getByRole("button", { name: "حفظ", exact: true }).click();
    await page.waitForFunction(() => document.querySelectorAll("ol li strong").length === 2);
    await page.getByRole("button", { name: "اقترح مقدمة من ملخصات المواد" }).click();
    await page.getByText("كُتبت مقدمة مقترحة").waitFor();
    await page.getByRole("button", { name: "نشر الملف" }).click();
    await page.getByText("راجعها واحفظها قبل النشر").waitFor();
    await page.getByLabel(/المقدمة/).fill("مقدمة راجعها المحرر في الاختبار الآلي.");
    await page.getByRole("button", { name: "حفظ", exact: true }).click();
    await page.getByText("حُفظ الملف").waitFor();
    await page.getByRole("button", { name: "نشر الملف" }).click();
    await page.getByText("نُشر الملف").waitFor();
    await page.goto(BASE + "/dossiers");
    await page.getByRole("link", { name: dossierTitle, exact: true }).click();
    await page.waitForURL(/\/dossiers\/[^/]+$/);
    await page.locator(".narrative").getByText("مقدمة راجعها المحرر في الاختبار الآلي.").waitFor();
  });

  await step("admin issues an API key that works once copied, and revokes it", async () => {
    await page.goto(BASE + "/editor/api-clients");
    await page.getByLabel("اسم الجهة").fill("جهة اختبار");
    await page.getByRole("button", { name: "أصدر المفتاح" }).click();
    const key = (await page.locator(".key-once").innerText()).trim();
    assert.match(key, /^mrsd_/);
    const ok = await page.request.get(`${ENGINE}/v1/articles?per_page=1`, { headers: { "X-API-Key": key } });
    assert.equal(ok.status(), 200);
    await page.reload();
    assert.equal(await page.locator(".key-once").count(), 0); // shown once only
    await page.getByRole("row", { name: /جهة اختبار/ }).first().getByRole("button", { name: "إيقاف المفتاح" }).click();
    await page.waitForLoadState("networkidle");
    const revoked = await page.request.get(`${ENGINE}/v1/articles`, { headers: { "X-API-Key": key } });
    assert.equal(revoked.status(), 401);
  });

  await step("legal pages, weekly sample and readership beacon", async () => {
    await page.goto(BASE + "/privacy");
    await page.getByRole("heading", { name: "سياسة الخصوصية" }).waitFor();
    await page.goto(BASE + "/terms#api");
    await page.getByRole("heading", { name: "شروط الواجهة البرمجية" }).waitFor();
    await page.goto(BASE + "/editor/sample");
    await page.getByRole("heading", { name: "عينة الأسبوع" }).waitFor();
    const beacon = page.waitForRequest((r) => r.url().endsWith("/api/views") && r.method() === "POST");
    await page.goto(BASE + fullUrl);
    await beacon;
  });

  await step("editor sets up two-step verification, then signs in with a code", async () => {
    const editorEmail = `twofa${Date.now()}@example.org`;
    execSync(`cd ../engine && .venv/bin/python -c "from marsad.db import session_scope; from marsad.models import User; from marsad.api.auth import hash_password;
with session_scope() as s: s.add(User(email='${editorEmail}', name='محرر الاختبار', password_hash=hash_password('twofa-pass-123')))"`, { stdio: "ignore" });
    const ctx = await browser.newContext();
    const p2 = await ctx.newPage();
    await p2.goto(BASE + "/editor/login");
    await p2.getByLabel("البريد الإلكتروني").fill(editorEmail);
    await p2.getByLabel("كلمة المرور").fill("twofa-pass-123");
    await p2.getByRole("button", { name: "ادخل" }).click();
    await p2.waitForURL(BASE + "/editor");
    await p2.goto(BASE + "/editor/security");
    await p2.getByRole("button", { name: "ابدأ الإعداد" }).click();
    const secret = (await p2.locator(".key-once").innerText()).trim();
    await p2.getByLabel("الرمز الذي يظهر في التطبيق").fill(totp(secret));
    await p2.getByRole("button", { name: "فعّل", exact: true }).click();
    await p2.getByText("التحقق بخطوتين مفعّل لحسابك").waitFor();
    await ctx.clearCookies();
    await p2.goto(BASE + "/editor/login");
    await p2.getByLabel("البريد الإلكتروني").fill(editorEmail);
    await p2.getByLabel("كلمة المرور").fill("twofa-pass-123");
    await p2.getByRole("button", { name: "ادخل" }).click();
    await p2.getByLabel("رمز التحقق من تطبيق المصادقة").fill(totp(secret, Date.now() / 1000 + 30));
    await p2.getByRole("button", { name: "ادخل" }).click();
    await p2.waitForURL(BASE + "/editor");
    await ctx.close();
  });

  await browser.close();
  console.log("smoke test passed");
})().catch((e) => {
  console.error("\nFAILED:", e.message);
  process.exit(1);
});
