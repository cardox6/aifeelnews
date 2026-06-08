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

export type ArticleFilterParams = {
  skip?: number;
  limit?: number;
  sentiment_label?: string;
  category?: string;
  source_id?: number;
  search?: string;
};

/**
 * Fetch articles from the canonical filtered endpoint `/api/v1/articles/`.
 *
 * Query params are serialised via URLSearchParams; empty / undefined values
 * are skipped so the backend gets a clean URL. Order is server-stable
 * (`published_at desc, id desc`).
 */
export async function fetchArticles(
  params: ArticleFilterParams = {}
): Promise<ArticleDto[]> {
  const qs = new URLSearchParams();
  if (params.skip !== undefined) qs.set("skip", String(params.skip));
  if (params.limit !== undefined) qs.set("limit", String(params.limit));
  if (params.sentiment_label) qs.set("sentiment_label", params.sentiment_label);
  if (params.category) qs.set("category", params.category);
  if (params.source_id !== undefined && params.source_id !== null) {
    qs.set("source_id", String(params.source_id));
  }
  if (params.search) qs.set("search", params.search);

  const queryString = qs.toString();
  const url = queryString
    ? `${API_BASE}/api/v1/articles/?${queryString}`
    : `${API_BASE}/api/v1/articles/`;

  const res = await fetch(url);

  if (!res.ok) {
    const errorText = await res.text();
    console.error("API Error:", errorText);
    throw new Error(`Failed to fetch articles: ${res.status} ${errorText}`);
  }

  return await res.json();
}

/**
 * Fetch a single article by ID. Used by BookmarksView to hydrate bookmarked
 * article details after listing the user's bookmarks.
 */
export async function fetchArticleById(id: number): Promise<ArticleDto> {
  const res = await fetch(`${API_BASE}/api/v1/articles/${id}`);
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch article ${id}: ${res.status} ${errorText}`);
  }
  return await res.json();
}

// ---------------------------------------------------------------------------
// Sources
// ---------------------------------------------------------------------------

export type SourceDto = {
  id: number;
  name: string;
};

export async function fetchSources(): Promise<SourceDto[]> {
  const res = await fetch(`${API_BASE}/api/v1/sources/`);
  if (!res.ok) {
    throw new Error(`Failed to fetch sources: ${res.status}`);
  }
  return await res.json();
}

// ---------------------------------------------------------------------------
// Bookmarks
// ---------------------------------------------------------------------------

export type BookmarkDto = {
  id: number;
  user_id: number;
  article_id: number;
  created_at?: string;
};

export class AuthExpiredError extends Error {
  constructor(message = "Authentication expired") {
    super(message);
    this.name = "AuthExpiredError";
  }
}

/**
 * Create a bookmark for the given article.
 *
 * Treats 409 (already bookmarked) as silent success — the caller's optimistic
 * UI was already correct. Throws ``AuthExpiredError`` on 401 so the caller
 * can sign-out + re-prompt.
 */
export async function createBookmark(
  articleId: number,
  idToken: string
): Promise<BookmarkDto | null> {
  const res = await fetch(`${API_BASE}/api/v1/bookmarks/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${idToken}`,
    },
    body: JSON.stringify({ article_id: articleId }),
  });

  if (res.status === 409) {
    return null; // already bookmarked — keep optimistic state
  }
  if (res.status === 401) {
    throw new AuthExpiredError();
  }
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to create bookmark: ${res.status} ${errorText}`);
  }
  return await res.json();
}

export async function listBookmarks(idToken: string): Promise<BookmarkDto[]> {
  const res = await fetch(`${API_BASE}/api/v1/bookmarks/`, {
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (res.status === 401) {
    throw new AuthExpiredError();
  }
  if (!res.ok) {
    throw new Error(`Failed to list bookmarks: ${res.status}`);
  }
  return await res.json();
}

/**
 * Delete a bookmark. 404 is treated as silent success — the bookmark is
 * already gone, which is exactly what the caller wanted.
 */
export async function deleteBookmark(
  bookmarkId: number,
  idToken: string
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/bookmarks/${bookmarkId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${idToken}` },
  });

  if (res.status === 401) {
    throw new AuthExpiredError();
  }
  if (res.status === 404) {
    return; // already gone — silent success
  }
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(
      `Failed to delete bookmark ${bookmarkId}: ${res.status} ${errorText}`
    );
  }
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

export type EntitySentimentTimelinePoint = {
  date: string;
  entity_name: string;
  entity_type: string;
  article_count: number;
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

export function fetchEntitySentimentTimeline(days = 30, entityType?: string, limit = 8): Promise<EntitySentimentTimelinePoint[]> {
  let params = `?days=${days}&limit=${limit}`;
  if (entityType) params += `&entity_type=${entityType}`;
  return fetchAnalytics(`/entities/sentiment-timeline${params}`);
}

export function fetchNlpCategories(days = 30, limit = 20): Promise<NlpCategoryBreakdown[]> {
  return fetchAnalytics(`/categories/nlp?days=${days}&limit=${limit}`);
}

// ---------------------------------------------------------------------------
// PostgreSQL analytics (advanced SQL: window functions, CTEs, GROUPING SETS).
//
// Unlike the BigQuery analytics above, these query the operational Postgres
// directly, so they return data in demo/assessment mode without GCP BigQuery.
// Shapes mirror app/crud/analytics.py exactly.
// ---------------------------------------------------------------------------

export type RollingSentimentPoint = {
  day: string;
  article_count: number;
  avg_sentiment: number;
  rolling_avg: number;
};

export type SourceRanked = {
  source_name: string;
  article_count: number;
  avg_sentiment: number;
  sentiment_stddev: number | null;
  positivity_rank: number;
};

export type SentimentBreakdownRow = {
  category: string;
  sentiment_label: string;
  article_count: number;
  avg_sentiment: number | null;
  is_category_total: number;
  is_label_total: number;
};

export type EntityMomentum = {
  entity_name: string;
  entity_type: string;
  recent_mentions: number;
  previous_mentions: number;
  growth_pct: number;
};

export type CategoryDailyPoint = {
  day: string;
  category: string;
  article_count: number;
  avg_sentiment: number | null;
  cumulative_articles: number;
};

async function fetchDbAnalyticsRaw(path: string): Promise<Record<string, unknown>[]> {
  const res = await fetch(`${API_BASE}/api/v1/db-analytics${path}`);
  if (!res.ok) throw new Error(`DB analytics request failed: ${res.status}`);
  const data = await res.json();
  if (!Array.isArray(data)) return [];
  return data;
}

/**
 * Postgres `ROUND(x::numeric, n)` serializes to a JSON *string* (e.g. "0.14"),
 * not a number — psycopg2 maps `Numeric` to `Decimal`, which FastAPI renders as
 * a string. Coerce the named decimal fields back to `number` (null-safe) at the
 * fetch boundary so chart/KPI code can rely on the declared `number` types.
 */
function coerceNumeric<T>(rows: Record<string, unknown>[], fields: string[]): T[] {
  return rows.map((row) => {
    const out: Record<string, unknown> = { ...row };
    for (const f of fields) {
      const v = out[f];
      out[f] = v === null || v === undefined ? null : Number(v);
    }
    return out as T;
  });
}

export async function fetchSentimentRolling(days = 30, window = 7): Promise<RollingSentimentPoint[]> {
  const rows = await fetchDbAnalyticsRaw(`/sentiment/rolling?days=${days}&window=${window}`);
  return coerceNumeric<RollingSentimentPoint>(rows, ['avg_sentiment', 'rolling_avg']);
}

export async function fetchSourcesRanked(days = 30): Promise<SourceRanked[]> {
  const rows = await fetchDbAnalyticsRaw(`/sources/ranked?days=${days}`);
  return coerceNumeric<SourceRanked>(rows, ['avg_sentiment', 'sentiment_stddev']);
}

export async function fetchSentimentBreakdown(days = 30): Promise<SentimentBreakdownRow[]> {
  const rows = await fetchDbAnalyticsRaw(`/sentiment/breakdown?days=${days}`);
  return coerceNumeric<SentimentBreakdownRow>(rows, ['avg_sentiment']);
}

export async function fetchEntityMomentum(days = 14): Promise<EntityMomentum[]> {
  const rows = await fetchDbAnalyticsRaw(`/entities/momentum?days=${days}`);
  return coerceNumeric<EntityMomentum>(rows, ['growth_pct']);
}

export async function fetchCategoriesDaily(days = 14): Promise<CategoryDailyPoint[]> {
  const rows = await fetchDbAnalyticsRaw(`/categories/daily?days=${days}`);
  return coerceNumeric<CategoryDailyPoint>(rows, ['avg_sentiment']);
}
