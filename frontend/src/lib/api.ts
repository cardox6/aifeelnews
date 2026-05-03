import { getIdToken } from "./firebase";

const DEFAULT_PROD_API_BASE = "https://aifeelnews-web-813770885946.europe-west1.run.app";
const DEFAULT_LOCAL_API_BASE = "http://127.0.0.1:8002";

const API_BASE = (() => {
  const fromEnv = import.meta.env.VITE_API_BASE_URL?.trim();
  if (fromEnv) return fromEnv.replace(/\/$/, "");

  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host === "localhost" || host === "127.0.0.1") {
      return DEFAULT_LOCAL_API_BASE;
    }
  }

  return DEFAULT_PROD_API_BASE;
})();

// ---------------------------------------------------------------------------
// Article types (mirrors backend ArticleRead / entity schemas)
// ---------------------------------------------------------------------------

export type EntityDto = {
  id: number;
  name: string;
  type: string;
  wikipedia_url: string | null;
  mid: string | null;
};

export type ArticleEntityDto = {
  id: number;
  entity: EntityDto;
  salience: number;
  mention_count: number;
  analyzed_at: string;
};

export type ArticleCategoryDto = {
  id: number;
  name: string;
  confidence: number;
  analyzed_at: string;
};

export type ArticleDto = {
  id: number;
  title: string;
  description: string | null;
  url: string;
  image_url: string | null;
  published_at: string;
  source: {
    id: number;
    name: string;
  };
  sentiment_label?: string | null;
  sentiment_score?: number | null;
  language?: string | null;
  country?: string | null;
  category?: string | null;
  article_entities?: ArticleEntityDto[] | null;
  article_categories?: ArticleCategoryDto[] | null;
};

export async function fetchLatestArticles(limit = 40): Promise<ArticleDto[]> {
  const url = `${API_BASE}/articles/latest?limit=${limit}`;

  const res = await fetch(url);

  if (!res.ok) {
    const errorText = await res.text();
    console.error('API Error:', errorText);
    throw new Error(`Failed to fetch latest articles: ${res.status} ${errorText}`);
  }

  const data = await res.json();
  return data;
}

export async function fetchBookmarks(): Promise<any[]> {
  const token = await getIdToken();
  if (!token) throw new Error("Not authenticated");

  const res = await fetch(`${API_BASE}/bookmarks`, {
    headers: { Authorization: `Bearer ${token}` }
  });

  if (!res.ok) throw new Error("Failed to fetch bookmarks");
  return await res.json();
}

// ---------------------------------------------------------------------------
// Analytics API (BigQuery-powered)
// ---------------------------------------------------------------------------

export type SentimentTrendPoint = {
  date: string;
  sentiment_label: string;
  article_count: number;
  avg_sentiment_score: number;
  avg_magnitude: number | null;
};

export type SourceComparison = {
  source_name: string;
  sentiment_label: string;
  article_count: number;
  avg_sentiment_score: number;
  percentage: number;
};

export type CategoryBreakdown = {
  category: string;
  article_count: number;
  avg_sentiment_score: number;
  avg_magnitude: number | null;
};

export type PipelineRun = {
  run_id: string;
  started_at: string;
  finished_at: string;
  duration_seconds: number;
  articles_fetched: number;
  articles_ingested: number;
  crawl_successful: number | null;
  crawl_failed: number | null;
  include_crawling: boolean;
};

export type TopEntity = {
  entity_name: string;
  entity_type: string;
  article_count: number;
  avg_salience: number | null;
  avg_sentiment_score: number | null;
};

export type EntitySentiment = {
  entity_name: string;
  entity_type: string;
  article_count: number;
  avg_sentiment_score: number | null;
  avg_salience: number | null;
};

export type NlpCategoryBreakdown = {
  category_name: string;
  article_count: number;
  avg_confidence: number | null;
  avg_sentiment_score: number | null;
};

async function fetchAnalytics<T>(path: string): Promise<T[]> {
  const res = await fetch(`${API_BASE}/api/v1/analytics${path}`);
  if (!res.ok) throw new Error(`Analytics request failed: ${res.status}`);
  const data = await res.json();
  // BQ disabled returns { message: "..." } instead of array
  if (!Array.isArray(data)) return [];
  return data;
}

export function fetchSentimentTrends(days = 30, source?: string): Promise<SentimentTrendPoint[]> {
  const params = source ? `?days=${days}&source=${source}` : `?days=${days}`;
  return fetchAnalytics(`/trends${params}`);
}

export function fetchSourceComparison(days = 30): Promise<SourceComparison[]> {
  return fetchAnalytics(`/sources?days=${days}`);
}

export function fetchCategoryBreakdown(days = 30): Promise<CategoryBreakdown[]> {
  return fetchAnalytics(`/categories?days=${days}`);
}

export function fetchPipelineHealth(days = 7): Promise<PipelineRun[]> {
  return fetchAnalytics(`/pipeline?days=${days}`);
}

export function fetchTopEntities(days = 30, entityType?: string, limit = 20): Promise<TopEntity[]> {
  let params = `?days=${days}&limit=${limit}`;
  if (entityType) params += `&entity_type=${entityType}`;
  return fetchAnalytics(`/entities/top${params}`);
}

export function fetchEntitySentiment(days = 30, entityType?: string, limit = 20): Promise<EntitySentiment[]> {
  let params = `?days=${days}&limit=${limit}`;
  if (entityType) params += `&entity_type=${entityType}`;
  return fetchAnalytics(`/entities/sentiment${params}`);
}

export function fetchNlpCategories(days = 30, limit = 20): Promise<NlpCategoryBreakdown[]> {
  return fetchAnalytics(`/categories/nlp?days=${days}&limit=${limit}`);
}
