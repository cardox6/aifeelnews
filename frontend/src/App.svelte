<script lang="ts">
  import { onMount } from "svelte";
  import {
    userStore,
    loginWithGoogle,
    logout,
    getIdToken,
  } from "./lib/firebase";
  import { theme, toggleTheme } from "./lib/theme";
  import {
    fetchArticles,
    searchArticles,
    fetchSources,
    createBookmark,
    deleteBookmark,
    listBookmarks,
    AuthExpiredError,
    type ArticleDto,
    type SourceDto,
  } from "./lib/api";
  import { bookmarkStore } from "./lib/bookmarkStore";
  import Dashboard from "./lib/Dashboard.svelte";
  import FilterBar from "./lib/FilterBar.svelte";
  import Pagination from "./lib/Pagination.svelte";
  import ArticleCard from "./lib/ArticleCard.svelte";
  import BookmarksView from "./lib/BookmarksView.svelte";
  import Privacy from "./lib/Privacy.svelte";
  import FlagToggle from "./lib/FlagToggle.svelte";
  import Logo from "./lib/Logo.svelte";

  type Page = "articles" | "analytics" | "bookmarks" | "privacy";
  let currentPage: Page = "articles";

  let articles: ArticleDto[] = [];
  let loading = true;
  let error = "";

  // Transient, non-fatal bookmark feedback (auto-clears). A failed bookmark
  // action must not be fatal or yank the user out of their session.
  let bookmarkError = "";
  let bookmarkErrorTimer: ReturnType<typeof setTimeout> | null = null;
  function flashBookmarkError(message: string) {
    bookmarkError = message;
    if (bookmarkErrorTimer !== null) clearTimeout(bookmarkErrorTimer);
    bookmarkErrorTimer = setTimeout(() => {
      bookmarkError = "";
      bookmarkErrorTimer = null;
    }, 4000);
  }

  // Filter / pagination state.
  let sentiment: string = "";
  let category: string = "";
  let sourceId: number | "" = "";
  let search: string = "";
  // ISO-8601 datetime strings (or "" when unset). The FilterBar owns the
  // preset-vs-custom UI and emits already-resolved bounds; App only stores and
  // forwards them.
  let publishedAfter: string = "";
  let publishedBefore: string = "";
  // Content language (ISO 639-1). The single source of truth for the EN/DE
  // toggle — drives both the article feed and the Analytics dashboard. Always
  // exactly one language; defaults to English.
  let language: string = "en";
  let skip: number = 0;
  const limit: number = 20;

  // Mediastack categories that the ingestion job actually fetches. The
  // production config (MEDIASTACK_FETCH_CATEGORIES in app/config/ingestion.py)
  // explicitly excludes ``sports`` and ``entertainment`` via the leading-``-``
  // syntax, so listing them here would offer the user dropdown options that
  // can never have results. Backend doesn't expose a categories endpoint yet
  // — TODO a /categories route so this can be data-driven instead of hand-kept
  // in sync.
  const CATEGORY_OPTIONS: string[] = [
    "general",
    "business",
    "health",
    "science",
    "technology",
  ];

  let sources: SourceDto[] = [];

  // Track whether we've already done the initial mount-load. The reactive
  // re-fetch block fires whenever filter/skip change, so we gate it until
  // after onMount completes to avoid double-fetching on first render.
  let initialised = false;

  // ── URL ⇄ filter-state sync ─────────────────────────────────────────
  // Filters/search/date/page live in the querystring so a filtered view is
  // shareable and survives reload. We use replaceState (not pushState) so each
  // keystroke/filter change doesn't spam the browser history.
  function readStateFromUrl() {
    const p = new URLSearchParams(window.location.search);
    sentiment = p.get("sentiment") ?? "";
    category = p.get("category") ?? "";
    const sid = p.get("source");
    sourceId = sid ? Number(sid) : "";
    search = p.get("search") ?? "";
    publishedAfter = p.get("after") ?? "";
    publishedBefore = p.get("before") ?? "";
    language = p.get("lang") ?? "en";
    const sk = Number(p.get("skip") ?? "0");
    skip = Number.isFinite(sk) && sk > 0 ? sk : 0;
  }

  function syncStateToUrl() {
    const p = new URLSearchParams();
    if (sentiment) p.set("sentiment", sentiment);
    if (category) p.set("category", category);
    if (sourceId !== "") p.set("source", String(sourceId));
    if (search.trim()) p.set("search", search.trim());
    if (publishedAfter) p.set("after", publishedAfter);
    if (publishedBefore) p.set("before", publishedBefore);
    if (language && language !== "en") p.set("lang", language);
    if (skip > 0) p.set("skip", String(skip));
    const qs = p.toString();
    const url = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
    window.history.replaceState(null, "", url);
  }

  // The active search term (>= 2 chars after trim), or "" when not searching.
  // Drives the FTS-vs-filter branch in loadArticles and the highlight/empty-state
  // UI below.
  $: activeQuery = search.trim().length >= 2 ? search.trim() : "";

  async function loadArticles() {
    try {
      loading = true;
      error = "";
      if (activeQuery) {
        // A search term switches to the relevance-ranked full-text endpoint
        // (title + description, phrase/boolean). It takes the date filter but
        // not the sentiment/category/source dropdowns — search is its own mode.
        articles = await searchArticles({
          q: activeQuery,
          skip,
          limit,
          published_after: publishedAfter || undefined,
          published_before: publishedBefore || undefined,
          language: language || undefined,
        });
      } else {
        articles = await fetchArticles({
          skip,
          limit,
          sentiment_label: sentiment || undefined,
          category: category || undefined,
          source_id: sourceId === "" ? undefined : sourceId,
          published_after: publishedAfter || undefined,
          published_before: publishedBefore || undefined,
          language: language || undefined,
        });
      }
    } catch (e) {
      console.error("Failed to load articles:", e);
      error = e instanceof Error ? e.message : "Failed to load articles";
    } finally {
      loading = false;
    }
  }

  async function loadSources() {
    try {
      sources = await fetchSources();
    } catch (e) {
      console.warn("Failed to load sources, continuing with empty list:", e);
      sources = [];
    }
  }

  async function hydrateBookmarks() {
    if (!$userStore) {
      bookmarkStore.reset();
      return;
    }
    try {
      const token = await getIdToken();
      if (!token) return;
      const bookmarks = await listBookmarks(token);
      bookmarkStore.hydrate(bookmarks);
    } catch (e) {
      // Hydration is a passive background fetch fired by the auth-state
      // reactive block. A 401 here must NOT force a logout — otherwise a
      // backend that can't verify the token (e.g. a local dev backend with
      // no Firebase service account) would sign the user straight back out
      // in a login→401→logout loop. Only user-initiated bookmark actions
      // treat a 401 as a genuinely expired session.
      console.warn("Failed to hydrate bookmarks (continuing signed in):", e);
    }
  }

  // ── Reactive triggers ───────────────────────────────────────────────

  // Re-fetch articles whenever a filter or pagination value changes.
  // (Gated by `initialised` so we don't double-fetch on first render.)
  $: if (initialised) {
    void loadArticles();
    syncStateToUrl();
    // Reading these makes the block reactive to all of them.
    void [
      sentiment,
      category,
      sourceId,
      search,
      publishedAfter,
      publishedBefore,
      language,
      skip,
    ];
  }

  // React to auth-state changes: hydrate / reset the bookmark store, and
  // bounce away from auth-only pages on sign-out.
  $: if ($userStore) {
    void hydrateBookmarks();
  } else {
    bookmarkStore.reset();
    if (currentPage === "analytics" || currentPage === "bookmarks") {
      currentPage = "articles";
    }
  }

  onMount(async () => {
    // Restore any shared/bookmarked filter state from the URL before the first
    // fetch so a deep-linked search lands on the right results immediately.
    readStateFromUrl();
    // ``allSettled`` so a slow/failing /sources/ request can't block the
    // articles fetch or prevent ``initialised`` from flipping. Both load
    // functions already swallow their own errors; this is belt-and-suspenders.
    await Promise.allSettled([loadArticles(), loadSources()]);
    initialised = true;
  });

  function handleRetry() {
    loadArticles();
  }

  function handleFilterChange(
    event: CustomEvent<{
      sentiment: string;
      category: string;
      sourceId: number | "";
      search: string;
      publishedAfter: string;
      publishedBefore: string;
    }>
  ) {
    const next = event.detail;
    sentiment = next.sentiment;
    category = next.category;
    sourceId = next.sourceId;
    search = next.search;
    publishedAfter = next.publishedAfter;
    publishedBefore = next.publishedBefore;
    // Filter changed → reset to first page.
    skip = 0;
  }

  // Switch the content language (EN/DE). Drives the feed + dashboard via the
  // reactive block; resets pagination since the result set changes entirely.
  function setLanguage(lang: string) {
    if (lang === language) return;
    language = lang;
    skip = 0;
  }

  function handlePrevPage() {
    skip = Math.max(0, skip - limit);
  }

  function handleNextPage() {
    skip = skip + limit;
  }

  $: hasMore = articles.length === limit;

  // ── Bookmark toggle from feed cards ────────────────────────────────

  async function handleBookmarkToggle(
    event: CustomEvent<{ article: ArticleDto }>
  ) {
    const article = event.detail.article;

    if (!$userStore) {
      // Not signed in → kick off sign-in flow. No-op on the bookmark itself
      // until the user finishes auth and clicks again.
      try {
        await loginWithGoogle();
      } catch (e) {
        console.warn("Sign-in cancelled or failed:", e);
      }
      return;
    }

    const token = await getIdToken();
    if (!token) {
      console.warn("Could not retrieve auth token; aborting bookmark op.");
      return;
    }

    const wasBookmarked = bookmarkStore.has(article.id);

    if (wasBookmarked) {
      // Remove flow.
      const bookmarkId = bookmarkStore.getBookmarkId(article.id);
      if (bookmarkId === null) {
        // Stale state — refetch and bail.
        await hydrateBookmarks();
        return;
      }
      // Optimistic remove.
      bookmarkStore.remove(article.id);
      try {
        await deleteBookmark(bookmarkId, token);
      } catch (e) {
        // Revert
        bookmarkStore.add(article.id, bookmarkId);
        // A 401 here means the backend rejected the token. We don't force a
        // logout: a valid token the backend can't verify (server-side issue)
        // shouldn't end the session. The next getIdToken() refreshes a
        // genuinely-expired token. Surface a transient, non-fatal message.
        if (e instanceof AuthExpiredError) {
          flashBookmarkError("Couldn't remove bookmark — please try again.");
        } else {
          console.error("Failed to remove bookmark:", e);
          flashBookmarkError("Couldn't remove bookmark — please try again.");
        }
      }
    } else {
      // Add flow. We don't yet have the bookmark.id, so optimistic-add
      // without it; then patch in the real id once POST returns.
      bookmarkStore.add(article.id);
      try {
        const created = await createBookmark(article.id, token);
        if (created) {
          bookmarkStore.add(article.id, created.id);
        } else {
          // 409 — already bookmarked server-side. Refetch to learn the id.
          await hydrateBookmarks();
        }
      } catch (e) {
        // Revert
        bookmarkStore.remove(article.id);
        // See the remove-flow note: a 401 is non-fatal, never a forced logout.
        if (e instanceof AuthExpiredError) {
          flashBookmarkError("Couldn't save bookmark — please try again.");
        } else {
          console.error("Failed to create bookmark:", e);
          flashBookmarkError("Couldn't save bookmark — please try again.");
        }
      }
    }
  }
</script>

<header class="header">
  <div class="header-inner">
    <Logo onhome={() => (currentPage = "articles")} />

    <nav class="nav" aria-label="Main navigation">
      <button
        on:click={() => (currentPage = "articles")}
        class="nav-button"
        class:nav-button-active={currentPage === "articles"}
        aria-current={currentPage === "articles" ? "page" : undefined}
      >
        Articles
      </button>
      {#if $userStore}
        <button
          on:click={() => (currentPage = "bookmarks")}
          class="nav-button"
          class:nav-button-active={currentPage === "bookmarks"}
          aria-current={currentPage === "bookmarks" ? "page" : undefined}
        >
          Bookmarks
        </button>
        <button
          on:click={() => (currentPage = "analytics")}
          class="nav-button"
          class:nav-button-active={currentPage === "analytics"}
          aria-current={currentPage === "analytics" ? "page" : undefined}
        >
          Analytics
        </button>
      {/if}
    </nav>

    <!-- Content-language toggle: rounded SVG flags, dead-centered in the header
         bar (absolutely positioned so it stays centered regardless of the
         left/right group widths). Switches both the feed and the dashboard. -->
    <div class="lang-center">
      <FlagToggle {language} onchange={setLanguage} />
    </div>

    <div class="header-right">
      {#if $userStore}
        <span class="user-email" title={$userStore.email ?? undefined}>{$userStore.email}</span>
      {/if}
      <button
        class="theme-toggle"
        on:click={toggleTheme}
        aria-label="Toggle light/dark theme"
        title="Toggle theme"
      >
        {$theme === "dark" ? "☀" : "☾"}
      </button>
      {#if $userStore}
        <button class="btn" on:click={logout}>Logout</button>
      {:else}
        <button class="btn btn-primary" on:click={loginWithGoogle}>Sign in with Google</button>
      {/if}
    </div>
  </div>
</header>

{#if bookmarkError}
  <div class="toast" role="status" aria-live="polite">
    <span class="error-icon" aria-hidden="true">⚠</span>
    <span>{bookmarkError}</span>
  </div>
{/if}

<main class="main">
  {#if currentPage === "articles"}
    <FilterBar
      {sentiment}
      {category}
      {sourceId}
      {search}
      {publishedAfter}
      {publishedBefore}
      categories={CATEGORY_OPTIONS}
      {sources}
      on:change={handleFilterChange}
    />

    {#if error}
      <div class="error-banner" role="alert">
        <span class="error-icon" aria-hidden="true">⚠</span>
        <span style="flex:1">{error}</span>
        <button class="btn" on:click={handleRetry}>Retry</button>
      </div>
    {/if}

    {#if loading}
      <div style="text-align:center;padding:var(--sp-10) 0">
        <div class="spinner"></div>
        <p class="text-sec">Loading latest articles…</p>
      </div>
    {:else}
      <div class="page-head">
        <h1 class="page-title">
          {activeQuery ? "Search results" : "Latest Articles"}
          <span class="text-ter" style="font-weight:400">({articles.length})</span>
        </h1>
        <p class="page-subtitle">
          {#if activeQuery}
            Ranked by relevance for “{activeQuery}”
          {:else}
            Recent news with sentiment analysis
          {/if}
        </p>
      </div>

      {#if articles.length === 0}
        <div class="empty-state">
          <div class="empty-icon" aria-hidden="true">◳</div>
          {#if activeQuery}
            <p class="empty-title">No results for “{activeQuery}”</p>
            <p class="empty-sub">
              Try a different term, or use quotes for a phrase and
              <code>-word</code> to exclude.
            </p>
          {:else}
            <p class="empty-title">No articles match these filters</p>
            <p class="empty-sub">Try clearing a filter or broadening your search.</p>
          {/if}
        </div>
      {:else}
        <div class="articles-grid">
          {#each articles as article (article.id)}
            <ArticleCard
              {article}
              searchTerm={activeQuery}
              showBookmarkButton={!!$userStore}
              isBookmarked={$bookmarkStore.bookmarkedIds.has(article.id)}
              actionVariant="toggle"
              on:bookmark={handleBookmarkToggle}
            />
          {/each}
        </div>
      {/if}

      <Pagination
        current={skip}
        pageSize={limit}
        {hasMore}
        on:prev={handlePrevPage}
        on:next={handleNextPage}
      />
    {/if}
  {:else if currentPage === "bookmarks" && $userStore}
    <BookmarksView />
  {:else if currentPage === "analytics" && $userStore}
    <Dashboard {language} />
  {:else if currentPage === "privacy"}
    <Privacy />
  {:else}
    <div class="empty-state">
      <div class="empty-icon" aria-hidden="true">◌</div>
      <p class="empty-title">Sign in to continue</p>
      <p class="empty-sub">This page needs an account. Sign in with Google to access it.</p>
    </div>
  {/if}
</main>

<footer class="site-footer">
  <div class="footer-inner">
    <p class="footer-copy">
      © 2026 aiFeelNews — a university project at
      <a href="https://code.berlin" target="_blank" rel="noopener noreferrer">CODE University</a>.
    </p>
    <p class="footer-credits">
      Sentiment by Google Cloud Natural Language · Articles via Mediastack ·
      No tracking cookies.
    </p>
    <nav class="footer-nav" aria-label="Footer">
      <button class="footer-link" on:click={() => (currentPage = "privacy")}>Privacy</button>
      <a
        class="footer-link"
        href="https://github.com/cardox6/aifeelnews"
        target="_blank"
        rel="noopener noreferrer">Source on GitHub</a>
    </nav>
  </div>
</footer>

<style>
  .articles-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: var(--sp-5);
    margin-bottom: var(--sp-6);
    /* Start-align so a card whose sentiment "Why?" panel is expanded grows on
       its own rather than stretching every other card in its row to match. */
    align-items: start;
  }

  .site-footer {
    border-top: 1px solid var(--border);
    margin-top: var(--sp-10);
    padding: var(--sp-6) var(--sp-4);
    background: var(--bg-panel);
  }
  .footer-inner {
    max-width: 1280px;
    margin: 0 auto;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--sp-2) var(--sp-5);
    font-size: 13px;
    color: var(--text-ter);
  }
  .footer-copy { margin: 0; color: var(--text-sec); }
  .footer-copy a { color: var(--text-sec); text-decoration: underline; }
  .footer-credits { margin: 0; }
  .footer-nav {
    margin-left: auto;
    display: flex;
    gap: var(--sp-4);
  }
  .footer-link {
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    color: var(--text-sec);
    font: inherit;
    text-decoration: none;
  }
  .footer-link:hover { color: var(--text-pri); }
  .footer-link:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
    border-radius: var(--r-sm);
  }
  @media (max-width: 640px) {
    .footer-nav { margin-left: 0; }
  }
  .error-icon { font-size: 16px; flex-shrink: 0; }

  .toast {
    position: fixed;
    top: 68px;
    right: var(--sp-6);
    z-index: 200;
    display: flex;
    align-items: center;
    gap: var(--sp-2);
    max-width: 360px;
    padding: var(--sp-3) var(--sp-4);
    background: var(--bg-panel);
    border: 1px solid rgba(251, 113, 133, 0.3);
    border-left: 3px solid var(--neg);
    border-radius: var(--r-lg);
    box-shadow: var(--shadow-md);
    color: var(--text-pri);
    font-size: 13px;
    animation: toast-in 0.18s ease;
  }
  @keyframes toast-in {
    from { opacity: 0; transform: translateY(-6px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  @media (max-width: 768px) {
    .articles-grid { grid-template-columns: 1fr; }
    .toast { left: var(--sp-4); right: var(--sp-4); max-width: none; }
  }
</style>
