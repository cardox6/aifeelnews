import { writable, get } from "svelte/store";
import type { BookmarkDto } from "./api";

/**
 * Bookmark state for the signed-in user.
 *
 * Two parallel structures:
 *   - `bookmarkedIds`: a Set of article IDs (drives icon fill on cards)
 *   - `byArticleId`:   a map article_id → bookmark.id (needed for DELETE,
 *     since the backend identifies bookmarks by their own primary key, not
 *     by article id).
 *
 * The store is hydrated once on auth-state-change (from `listBookmarks`) and
 * updated optimistically on add/remove from the article-card click handlers.
 * On error the caller is expected to revert via the inverse mutation.
 */

type BookmarkState = {
  bookmarkedIds: Set<number>;
  byArticleId: Map<number, number>; // article_id -> bookmark.id
};

function createInitialState(): BookmarkState {
  return {
    bookmarkedIds: new Set<number>(),
    byArticleId: new Map<number, number>(),
  };
}

const internalStore = writable<BookmarkState>(createInitialState());

export const bookmarkStore = {
  subscribe: internalStore.subscribe,

  /**
   * Add an article to the bookmark set. If `bookmarkId` is known (post-create)
   * pass it so future deletes can resolve. If unknown (optimistic-add before
   * the POST returns) call again with the bookmarkId once the response lands.
   */
  add(articleId: number, bookmarkId?: number): void {
    internalStore.update((state) => {
      state.bookmarkedIds.add(articleId);
      if (bookmarkId !== undefined) {
        state.byArticleId.set(articleId, bookmarkId);
      }
      return { ...state };
    });
  },

  remove(articleId: number): void {
    internalStore.update((state) => {
      state.bookmarkedIds.delete(articleId);
      state.byArticleId.delete(articleId);
      return { ...state };
    });
  },

  has(articleId: number): boolean {
    return get(internalStore).bookmarkedIds.has(articleId);
  },

  /**
   * Resolve an article id to its server-side bookmark.id (for DELETE).
   * Returns null if the mapping isn't known — the caller should refetch.
   */
  getBookmarkId(articleId: number): number | null {
    return get(internalStore).byArticleId.get(articleId) ?? null;
  },

  hydrate(bookmarks: BookmarkDto[]): void {
    const next = createInitialState();
    for (const bm of bookmarks) {
      next.bookmarkedIds.add(bm.article_id);
      next.byArticleId.set(bm.article_id, bm.id);
    }
    internalStore.set(next);
  },

  reset(): void {
    internalStore.set(createInitialState());
  },
};
