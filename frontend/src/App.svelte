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

  type Page = "articles" | "analytics" | "bookmarks";
  let currentPage: Page = "articles";

  let articles: ArticleDto[] = [];
  let loading = true;
  let error = "";

  // Filter / pagination state.
  let sentiment: string = "";
  let category: string = "";
  let sourceId: number | "" = "";
  let search: string = "";
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

  async function loadArticles() {
    try {
      loading = true;
      error = "";
      articles = await fetchArticles({
        skip,
        limit,
        sentiment_label: sentiment || undefined,
        category: category || undefined,
        source_id: sourceId === "" ? undefined : sourceId,
        search: search.trim().length >= 2 ? search.trim() : undefined,
      });
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
    // Reading these makes the block reactive to all of them.
    void [sentiment, category, sourceId, search, skip];
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
    }>
  ) {
    const next = event.detail;
    sentiment = next.sentiment;
    category = next.category;
    sourceId = next.sourceId;
    search = next.search;
    // Filter changed → reset to first page.
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
        if (e instanceof AuthExpiredError) {
          await logout();
        } else {
          console.error("Failed to remove bookmark:", e);
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
        if (e instanceof AuthExpiredError) {
          await logout();
        } else {
          console.error("Failed to create bookmark:", e);
        }
      }
    }
  }
</script>

<header class="header">
  <div class="header-inner">
    <div class="wordmark" aria-label="aiFeelNews">ai<span>Feel</span>News</div>

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

<main class="main">
  {#if currentPage === "articles"}
    <FilterBar
      {sentiment}
      {category}
      {sourceId}
      {search}
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
          Latest Articles
          <span class="text-ter" style="font-weight:400">({articles.length})</span>
        </h1>
        <p class="page-subtitle">Recent news with sentiment analysis</p>
      </div>

      {#if articles.length === 0}
        <div class="empty-state">
          <div class="empty-icon" aria-hidden="true">◳</div>
          <p class="empty-title">No articles match these filters</p>
          <p class="empty-sub">Try clearing a filter or broadening your search.</p>
        </div>
      {:else}
        <div class="articles-grid">
          {#each articles as article (article.id)}
            <ArticleCard
              {article}
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
    <Dashboard />
  {:else}
    <div class="empty-state">
      <div class="empty-icon" aria-hidden="true">◌</div>
      <p class="empty-title">Sign in to continue</p>
      <p class="empty-sub">This page needs an account. Sign in with Google to access it.</p>
    </div>
  {/if}
</main>

<style>
  .articles-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: var(--sp-5);
    margin-bottom: var(--sp-6);
  }
  .error-icon { font-size: 16px; flex-shrink: 0; }
  @media (max-width: 768px) {
    .articles-grid { grid-template-columns: 1fr; }
  }
</style>
