export type Tag = { slug: string; name_ar: string };
export type SourceBrief = { slug: string; name: string; name_ar: string; homepage: string; kind: string };

export type ArticleCard = {
  id: number;
  title_ar: string;
  title_en: string;
  dek_ar: string;
  source: SourceBrief;
  authors: string[];
  original_published_at: string | null;
  published_at: string | null;
  publish_level: "full" | "summary";
  human_reviewed: boolean;
  topics: Tag[];
  regions: Tag[];
  doc_type: Tag | null;
  importance: number | null;
  url: string;
  word_count: number;
  basis: "full_text" | "abstract" | "title";
  source_language: string;
  meta: { journal?: string; volume?: string; issue?: string; start_page?: string; end_page?: string; doi?: string; open_access?: boolean };
  authors_detail: { name: string; slug: string }[];
};

export type ArticleDetail = ArticleCard & {
  summary: {
    thesis_ar?: string;
    key_points_ar?: string[];
    evidence_ar?: string;
    recommendations_ar?: string[];
    significance_ar?: string;
    quotes?: { en: string; ar: string }[];
  };
  body: { en: string; ar: string }[] | null;
  license: string | null;
  rights_note: string;
  glossary: { en: string; ar: string; definition_ar: string }[];
  translation: { model: string; prompt_version: string; reviewed_at: string | null };
  citation_original: string;
  citations: { apa: string; chicago: string; bibtex: string; translation: string };
};

export type Related = { items: ArticleCard[]; basis: "semantic" | "tags" };
export type Issue = { volume: string; issue: string; count: number; latest: string | null };
export type AuthorPage = Page<ArticleCard> & { name: string; name_ar: string | null; affiliation: string | null; slug: string; sources: string[] };
export type SearchPage = Page<ArticleCard> & { mode: "keyword" | "semantic" };
export type Subscription = { email: string; confirmed: boolean; active: boolean; topics: string[]; sources: string[]; keywords: string[] };

export type Page<T> = { items: T[]; total: number; page: number; per_page: number; q?: string };

export type SourceRow = SourceBrief & {
  description_ar: string;
  is_active: boolean;
  rights_level: "a" | "b" | "c";
  license: string | null;
  published_count: number;
};

export type TopicRow = { slug: string; name_ar: string; name_en: string; count: number };
export type Topics = { topic: TopicRow[]; region: TopicRow[]; doc_type: TopicRow[] };
export type GlossaryRow = { en: string; ar: string; variants_ar: string[]; definition_ar: string; domain: string };

export type QAIssue = { paragraph_id: number; kind: string; severity: "low" | "medium" | "high"; detail_ar: string; by?: string };

export type EditorItem = {
  id: number;
  stage: string;
  error: string | null;
  attempts: number;
  title_en: string;
  url: string;
  authors: string[];
  source: SourceBrief & { rights_level: string; license: string | null };
  original_published_at: string | null;
  created_at: string;
  importance: number | null;
  doc_type: string | null;
  max_level: "full" | "summary";
  word_count: number;
  abstract_en: string | null;
  meta: Record<string, any>;
  item_license: string | null;
  item_rights_evidence: string | null;
  content_mode: string;
  paragraphs_en: string[];
  topics: Tag[];
  regions: Tag[];
  translation: null | {
    title_ar: string;
    summary: Record<string, any>;
    paragraphs_ar: string[] | null;
    notes: { id: number; note_ar: string }[];
    publish_level: "full" | "summary";
    qa_report: { score: number | null; issues: QAIssue[]; high: number; summary_only?: boolean };
    cost_usd: number;
    model: string;
    human_reviewed: boolean;
    published_at: string | null;
  };
};

export type QueueRow = {
  id: number;
  stage: string;
  title_en: string;
  title_ar: string | null;
  source: SourceBrief;
  importance: number | null;
  max_level: "full" | "summary";
  qa_score: number | null;
  qa_high: number;
  notes: number;
  error: string | null;
  created_at: string;
};

export type Stats = {
  worker: { last_seen: string | null; stale: boolean; last_cycle: Record<string, number> };
  problems: string[];
  stages: Record<string, number>;
  spent_today_usd: number;
  daily_budget_usd: number;
  open_feedback: number;
  proposed_terms: number;
  sources: { slug: string; name: string; name_ar: string; rights_level: string; last_success_at: string | null; last_fetched_at: string | null; last_error: string | null }[];
};

export type DigestRow = {
  id: number; status: "draft" | "sending" | "sent"; subject_ar: string; intro_ar: string;
  period_start: string; period_end: string; document_ids: number[]; sent_at: string | null;
  deliveries: Record<string, number>; items?: QueueRow[];
};

export type DossierCard = { slug: string; title_ar: string; item_count: number; excerpt_ar: string; published_at: string | null; updated_at: string | null };
export type DossierPage = DossierCard & { intro_ar: string; items: (ArticleCard & { note_ar: string })[] };
export type EditorDossier = { id: number; slug: string; title_ar: string; intro_ar: string; intro_is_draft: boolean; status: "draft" | "published"; published_at: string | null; items: (QueueRow & { note_ar: string })[] };

export type TrendRow = { slug: string; name_ar: string; count: number; previous: number; change: number; avg_3m: number };
export type TrendStats = {
  month: string; total: number; previous_total: number; empty: boolean; small_sample: boolean;
  topics: TrendRow[]; regions: TrendRow[]; sources: TrendRow[]; doc_types: TrendRow[];
  rising_topics: TrendRow[]; falling_topics: TrendRow[];
  rising_keywords: { keyword: string; count: number; previous: number }[];
  weeks: { week: number; count: number }[];
  top_items: { id: number; title_ar: string; source: string; importance: number }[];
  report: null | { month: string; status: string; narrative_ar: string; narrative_is_draft: boolean; published_at: string | null };
};

export type AccountMe = { email: string; created_at: string; saved_ids: number[]; alerts: { active: boolean; topics: string[]; sources: string[]; keywords: string[] } };
export type LibraryRow = { document_id: number; note: string; saved_at: string; available: boolean; article: ArticleCard | null };
export type ApiClientRow = { id: number; name: string; organization: string; contact_email: string; key_prefix: string; rate_limit_per_minute: number; is_active: boolean; created_at: string; requests_30d: number; last_used_at: string | null; key?: string };
