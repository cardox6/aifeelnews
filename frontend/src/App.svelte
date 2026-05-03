<script lang="ts">
  import { onMount } from "svelte";
  import { userStore, loginWithGoogle, logout } from "./lib/firebase";
  import {
    fetchArticles,
    fetchSources,
    type ArticleDto,
    type ArticleEntityDto,
    type ArticleCategoryDto,
    type SourceDto,
  } from "./lib/api";
  import Dashboard from "./lib/Dashboard.svelte";
  import FilterBar from "./lib/FilterBar.svelte";
  import Pagination from "./lib/Pagination.svelte";

  let currentPage: "articles" | "analytics" = "articles";
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

  // Static mediastack categories. (Backend doesn't expose a categories endpoint
  // yet; we keep this client-side for now and TODO a `/categories` route.)
  const CATEGORY_OPTIONS: string[] = [
    "general",
    "business",
    "entertainment",
    "health",
    "science",
    "sports",
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

  // Re-fetch articles whenever a filter or pagination value changes.
  // (Gated by `initialised` so we don't double-fetch on first render.)
  $: if (initialised) {
    void loadArticles();
    // Reading these makes the block reactive to all of them.
    void [sentiment, category, sourceId, search, skip];
  }

  // Redirect to articles if user logs out while on analytics
  $: if (!$userStore && currentPage === "analytics") {
    currentPage = "articles";
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

  // ── Sentiment helpers ──────────────────────────────────────────────

  function getSentimentColor(label?: string): string {
    if (!label) return "text-gray-500";
    switch (label.toLowerCase()) {
      case "positive": return "text-green-600";
      case "negative": return "text-red-600";
      case "neutral":  return "text-blue-600";
      default:         return "text-gray-500";
    }
  }

  function getSentimentBgColor(label?: string): string {
    if (!label) return "bg-gray-100";
    switch (label.toLowerCase()) {
      case "positive": return "bg-green-100";
      case "negative": return "bg-red-100";
      case "neutral":  return "bg-blue-100";
      default:         return "bg-gray-100";
    }
  }

  function getSentimentBarColor(label?: string): string {
    if (!label) return "#9ca3af";
    switch (label.toLowerCase()) {
      case "positive": return "#16a34a";
      case "negative": return "#dc2626";
      case "neutral":  return "#2563eb";
      default:         return "#9ca3af";
    }
  }

  function sentimentScoreToPercent(score: number): number {
    return Math.round(((score + 1) / 2) * 100);
  }

  function getSentimentExplanation(label?: string | null, score?: number | null): string {
    if (!label || score === null || score === undefined) return "";
    const abs = Math.abs(score);
    const intensity = abs > 0.6 ? "strongly" : abs > 0.25 ? "moderately" : "slightly";
    switch (label.toLowerCase()) {
      case "positive": return `Overall tone is ${intensity} positive`;
      case "negative": return `Overall tone is ${intensity} negative`;
      case "neutral":  return "Balanced, neutral tone";
      default:         return "";
    }
  }

  // ── Entity / category helpers ────────────────────────────────────

  function getTopEntities(entities?: ArticleEntityDto[] | null, max = 3): ArticleEntityDto[] {
    if (!entities || entities.length === 0) return [];
    return [...entities].sort((a, b) => b.salience - a.salience).slice(0, max);
  }

  function getTopCategories(categories?: ArticleCategoryDto[] | null, max = 2): ArticleCategoryDto[] {
    if (!categories || categories.length === 0) return [];
    return [...categories].sort((a, b) => b.confidence - a.confidence).slice(0, max);
  }

  function formatCategoryName(taxonomyPath: string): string {
    const parts = taxonomyPath.split("/").filter(Boolean);
    return parts[parts.length - 1] || taxonomyPath;
  }

  function formatEntityType(type: string): string {
    const map: Record<string, string> = {
      ORGANIZATION: "Org", PERSON: "Person", LOCATION: "Place",
      EVENT: "Event", WORK_OF_ART: "Work", CONSUMER_GOOD: "Product",
      OTHER: "", UNKNOWN: "",
    };
    return map[type] ?? type.charAt(0) + type.slice(1).toLowerCase();
  }

  // ── Image / favicon helpers ─────────────────────────────────────

  function getDomain(url: string): string {
    try {
      return new URL(url).hostname.replace(/^www\./, "");
    } catch {
      return "";
    }
  }

  function getFaviconUrl(articleUrl: string, size = 20): string {
    const domain = getDomain(articleUrl);
    if (!domain) return "";
    return `https://www.google.com/s2/favicons?domain=${domain}&sz=${size}`;
  }

  function handleImageError(event: Event) {
    const img = event.target as HTMLImageElement;
    img.style.display = "none";
  }

  // ── General helpers ──────────────────────────────────────────────

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString();
  }

  function handleBookmark(article: ArticleDto) {
    // TODO: Implement bookmark functionality when Firebase auth is working
    console.log("Bookmarking article:", article.title);
    // For now, show a simple alert
    alert(`Bookmark feature coming soon!\n\nArticle: ${article.title}`);
  }
</script>

<div class="min-h-screen bg-gray-50">
  <!-- Header -->
  <header class="bg-white shadow-sm border-b">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between items-center h-16">
        <div class="flex items-center space-x-6">
          <h1 class="text-2xl font-bold text-gray-900">aiFeelNews</h1>

          <nav class="flex space-x-1">
            <button
              on:click={() => currentPage = "articles"}
              class="px-3 py-1.5 rounded-md text-sm font-medium transition-colors
                {currentPage === 'articles' ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'}"
            >
              Articles
            </button>
            {#if $userStore}
              <button
                on:click={() => currentPage = "analytics"}
                class="px-3 py-1.5 rounded-md text-sm font-medium transition-colors
                  {currentPage === 'analytics' ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'}"
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
          <h2 class="text-xl font-semibold text-gray-900">Latest Articles ({articles.length})</h2>
          <p class="text-gray-600">Recent news with sentiment analysis</p>
        </div>

        {#if articles.length === 0}
          <div class="text-center py-12">
            <p class="text-gray-600">No articles match the current filters.</p>
          </div>
        {:else}
          <div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {#each articles as article (article.id)}
              <div class="bg-white rounded-lg shadow-sm border overflow-hidden hover:shadow-md transition-shadow">
                <!-- Article image / placeholder -->
                <div class="card-image-wrapper">
                  <div class="card-image-placeholder">
                    <svg class="card-image-placeholder-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v12a2 2 0 01-2 2z" />
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 15l-5-5L5 21" />
                      <circle cx="8.5" cy="8.5" r="1.5" fill="currentColor" />
                    </svg>
                  </div>
                  {#if article.image_url}
                    <img
                      src={article.image_url}
                      alt=""
                      class="card-image"
                      loading="lazy"
                      decoding="async"
                      referrerpolicy="no-referrer"
                      on:error={handleImageError}
                    />
                  {/if}
                </div>

                <div class="card-body">
                  <!-- Source (with favicon) -->
                  <div class="flex items-center justify-between mb-3">
                    <span class="source-badge text-xs font-medium text-blue-600 bg-blue-100 px-2 py-1 rounded">
                      {#if getDomain(article.url)}
                        <img
                          src={getFaviconUrl(article.url)}
                          alt=""
                          class="source-favicon"
                          loading="lazy"
                          on:error={handleImageError}
                        />
                      {/if}
                      {article.source?.name || `Source #${article.source?.id || "Unknown"}`}
                    </span>
                    <span class="text-xs text-gray-500">{formatDate(article.published_at)}</span>
                  </div>

                  <!-- Title -->
                  <h3 class="text-lg font-semibold text-gray-900 mb-2 line-clamp-2">
                    {article.title}
                  </h3>

                  <!-- Description -->
                  {#if article.description}
                    <p class="text-gray-600 text-sm mb-3 line-clamp-3">
                      {article.description}
                    </p>
                  {/if}

                  <!-- Sentiment analysis -->
                  {#if article.sentiment_label && article.sentiment_score !== null && article.sentiment_score !== undefined}
                    <div class="sentiment-section mb-3">
                      <div class="flex items-center justify-between mb-2">
                        <span class="text-xs font-semibold px-2 rounded {getSentimentBgColor(article.sentiment_label)} {getSentimentColor(article.sentiment_label)}">
                          {article.sentiment_label.toUpperCase()}
                        </span>
                        <span
                          class="text-xs text-gray-500"
                          title="Sentiment score from -1.0 (very negative) to 1.0 (very positive)"
                        >
                          Score: {article.sentiment_score.toFixed(2)}
                        </span>
                      </div>

                      <div class="sentiment-bar-track">
                        <div
                          class="sentiment-bar-fill"
                          style="width: {sentimentScoreToPercent(article.sentiment_score)}%; background-color: {getSentimentBarColor(article.sentiment_label)};"
                        ></div>
                        <div class="sentiment-bar-midpoint"></div>
                      </div>

                      <p class="text-xs text-gray-400 mt-1 sentiment-explanation">
                        {getSentimentExplanation(article.sentiment_label, article.sentiment_score)}
                      </p>
                    </div>
                  {/if}

                  <!-- Content categories -->
                  {#if getTopCategories(article.article_categories).length > 0}
                    <div class="flex items-center flex-wrap gap-1 mb-2">
                      <span class="text-xs text-gray-400 mr-1">Topics:</span>
                      {#each getTopCategories(article.article_categories) as cat}
                        <span
                          class="category-chip"
                          title="Category: {cat.name} (confidence: {(cat.confidence * 100).toFixed(0)}%)"
                        >
                          {formatCategoryName(cat.name)}
                        </span>
                      {/each}
                    </div>
                  {/if}

                  <!-- Key entities -->
                  {#if getTopEntities(article.article_entities).length > 0}
                    <div class="flex items-center flex-wrap gap-1 mb-3">
                      <span class="text-xs text-gray-400 mr-1">Entities:</span>
                      {#each getTopEntities(article.article_entities) as ae}
                        {#if ae.entity.wikipedia_url}
                          <a
                            href={ae.entity.wikipedia_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            class="entity-chip entity-chip-link"
                            title="{ae.entity.name} ({ae.entity.type}) — Relevance: {(ae.salience * 100).toFixed(0)}%, Mentions: {ae.mention_count}"
                          >
                            {ae.entity.name}
                            {#if formatEntityType(ae.entity.type)}<span class="entity-type">{formatEntityType(ae.entity.type)}</span>{/if}
                          </a>
                        {:else}
                          <span
                            class="entity-chip"
                            title="{ae.entity.name} ({ae.entity.type}) — Relevance: {(ae.salience * 100).toFixed(0)}%, Mentions: {ae.mention_count}"
                          >
                            {ae.entity.name}
                            {#if formatEntityType(ae.entity.type)}<span class="entity-type">{formatEntityType(ae.entity.type)}</span>{/if}
                          </span>
                        {/if}
                      {/each}
                    </div>
                  {/if}

                  <!-- Actions -->
                  <div class="flex items-center justify-between">
                    <a
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      class="text-blue-600 hover:text-blue-800 text-sm font-medium"
                    >
                      Read Article →
                    </a>

                    {#if $userStore}
                      <button
                        on:click={() => handleBookmark(article)}
                        class="text-gray-400 hover:text-gray-600"
                        aria-label="Bookmark this article"
                        title="Bookmark this article"
                      >
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"></path>
                        </svg>
                      </button>
                    {/if}
                  </div>
                </div>
              </div>
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
    {:else if currentPage === "analytics" && $userStore}
      <Dashboard />
    {:else}
      <div class="text-center py-12">
        <p class="text-gray-600">Please log in to access analytics.</p>
      </div>
    {/if}
  </main>
</div>

<style>
  .line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    line-clamp: 2; /* Standard property for compatibility */
    overflow: hidden;
  }

  .line-clamp-3 {
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    line-clamp: 3; /* Standard property for compatibility */
    overflow: hidden;
  }
</style>
