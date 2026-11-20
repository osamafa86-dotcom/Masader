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
};

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
  stages: Record<string, number>;
  spent_today_usd: number;
  daily_budget_usd: number;
  open_feedback: number;
  proposed_terms: number;
  sources: { slug: string; name: string; name_ar: string; rights_level: string; last_success_at: string | null; last_fetched_at: string | null; last_error: string | null }[];
};
