const dateFmt = new Intl.DateTimeFormat("ar-u-nu-latn", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

export function arDate(iso: string | null | undefined): string {
  if (!iso) return "";
  return dateFmt.format(new Date(iso));
}

export function authorsLine(authors: string[]): string {
  if (!authors.length) return "";
  if (authors.length === 1) return authors[0];
  return `${authors.slice(0, -1).join("، ")} و${authors[authors.length - 1]}`;
}

export function readingMinutes(words: number): number {
  return Math.max(1, Math.round(words / 230));
}

export const SITE_NAME = process.env.NEXT_PUBLIC_SITE_NAME ?? "مرصد";
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
