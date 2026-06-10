import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  fetchArticles,
  searchArticles,
  fetchArticleById,
  fetchSources,
  createBookmark,
  listBookmarks,
  deleteBookmark,
  AuthExpiredError,
  fetchSentimentTrends,
  fetchSentimentRolling,
  fetchSourcesRanked,
} from "./api";

// vitest.config.ts pins VITE_API_BASE_URL to this value.
const BASE = "http://test.local";

/** Build a minimal fetch Response stand-in. */
function res(
  data: unknown,
  { ok = true, status = 200 }: { ok?: boolean; status?: number } = {},
): Response {
  return {
    ok,
    status,
    json: async () => data,
    text: async () => (typeof data === "string" ? data : JSON.stringify(data)),
  } as Response;
}

let fetchMock: ReturnType<typeof vi.fn>;

/** URL string passed to the Nth fetch call. */
function calledUrl(n = 0): string {
  return fetchMock.mock.calls[n][0] as string;
}

/** RequestInit passed to the Nth fetch call. */
function calledInit(n = 0): RequestInit | undefined {
  return fetchMock.mock.calls[n][1] as RequestInit | undefined;
}

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  // api.ts logs to console.error on non-ok responses; keep test output clean.
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("fetchArticles — query-string assembly", () => {
  it("hits the canonical endpoint with no query string when no params given", async () => {
    fetchMock.mockResolvedValue(res([]));
    await fetchArticles();
    expect(calledUrl()).toBe(`${BASE}/api/v1/articles/`);
  });

  it("keeps skip=0 (it is a meaningful offset, not 'unset')", async () => {
    fetchMock.mockResolvedValue(res([]));
    await fetchArticles({ skip: 0, limit: 20 });
    const url = new URL(calledUrl());
    expect(url.searchParams.get("skip")).toBe("0");
    expect(url.searchParams.get("limit")).toBe("20");
  });

  it("keeps source_id=0 but drops it when null/undefined", async () => {
    fetchMock.mockResolvedValue(res([]));
    await fetchArticles({ source_id: 0 });
    expect(new URL(calledUrl()).searchParams.get("source_id")).toBe("0");

    fetchMock.mockClear();
    await fetchArticles({ source_id: null as unknown as number });
    expect(new URL(calledUrl()).searchParams.has("source_id")).toBe(false);
  });

  it("drops empty-string text filters (falsy)", async () => {
    fetchMock.mockResolvedValue(res([]));
    await fetchArticles({ search: "", category: "", sentiment_label: "" });
    expect(calledUrl()).toBe(`${BASE}/api/v1/articles/`);
  });

  it("serialises every supported filter", async () => {
    fetchMock.mockResolvedValue(res([]));
    await fetchArticles({
      sentiment_label: "positive",
      category: "tech",
      search: "ai",
      published_after: "2026-01-01T00:00:00Z",
      published_before: "2026-02-01T00:00:00Z",
      language: "de",
    });
    const p = new URL(calledUrl()).searchParams;
    expect(p.get("sentiment_label")).toBe("positive");
    expect(p.get("category")).toBe("tech");
    expect(p.get("search")).toBe("ai");
    expect(p.get("published_after")).toBe("2026-01-01T00:00:00Z");
    expect(p.get("published_before")).toBe("2026-02-01T00:00:00Z");
    expect(p.get("language")).toBe("de");
  });

  it("throws with status + body on a non-ok response", async () => {
    fetchMock.mockResolvedValue(res("boom", { ok: false, status: 500 }));
    await expect(fetchArticles()).rejects.toThrow(/500/);
  });
});

describe("searchArticles", () => {
  it("always sends q and targets the /search endpoint", async () => {
    fetchMock.mockResolvedValue(res([]));
    await searchArticles({ q: '"climate" or energy', language: "en" });
    const url = new URL(calledUrl());
    expect(url.pathname).toBe("/api/v1/articles/search");
    expect(url.searchParams.get("q")).toBe('"climate" or energy');
    expect(url.searchParams.get("language")).toBe("en");
  });
});

describe("fetchArticleById", () => {
  it("targets the by-id path", async () => {
    fetchMock.mockResolvedValue(res({ id: 42 }));
    await fetchArticleById(42);
    expect(calledUrl()).toBe(`${BASE}/api/v1/articles/42`);
  });
});

describe("fetchSources", () => {
  it("appends an encoded language filter when given", async () => {
    fetchMock.mockResolvedValue(res([]));
    await fetchSources("de");
    expect(calledUrl()).toBe(`${BASE}/api/v1/sources/?language=de`);
  });

  it("omits the query string when no language given", async () => {
    fetchMock.mockResolvedValue(res([]));
    await fetchSources();
    expect(calledUrl()).toBe(`${BASE}/api/v1/sources/`);
  });
});

describe("createBookmark — status-code contract", () => {
  it("POSTs with the bearer token and JSON body, returning the created bookmark", async () => {
    const bm = { id: 7, user_id: 1, article_id: 99 };
    fetchMock.mockResolvedValue(res(bm, { status: 201 }));
    const out = await createBookmark(99, "tok-abc");
    expect(out).toEqual(bm);

    const init = calledInit();
    expect(init?.method).toBe("POST");
    const headers = init?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer tok-abc");
    expect(headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init?.body as string)).toEqual({ article_id: 99 });
  });

  it("treats 409 (already bookmarked) as silent success → null", async () => {
    fetchMock.mockResolvedValue(res("conflict", { ok: false, status: 409 }));
    await expect(createBookmark(99, "tok")).resolves.toBeNull();
  });

  it("throws AuthExpiredError on 401", async () => {
    fetchMock.mockResolvedValue(res("unauth", { ok: false, status: 401 }));
    await expect(createBookmark(99, "tok")).rejects.toBeInstanceOf(
      AuthExpiredError,
    );
  });

  it("throws a generic error on other failures", async () => {
    fetchMock.mockResolvedValue(res("nope", { ok: false, status: 500 }));
    await expect(createBookmark(99, "tok")).rejects.toThrow(/500/);
  });
});

describe("listBookmarks", () => {
  it("sends the bearer token and returns the array", async () => {
    fetchMock.mockResolvedValue(res([{ id: 1, user_id: 1, article_id: 2 }]));
    const out = await listBookmarks("tok-xyz");
    expect(out).toHaveLength(1);
    const headers = calledInit()?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer tok-xyz");
  });

  it("throws AuthExpiredError on 401", async () => {
    fetchMock.mockResolvedValue(res("", { ok: false, status: 401 }));
    await expect(listBookmarks("tok")).rejects.toBeInstanceOf(AuthExpiredError);
  });
});

describe("deleteBookmark — status-code contract", () => {
  it("resolves on success", async () => {
    fetchMock.mockResolvedValue(res(null, { status: 204 }));
    await expect(deleteBookmark(5, "tok")).resolves.toBeUndefined();
    expect(calledInit()?.method).toBe("DELETE");
  });

  it("treats 404 (already gone) as silent success", async () => {
    fetchMock.mockResolvedValue(res("", { ok: false, status: 404 }));
    await expect(deleteBookmark(5, "tok")).resolves.toBeUndefined();
  });

  it("throws AuthExpiredError on 401", async () => {
    fetchMock.mockResolvedValue(res("", { ok: false, status: 401 }));
    await expect(deleteBookmark(5, "tok")).rejects.toBeInstanceOf(
      AuthExpiredError,
    );
  });

  it("throws a generic error on other failures", async () => {
    fetchMock.mockResolvedValue(res("err", { ok: false, status: 500 }));
    await expect(deleteBookmark(5, "tok")).rejects.toThrow(/500/);
  });
});

describe("analytics fetchers", () => {
  it("fetchSentimentTrends builds days + optional source params", async () => {
    fetchMock.mockResolvedValue(res([]));
    await fetchSentimentTrends(7, "bbc");
    const url = new URL(calledUrl());
    expect(url.pathname).toBe("/api/v1/analytics/trends");
    expect(url.searchParams.get("days")).toBe("7");
    expect(url.searchParams.get("source")).toBe("bbc");
  });

  it("returns [] when BigQuery is disabled (response is an object, not an array)", async () => {
    fetchMock.mockResolvedValue(res({ message: "BigQuery disabled" }));
    await expect(fetchSentimentTrends()).resolves.toEqual([]);
  });

  it("throws when the analytics request fails", async () => {
    fetchMock.mockResolvedValue(res("", { ok: false, status: 503 }));
    await expect(fetchSentimentTrends()).rejects.toThrow(/503/);
  });
});

describe("DB-analytics numeric coercion (Postgres Decimal → string)", () => {
  it("coerces declared decimal fields from string to number, null-safe", async () => {
    // psycopg2 renders ROUND(numeric) as a JSON *string*; api.ts must coerce.
    fetchMock.mockResolvedValue(
      res([
        { day: "2026-06-01", article_count: 3, avg_sentiment: "0.14", rolling_avg: "0.20" },
        { day: "2026-06-02", article_count: 0, avg_sentiment: null, rolling_avg: null },
      ]),
    );
    const rows = await fetchSentimentRolling(30, 7);
    expect(rows[0].avg_sentiment).toBe(0.14);
    expect(typeof rows[0].avg_sentiment).toBe("number");
    expect(rows[0].rolling_avg).toBe(0.2);
    // null stays null (not coerced to 0)
    expect(rows[1].avg_sentiment).toBeNull();
    expect(rows[1].rolling_avg).toBeNull();
  });

  it("appends the language suffix only when a language is selected", async () => {
    fetchMock.mockResolvedValue(res([]));
    await fetchSourcesRanked(30, "de");
    expect(calledUrl()).toContain("&language=de");

    fetchMock.mockClear();
    await fetchSourcesRanked(30);
    expect(calledUrl()).not.toContain("language=");
  });

  it("returns [] when the DB-analytics response is not an array", async () => {
    fetchMock.mockResolvedValue(res({ detail: "nope" }));
    await expect(fetchSourcesRanked()).resolves.toEqual([]);
  });
});
