<script lang="ts">
  import { onMount } from "svelte";
  import { userStore, getIdToken, loginWithGoogle } from "./firebase";
  import {
    listBookmarks,
    deleteBookmark,
    fetchArticleById,
    AuthExpiredError,
    type ArticleDto,
    type BookmarkDto,
  } from "./api";
  import { bookmarkStore } from "./bookmarkStore";
  import ArticleCard from "./ArticleCard.svelte";

  type BookmarkedItem = {
    bookmark: BookmarkDto;
    article: ArticleDto;
  };

  let items: BookmarkedItem[] = [];
  let loading = true;
  let error = "";

  async function loadBookmarks() {
    loading = true;
    error = "";

    if (!$userStore) {
      // Render empty state — sign-in prompt is in the template.
      items = [];
      loading = false;
      return;
    }

    try {
      const token = await getIdToken();
      if (!token) {
        items = [];
        loading = false;
        return;
      }

      const bookmarks = await listBookmarks(token);
      bookmarkStore.hydrate(bookmarks);

      // Hydrate each bookmark into a full article view. We fetch in parallel
      // and gracefully drop any 404s (orphaned bookmark whose article was
      // pruned by TTL cleanup).
      const settled = await Promise.allSettled(
        bookmarks.map((bm) => fetchArticleById(bm.article_id))
      );

      const next: BookmarkedItem[] = [];
      bookmarks.forEach((bm, i) => {
        const r = settled[i];
        if (r.status === "fulfilled") {
          next.push({ bookmark: bm, article: r.value });
        } else {
          console.warn(
            `Could not load article ${bm.article_id} for bookmark ${bm.id}:`,
            r.reason
          );
        }
      });
      items = next;
    } catch (e) {
      if (e instanceof AuthExpiredError) {
        error = "Your session expired. Please sign in again.";
      } else {
        console.error("Failed to load bookmarks:", e);
        error =
          e instanceof Error ? e.message : "Failed to load bookmarks";
      }
    } finally {
      loading = false;
    }
  }

  async function handleRemove(event: CustomEvent<{ article: ArticleDto }>) {
    const articleId = event.detail.article.id;
    const item = items.find((i) => i.article.id === articleId);
    if (!item) return;

    const token = await getIdToken();
    if (!token) {
      error = "You must be signed in to remove bookmarks.";
      return;
    }

    // Optimistic removal: drop from local list + store, revert on error.
    const previousItems = items;
    items = items.filter((i) => i.article.id !== articleId);
    bookmarkStore.remove(articleId);

    try {
      await deleteBookmark(item.bookmark.id, token);
    } catch (e) {
      if (e instanceof AuthExpiredError) {
        error = "Your session expired. Please sign in again.";
      } else {
        console.error("Failed to delete bookmark:", e);
        error =
          e instanceof Error ? e.message : "Failed to delete bookmark";
      }
      // Revert
      items = previousItems;
      bookmarkStore.add(articleId, item.bookmark.id);
    }
  }

  function handleRetry() {
    loadBookmarks();
  }

  onMount(() => {
    loadBookmarks();
  });
</script>

<div class="page-head">
  <h1 class="page-title">Your Bookmarks</h1>
  <p class="page-subtitle">Articles you've saved for later</p>
</div>

{#if !$userStore}
  <div class="empty-state">
    <div class="empty-icon" aria-hidden="true">◌</div>
    <p class="empty-title">Sign in to see your bookmarks</p>
    <p class="empty-sub">Bookmarks are tied to your account.</p>
    <button class="btn btn-primary" style="margin-top:var(--sp-4)" on:click={loginWithGoogle}>
      Sign in with Google
    </button>
  </div>
{:else if error}
  <div class="error-banner" role="alert">
    <span class="error-icon" aria-hidden="true">⚠</span>
    <span style="flex:1">Couldn't load bookmarks. {error}</span>
    <button class="btn" on:click={handleRetry}>Retry</button>
  </div>
{:else if loading}
  <div style="text-align:center;padding:var(--sp-10) 0">
    <div class="spinner"></div>
    <p class="text-sec">Loading your bookmarks…</p>
  </div>
{:else if items.length === 0}
  <div class="empty-state">
    <div class="empty-icon" aria-hidden="true">◻</div>
    <p class="empty-title">No bookmarks yet</p>
    <p class="empty-sub">Click the bookmark icon on any article in the feed to save it here.</p>
  </div>
{:else}
  <div class="articles-grid">
    {#each items as item (item.bookmark.id)}
      <ArticleCard
        article={item.article}
        showBookmarkButton={true}
        isBookmarked={true}
        actionVariant="remove"
        on:remove={handleRemove}
      />
    {/each}
  </div>
{/if}

<style>
  .articles-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: var(--sp-5);
    /* Start-align so an expanded sentiment "Why?" panel grows its own card
       rather than stretching the rest of the row. */
    align-items: start;
  }
  .error-icon { font-size: 16px; flex-shrink: 0; }
  @media (max-width: 768px) {
    .articles-grid { grid-template-columns: 1fr; }
  }
</style>
