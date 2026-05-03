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

<div class="mb-6">
  <h2 class="text-xl font-semibold text-gray-900">Your Bookmarks</h2>
  <p class="text-gray-600">Articles you've saved for later</p>
</div>

{#if !$userStore}
  <div class="text-center py-12">
    <p class="text-gray-600 mb-4">Please sign in to view your bookmarks.</p>
    <button
      on:click={loginWithGoogle}
      class="bg-blue-600 text-white px-4 py-2 rounded-md text-sm hover:bg-blue-700"
    >
      Login with Google
    </button>
  </div>
{:else if error}
  <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-6">
    <div class="flex items-center justify-between">
      <span>Couldn't load bookmarks. {error}</span>
      <button
        on:click={handleRetry}
        class="bg-red-600 text-white px-3 py-1 rounded text-sm hover:bg-red-700"
      >
        Retry
      </button>
    </div>
  </div>
{:else if loading}
  <div class="text-center py-12">
    <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
    <p class="mt-4 text-gray-600">Loading your bookmarks...</p>
  </div>
{:else if items.length === 0}
  <div class="text-center py-12">
    <p class="text-gray-600">
      No bookmarks yet. Click the 🔖 icon on any article in the feed to save it here.
    </p>
  </div>
{:else}
  <div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
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
