<script lang="ts">
  import { onMount } from "svelte";
  import {
    userStore,
    loginWithGoogle,
    logout,
    getIdToken,
  } from "./lib/firebase";
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
      if (e instanceof AuthExpiredError) {
        await logout();
      } else {
        console.warn("Failed to hydrate bookmarks:", e);
      }
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
    await Promise.all([loadArticles(), loadSources()]);
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

<div class="min-h-screen bg-gray-50">
  <!-- Header -->
  <header class="bg-white shadow-sm border-b">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between items-center h-16">
        <div class="flex items-center space-x-6">
          <h1 class="text-2xl font-bold text-gray-900">aiFeelNews</h1>

          <nav class="nav">
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
        </div>

        <div class="flex items-center space-x-4">
          {#if $userStore}
            <span class="text-sm text-gray-600">Welcome, {$userStore.email}</span>
            <button
              on:click={logout}
              class="bg-red-600 text-white px-4 py-2 rounded-md text-sm hover:bg-red-700"
            >
              Logout
            </button>
          {:else}
            <button
              on:click={loginWithGoogle}
              class="bg-blue-600 text-white px-4 py-2 rounded-md text-sm hover:bg-blue-700"
            >
              Login with Google
            </button>
          {/if}
        </div>
      </div>
    </div>
  </header>

  <!-- Main Content -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
        <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-6">
          <div class="flex items-center justify-between">
            <span>{error}</span>
            <button
              on:click={handleRetry}
              class="bg-red-600 text-white px-3 py-1 rounded text-sm hover:bg-red-700"
            >
              Retry
            </button>
          </div>
        </div>
      {/if}

      {#if loading}
        <div class="text-center py-12">
          <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p class="mt-4 text-gray-600">Loading latest articles...</p>
        </div>
      {:else}
        <div class="mb-6">
          <h2 class="text-xl font-semibold text-gray-900">
            Latest Articles ({articles.length})
          </h2>
          <p class="text-gray-600">Recent news with sentiment analysis</p>
        </div>

        {#if articles.length === 0}
          <div class="text-center py-12">
            <p class="text-gray-600">
              No articles match the current filters.
            </p>
          </div>
        {:else}
          <div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
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
      <div class="text-center py-12">
        <p class="text-gray-600">Please log in to access this page.</p>
      </div>
    {/if}
  </main>
</div>
