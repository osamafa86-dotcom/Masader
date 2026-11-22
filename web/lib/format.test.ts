// Unit tests for the Arabic formatting helpers. Run with `npm test` (node --test, built-in type stripping).
import { test } from "node:test";
import assert from "node:assert/strict";
import { arCount, arDate, arMonth, arWeekdayDate, importanceLabel, NOUNS } from "./format.ts";

test("arCount: one and two are words, not numerals", () => {
  assert.equal(arCount(1, NOUNS.item), "مادة واحدة");
  assert.equal(arCount(2, NOUNS.item), "مادتان");
  assert.equal(arCount(1, NOUNS.source), "مصدر واحد");
  assert.equal(arCount(2, NOUNS.source), "مصدران");
});

test("arCount: 3 to 10 take the plural", () => {
  assert.equal(arCount(3, NOUNS.item), "3 مواد");
  assert.equal(arCount(10, NOUNS.item), "10 مواد");
  assert.equal(arCount(7, NOUNS.source), "7 مصادر");
});

test("arCount: 11 to 99 take the singular (tamyiz)", () => {
  assert.equal(arCount(11, NOUNS.item), "11 مادة");
  assert.equal(arCount(14, NOUNS.source), "14 مصدراً");
  assert.equal(arCount(99, NOUNS.item), "99 مادة");
});

test("arCount: hundreds follow the last two digits", () => {
  assert.equal(arCount(100, NOUNS.source), "100 مصدر");
  assert.equal(arCount(103, NOUNS.item), "103 مواد");
  assert.equal(arCount(212, NOUNS.item), "212 مادة");
  assert.equal(arCount(1083, NOUNS.item), "1,083 مادة");
});

test("arCount: words for the article card", () => {
  assert.equal(arCount(9400, NOUNS.word), "9,400 كلمة");
  assert.equal(arCount(7, NOUNS.paragraph), "7 فقرات");
});

test("arCount: zero says there is none", () => {
  assert.equal(arCount(0, NOUNS.item), "لا مواد");
});

test("arMonth and arDate use Levantine month names with Latin digits", () => {
  assert.equal(arMonth("2026-11"), "تشرين الثاني 2026");
  assert.equal(arMonth("2026-01"), "كانون الثاني 2026");
  assert.equal(arDate("2026-11-18T10:00:00Z"), "18 تشرين الثاني 2026");
  assert.equal(arDate(null), "");
});

test("arWeekdayDate computes the weekday instead of trusting a label", () => {
  assert.equal(arWeekdayDate(new Date(Date.UTC(2026, 10, 22))), "الأحد 22 تشرين الثاني 2026");
  assert.equal(arWeekdayDate(new Date(Date.UTC(2026, 10, 19))), "الخميس 19 تشرين الثاني 2026");
});

test("importanceLabel is explicit for screen readers and compact for print", () => {
  assert.deepEqual(importanceLabel(4), { short: "4/5", long: "الأهمية 4 من 5" });
  assert.deepEqual(importanceLabel(null), { short: "–", long: "لم تُقدَّر الأهمية بعد" });
});
