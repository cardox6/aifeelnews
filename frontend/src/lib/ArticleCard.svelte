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
  // The sentiment scale (emerald / slate / rose) is intentionally distinct
  // from the indigo brand accent, so a sentiment colour can never read as a
  // brand colour. `sentimentClass` maps a label to the shared chip modifier
  // (.pos / .neu / .neg in app.css); the score bar reads the same token vars.

  function sentimentClass(label?: string | null): "pos" | "neu" | "neg" {
    switch ((label ?? "").toLowerCase()) {
      case "positive": return "pos";
      case "negative": return "neg";
      default:         return "neu";
    }
  }

  function getSentimentBarColor(label?: string | null): string {
    switch ((label ?? "").toLowerCase()) {
      case "positive": return "var(--pos)";
      case "negative": return "var(--neg)";
      default:         return "var(--neu)";
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

<article class="card">
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

  <div class="card-meta">
    <span class="source-badge">
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
    <span class="pub-date mono">{formatDate(article.published_at)}</span>
  </div>

  <div class="card-body">
    <!-- Title -->
    <h3 class="card-title">{article.title}</h3>

    <!-- Description -->
    {#if article.description}
      <p class="card-desc">{article.description}</p>
    {/if}

    <!-- Sentiment analysis -->
    {#if article.sentiment_label && article.sentiment_score !== null && article.sentiment_score !== undefined}
      <div class="sentiment-box" aria-label="Sentiment analysis">
        <div class="sentiment-row">
          <span class="sentiment-chip {sentimentClass(article.sentiment_label)}">
            <span class="chip-dot" aria-hidden="true"></span>
            {article.sentiment_label}
          </span>
          <span
            class="sentiment-score mono"
            title="Sentiment score from -1.0 (very negative) to 1.0 (very positive)"
          >
            {article.sentiment_score > 0 ? "+" : ""}{article.sentiment_score.toFixed(2)}
          </span>
        </div>

        <div class="score-bar">
          <div class="score-bar-mid"></div>
          <div
            class="score-bar-fill"
            style="width: {Math.abs(sentimentScoreToPercent(article.sentiment_score) - 50)}%;
                   {article.sentiment_score >= 0 ? 'left:50%' : `left:${sentimentScoreToPercent(article.sentiment_score)}%`};
                   background: {getSentimentBarColor(article.sentiment_label)};"
          ></div>
        </div>

        {#if getSentimentExplanation(article.sentiment_label, article.sentiment_score)}
          <p class="sentiment-note">
            {getSentimentExplanation(article.sentiment_label, article.sentiment_score)}
          </p>
        {/if}
      </div>
    {/if}

    <!-- Content categories -->
    {#if getTopCategories(article.article_categories).length > 0}
      <div class="chips-row" aria-label="Topics">
        {#each getTopCategories(article.article_categories) as cat}
          <span
            class="chip chip-topic"
            title="Category: {cat.name} (confidence: {(cat.confidence * 100).toFixed(0)}%)"
          >
            {formatCategoryName(cat.name)}
          </span>
        {/each}
      </div>
    {/if}

    <!-- Key entities -->
    {#if getTopEntities(article.article_entities).length > 0}
      <div class="chips-row" aria-label="Named entities">
        {#each getTopEntities(article.article_entities) as ae}
          {#if ae.entity.wikipedia_url}
            <a
              href={ae.entity.wikipedia_url}
              target="_blank"
              rel="noopener noreferrer"
              class="chip chip-entity"
              title="{ae.entity.name} ({ae.entity.type}) — Relevance: {(ae.salience * 100).toFixed(0)}%, Mentions: {ae.mention_count}"
            >
              {ae.entity.name}
              {#if formatEntityType(ae.entity.type)}<span class="entity-type">{formatEntityType(ae.entity.type)}</span>{/if}
            </a>
          {:else}
            <span
              class="chip chip-entity"
              title="{ae.entity.name} ({ae.entity.type}) — Relevance: {(ae.salience * 100).toFixed(0)}%, Mentions: {ae.mention_count}"
            >
              {ae.entity.name}
              {#if formatEntityType(ae.entity.type)}<span class="entity-type">{formatEntityType(ae.entity.type)}</span>{/if}
            </span>
          {/if}
        {/each}
      </div>
    {/if}
  </div>

  <!-- Footer / actions -->
  <div class="card-footer">
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      class="read-link"
    >
      Read Article →
    </a>

    {#if showBookmarkButton && actionVariant === "toggle"}
      <button
        on:click={handleBookmarkClick}
        class="bookmark-btn"
        class:bookmarked={isBookmarked}
        aria-label={isBookmarked ? "Remove bookmark" : "Bookmark this article"}
        aria-pressed={isBookmarked}
        title={isBookmarked ? "Remove bookmark" : "Bookmark this article"}
      >
        <svg viewBox="0 0 24 24" fill={isBookmarked ? "currentColor" : "none"} stroke="currentColor">
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
</article>

<style>
  .card {
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: var(--r-xl);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    box-shadow: var(--shadow);
    transition: box-shadow var(--transition), border-color var(--transition), transform var(--transition);
  }
  .card:hover {
    border-color: var(--border-med);
    box-shadow: var(--shadow-md);
    transform: translateY(-1px);
  }

  .card-image-wrapper {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    overflow: hidden;
    flex-shrink: 0;
    background: linear-gradient(135deg, var(--bg-raised) 0%, var(--bg-hover) 100%);
  }
  .card-image { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  .card-image-placeholder {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .card-image-placeholder-icon { width: 2.25rem; height: 2.25rem; color: var(--text-ter); opacity: 0.4; }

  .card-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--sp-3) var(--sp-4) 0;
  }
  .source-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-sec);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .source-favicon { width: 16px; height: 16px; border-radius: 3px; flex-shrink: 0; }
  .pub-date { font-size: 11px; color: var(--text-ter); }

  .card-body {
    padding: var(--sp-3) var(--sp-4);
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--sp-3);
  }
  .card-title {
    font-size: 14px;
    font-weight: 600;
    line-height: 1.4;
    letter-spacing: -0.01em;
    color: var(--text-pri);
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    overflow: hidden;
  }
  .card-desc {
    font-size: 13px;
    color: var(--text-sec);
    line-height: 1.55;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    overflow: hidden;
  }

  /* Sentiment block */
  .sentiment-box {
    background: var(--bg-raised);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    padding: var(--sp-3);
    display: flex;
    flex-direction: column;
    gap: var(--sp-2);
  }
  .sentiment-row { display: flex; align-items: center; justify-content: space-between; gap: var(--sp-3); }
  .sentiment-score { font-size: 12px; font-weight: 600; color: var(--text-pri); white-space: nowrap; }

  .score-bar {
    position: relative;
    height: 4px;
    background: var(--border);
    border-radius: 2px;
    overflow: hidden;
  }
  .score-bar-mid {
    position: absolute;
    left: 50%;
    top: 0;
    width: 1px;
    height: 100%;
    background: var(--border-hi);
    transform: translateX(-0.5px);
    z-index: 1;
  }
  .score-bar-fill { position: absolute; top: 0; height: 100%; border-radius: 2px; }
  .sentiment-note { font-size: 11px; font-style: italic; color: var(--text-ter); line-height: 1.4; }

  /* Chips */
  .chips-row { display: flex; flex-wrap: wrap; gap: 5px; }
  .chip {
    padding: 2px 7px;
    border-radius: 3px;
    font-size: 11px;
    font-weight: 500;
    border: 1px solid;
    white-space: nowrap;
  }
  .chip-topic {
    background: var(--accent-dim);
    color: var(--accent);
    border-color: rgba(124, 92, 252, 0.25);
  }
  .chip-entity {
    background: var(--bg-raised);
    color: var(--text-sec);
    border-color: var(--border-med);
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .chip-entity:hover { border-color: var(--border-hi); text-decoration: none; }
  .entity-type {
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-ter);
  }

  /* Footer */
  .card-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--sp-3) var(--sp-4);
    border-top: 1px solid var(--border);
    margin-top: auto;
  }
  .read-link {
    font-size: 12px;
    font-weight: 600;
    color: var(--accent);
    transition: gap var(--transition);
  }
  .read-link:hover { text-decoration: none; opacity: 0.85; }

  .bookmark-btn {
    width: 28px;
    height: 28px;
    border-radius: var(--r-md);
    background: none;
    border: 1px solid var(--border-med);
    color: var(--text-ter);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all var(--transition);
  }
  .bookmark-btn svg { width: 15px; height: 15px; }
  .bookmark-btn:hover { color: var(--accent); border-color: var(--accent); background: var(--accent-dim); }
  .bookmark-btn.bookmarked { color: var(--accent); border-color: var(--accent); background: var(--accent-dim); }

  .bookmark-card-remove {
    font-size: 12px;
    font-weight: 600;
    font-family: var(--font-ui);
    padding: 4px 10px;
    border-radius: var(--r-md);
    border: 1px solid rgba(251, 113, 133, 0.3);
    background: var(--neg-dim);
    color: var(--neg);
    transition: background var(--transition);
  }
  .bookmark-card-remove:hover { background: rgba(251, 113, 133, 0.28); }
</style>
