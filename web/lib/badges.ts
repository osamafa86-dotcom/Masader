// Labels for what an item is, in the three levels of the methodology: أ open licence, ب by permission, ج summary.
// Pure functions so the wording is tested once and shared by every list, the article page and the editor.

type Level = { publish_level: "full" | "summary"; basis: "full_text" | "abstract" | "title"; rights_level?: "a" | "b" | "c" };

const SUMMARY_BASIS: Record<Level["basis"], string> = {
  full_text: "ملخص من النصّ",
  abstract: "ملخص من الملخص المنشور",
  title: "عنوان من فهرس العدد",
};

export function levelBadge(a: Level): { text: string; full: boolean } {
  if (a.publish_level === "full") {
    if (a.rights_level === "b") return { text: "ب · نصّ كامل بإذن المصدر", full: true };
    if (a.rights_level === "a") return { text: "أ · نصّ كامل مترجم", full: true };
    return { text: "نصّ كامل مترجم", full: true };
  }
  return { text: `ج · ${SUMMARY_BASIS[a.basis]}`, full: false };
}

export function reviewBadge(reviewed: boolean): { text: string; machine: boolean } {
  return reviewed ? { text: "مراجَعة بشرياً", machine: false } : { text: "ترجمة آلية دون مراجعة", machine: true };
}
