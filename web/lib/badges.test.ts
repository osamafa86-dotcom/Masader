// The level badge says what was published and on what right, in the letters the methodology defines.
import { test } from "node:test";
import assert from "node:assert/strict";
import { levelBadge, reviewBadge } from "./badges.ts";

test("full text under an open licence is أ", () => {
  assert.deepEqual(levelBadge({ publish_level: "full", basis: "full_text", rights_level: "a" }),
    { text: "أ · نصّ كامل مترجم", full: true });
});

test("full text by permission is ب", () => {
  assert.deepEqual(levelBadge({ publish_level: "full", basis: "full_text", rights_level: "b" }),
    { text: "ب · نصّ كامل بإذن المصدر", full: true });
});

test("full text with an unknown right carries no letter rather than a guessed one", () => {
  assert.deepEqual(levelBadge({ publish_level: "full", basis: "full_text" }),
    { text: "نصّ كامل مترجم", full: true });
});

test("a summary is ج, and names what it rests on", () => {
  assert.equal(levelBadge({ publish_level: "summary", basis: "full_text", rights_level: "c" }).text, "ج · ملخص من النصّ");
  assert.equal(levelBadge({ publish_level: "summary", basis: "abstract", rights_level: "c" }).text, "ج · ملخص من الملخص المنشور");
  assert.equal(levelBadge({ publish_level: "summary", basis: "title", rights_level: "c" }).text, "ج · عنوان من فهرس العدد");
  // A source that may publish in full but was served as a summary is still labelled by what was served.
  assert.equal(levelBadge({ publish_level: "summary", basis: "full_text", rights_level: "a" }).full, false);
});

test("review state is a word, and machine output is marked as such", () => {
  assert.deepEqual(reviewBadge(true), { text: "مراجَعة بشرياً", machine: false });
  assert.deepEqual(reviewBadge(false), { text: "ترجمة آلية دون مراجعة", machine: true });
});
