import "server-only";
import type { ArticleCard, ArticleDetail, GlossaryRow, Page, SourceRow, Topics } from "./types";

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
  search: (q: string, page = 1) => get<Page<ArticleCard>>("/api/search", { q, page }),
  glossary: (q?: string) => get<GlossaryRow[]>("/api/glossary", { q }),
};
