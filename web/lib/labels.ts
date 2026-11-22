import type { SourceRow } from "./types";

/** The three rights levels of the methodology, as letters and as words. */
export const RIGHTS: Record<SourceRow["rights_level"], { letter: string; short: string; long: string }> = {
  a: { letter: "أ", short: "نصّ كامل مترجم", long: "ترخيص مفتوح أو ملك عام: نترجم النص كاملاً ونذكر الترخيص والمؤلف." },
  b: { letter: "ب", short: "نصّ كامل بإذن", long: "إذن مكتوب من المصدر: نترجم النص كاملاً بالشروط التي حددها." },
  c: { letter: "ج", short: "ملخص ورابط فقط", long: "حقوق محفوظة: ملخص تحليلي بصياغتنا مع اقتباسات قصيرة ورابط إلى الأصل." },
};

export const KIND: Record<string, string> = {
  think_tank: "مركز فكر", journal: "مجلة محكّمة", media: "منصة تحليل", government: "جهة حكومية",
};
