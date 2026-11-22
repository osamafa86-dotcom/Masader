// Arabic formatting helpers. Digits stay Latin throughout the site, as in the source data and the design.

// Levantine month names, as used across the design (owner may switch to dual names in one place here).
const MONTHS_AR = ["كانون الثاني", "شباط", "آذار", "نيسان", "أيار", "حزيران", "تموز", "آب", "أيلول", "تشرين الأول", "تشرين الثاني", "كانون الأول"];
const WEEKDAYS_AR = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"];

const num = new Intl.NumberFormat("en-US");

/** "18 تشرين الثاني 2026" (UTC, so a date stored as midnight does not slip a day). */
export function arDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getUTCDate()} ${MONTHS_AR[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

/** "الأحد 22 تشرين الثاني 2026": the weekday is computed, never written by hand. */
export function arWeekdayDate(d: Date): string {
  return `${WEEKDAYS_AR[d.getUTCDay()]} ${arDate(d.toISOString())}`;
}

/** "2026-11" → "تشرين الثاني 2026". */
export function arMonth(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return `${MONTHS_AR[m - 1]} ${y}`;
}

/** Day and month only, for dense list margins: "18 تشرين الثاني". */
export function arDayMonth(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getUTCDate()} ${MONTHS_AR[d.getUTCMonth()]}`;
}

export type Noun = { one: string; two: string; few: string; many: string; hundreds?: string; none: string };

/** Counted nouns. `many` is the accusative singular used after 11–99; `hundreds` the genitive after 100, 200… */
export const NOUNS = {
  item: { one: "مادة واحدة", two: "مادتان", few: "مواد", many: "مادة", none: "لا مواد" },
  source: { one: "مصدر واحد", two: "مصدران", few: "مصادر", many: "مصدراً", hundreds: "مصدر", none: "لا مصادر" },
  dossier: { one: "ملف واحد", two: "ملفان", few: "ملفات", many: "ملفاً", hundreds: "ملف", none: "لا ملفات" },
  issue: { one: "عدد واحد", two: "عددان", few: "أعداد", many: "عدداً", hundreds: "عدد", none: "لا أعداد" },
  minute: { one: "دقيقة واحدة", two: "دقيقتان", few: "دقائق", many: "دقيقة", none: "أقل من دقيقة" },
  paragraph: { one: "فقرة واحدة", two: "فقرتان", few: "فقرات", many: "فقرة", none: "لا فقرات" },
  word: { one: "كلمة واحدة", two: "كلمتان", few: "كلمات", many: "كلمة", none: "لا كلمات" },
  term: { one: "مصطلح واحد", two: "مصطلحان", few: "مصطلحات", many: "مصطلحاً", hundreds: "مصطلح", none: "لا مصطلحات" },
  result: { one: "نتيجة واحدة", two: "نتيجتان", few: "نتائج", many: "نتيجة", none: "لا نتائج" },
  topic: { one: "موضوع واحد", two: "موضوعان", few: "موضوعات", many: "موضوعاً", hundreds: "موضوع", none: "لا موضوعات" },
} satisfies Record<string, Noun>;

/** Arabic number agreement: 1 and 2 are words, 3–10 plural, 11–99 singular, then by the last two digits. */
export function arCount(n: number, noun: Noun): string {
  if (n === 0) return noun.none;
  if (n === 1) return noun.one;
  if (n === 2) return noun.two;
  const r = n % 100;
  const word = r >= 3 && r <= 10 ? noun.few : r >= 11 ? noun.many : (noun.hundreds ?? noun.many);
  return `${num.format(n)} ${word}`;
}

/** Thousands separator with Latin digits: 1,083. */
export function arNumber(n: number): string {
  return num.format(n);
}

export function importanceLabel(level: number | null | undefined): { short: string; long: string } {
  if (level === null || level === undefined) return { short: "–", long: "لم تُقدَّر الأهمية بعد" };
  return { short: `${level}/5`, long: `الأهمية ${level} من 5` };
}

export function authorsLine(authors: string[]): string {
  if (!authors.length) return "";
  if (authors.length === 1) return authors[0];
  return `${authors.slice(0, -1).join("، ")} و${authors[authors.length - 1]}`;
}

export function readingMinutes(words: number): number {
  return Math.max(1, Math.round(words / 230));
}

export const SITE_NAME = process.env.NEXT_PUBLIC_SITE_NAME ?? "مصادر";
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
export const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL ?? "editor@example.org";

export const LANG_AR: Record<string, string> = { en: "الإنجليزية", fr: "الفرنسية", ru: "الروسية", he: "العبرية", zh: "الصينية", de: "الألمانية", es: "الإسبانية", ar: "العربية" };
export const RTL_LANGS = new Set(["ar", "he"]);
