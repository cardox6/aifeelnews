<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import type {
    ArticleDto,
    ArticleEntityDto,
    ArticleCategoryDto,
  } from "./api";

  export let article: ArticleDto;
  /** Whether to render the bookmark/remove control (signed-in only). */
  export let showBookmarkButton: boolean = false;
  /** Whether the article is currently bookmarked (drives icon fill / toggle). */
  export let isBookmarked: boolean = false;
  /**
   * Variant of the trailing action:
   *  - 'toggle'  → bookmark icon, click toggles add/remove
   *  - 'remove'  → explicit "✕ Remove" button (used by BookmarksView)
   *  - 'none'    → no action button at all
   */
  export let actionVariant: "toggle" | "remove" | "none" = "toggle";

  const dispatch = createEventDispatcher<{
    bookmark: { article: ArticleDto };
    remove: { article: ArticleDto };
  }>();

  // ── Sentiment helpers ──────────────────────────────────────────────

  function getSentimentColor(label?: string | null): string {
    if (!label) return "text-gray-500";
    switch (label.toLowerCase()) {
      case "positive": return "text-green-600";
      case "negative": return "text-red-600";
      case "neutral":  return "text-blue-600";
      default:         return "text-gray-500";
    }
  }

  function getSentimentBgColor(label?: string | null): string {
    if (!label) return "bg-gray-100";
    switch (label.toLowerCase()) {
      case "positive": return "bg-green-100";
      case "negative": return "bg-red-100";
      case "neutral":  return "bg-blue-100";
      default:         return "bg-gray-100";
    }
  }

  function getSentimentBarColor(label?: string | null): string {
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

  function getSentimentExplanation(
    label?: string | null,
    score?: number | null
  ): string {
    if (!label || score === null || score === undefined) return "";
    const abs = Math.abs(score);
    const intensity =
      abs > 0.6 ? "strongly" : abs > 0.25 ? "moderately" : "slightly";
    switch (label.toLowerCase()) {
      case "positive": return `Overall tone is ${intensity} positive`;
      case "negative": return `Overall tone is ${intensity} negative`;
      case "neutral":  return "Balanced, neutral tone";
      default:         return "";
    }
  }

  // ── Entity / category helpers ────────────────────────────────────

  function getTopEntities(
    entities?: ArticleEntityDto[] | null,
    max = 3
  ): ArticleEntityDto[] {
    if (!entities || entities.length === 0) return [];
    return [...entities].sort((a, b) => b.salience - a.salience).slice(0, max);
  }

  function getTopCategories(
    categories?: ArticleCategoryDto[] | null,
    max = 2
  ): ArticleCategoryDto[] {
    if (!categories || categories.length === 0) return [];
    return [...categories]
      .sort((a, b) => b.confidence - a.confidence)
      .slice(0, max);
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

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString();
  }

  function handleBookmarkClick() {
    dispatch("bookmark", { article });
  }

  function handleRemoveClick() {
    dispatch("remove", { article });
  }
</script>

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

      {#if showBookmarkButton && actionVariant === "toggle"}
        <button
          on:click={handleBookmarkClick}
          class="text-gray-400 hover:text-gray-600"
          aria-label={isBookmarked ? "Remove bookmark" : "Bookmark this article"}
          aria-pressed={isBookmarked}
          title={isBookmarked ? "Remove bookmark" : "Bookmark this article"}
        >
          <svg
            class="w-5 h-5"
            fill={isBookmarked ? "currentColor" : "none"}
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"></path>
          </svg>
        </button>
      {:else if actionVariant === "remove"}
        <button
          on:click={handleRemoveClick}
          class="bookmark-card-remove"
          aria-label="Remove bookmark"
          title="Remove bookmark"
          type="button"
        >
          ✕ Remove
        </button>
      {/if}
    </div>
  </div>
</div>

<style>
  .line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    line-clamp: 2;
    overflow: hidden;
  }

  .line-clamp-3 {
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    line-clamp: 3;
    overflow: hidden;
  }
</style>
