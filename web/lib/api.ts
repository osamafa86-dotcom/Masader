import "server-only";
import type { ArticleCard, ArticleDetail, AuthorPage, DossierCard, DossierPage, GlossaryRow, Issue, Page, Related, SearchPage, SourceRow, Topics, TrendStats } from "./types";

export const ENGINE_URL = process.env.ENGINE_URL ?? "http://127.0.0.1:8000";
const REVALIDATE = Number(process.env.PUBLIC_REVALIDATE_SECONDS ?? 60);

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function get<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const url = new URL(path, ENGINE_URL);
  for (const [k, v] of Object.entries(params ?? {})) if (v !== undefined && v !== "") url.searchParams.set(k, String(v));
  const res = await fetch(url, { next: { revalidate: REVALIDATE, tags: ["public"] } });
  if (!res.ok) throw new ApiError(res.status, `${res.status} ${url.pathname}`);
  return res.json() as Promise<T>;
}

export type ArticleFilters = { topic?: string; region?: string; source?: string; doc_type?: string; page?: number; per_page?: number };

export const api = {
  articles: (f: ArticleFilters = {}) => get<Page<ArticleCard>>("/api/articles", f),
  article: (id: number) => get<ArticleDetail>(`/api/articles/${id}`),
  sources: () => get<SourceRow[]>("/api/sources"),
  topics: () => get<Topics>("/api/topics"),
  search: (q: string, page = 1, mode: "keyword" | "semantic" = "keyword") => get<SearchPage>("/api/search", { q, page, mode }),
  dossiers: () => get<DossierCard[]>("/api/dossiers"),
  mostRead: () => get<(ArticleCard & { views: number })[]>("/api/most-read"),
  dossier: (slug: string) => get<DossierPage>(`/api/dossiers/${encodeURIComponent(slug)}`),
  trendMonths: () => get<{ month: string; report: boolean }[]>("/api/trends/months"),
  trend: (month: string) => get<TrendStats>(`/api/trends/${encodeURIComponent(month)}`),
  related: (id: number) => get<Related>(`/api/articles/${id}/related`),
  author: (slug: string, page = 1) => get<AuthorPage>(`/api/authors/${encodeURIComponent(slug)}`, { page }),
  issues: (slug: string) => get<Issue[]>(`/api/sources/${encodeURIComponent(slug)}/issues`),
  issue: (slug: string, volume: string, issue: string) =>
    get<{ volume: string; issue: string; items: ArticleCard[] }>(`/api/sources/${encodeURIComponent(slug)}/issues/${encodeURIComponent(volume)}/${encodeURIComponent(issue)}`),
  glossary: (q?: string) => get<GlossaryRow[]>("/api/glossary", { q }),
};

/** Uncached call for the newsletter flows (each response depends on a personal token). */
export async function engine<T>(path: string, init: RequestInit = {}): Promise<{ status: number; data: T | null }> {
  const { clientHeaders } = await import("./clientip");
  const res = await fetch(`${ENGINE_URL}${path}`, {
    ...init, cache: "no-store",
    headers: { "content-type": "application/json", ...(await clientHeaders()), ...(init.headers ?? {}) },
  });
  let data: T | null = null;
  try { data = (await res.json()) as T; } catch { /* empty body */ }
  return { status: res.status, data };
}
