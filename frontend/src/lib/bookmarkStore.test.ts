import { describe, it, expect, beforeEach } from "vitest";
import { get } from "svelte/store";
import { bookmarkStore } from "./bookmarkStore";
import type { BookmarkDto } from "./api";

function bm(id: number, articleId: number): BookmarkDto {
  return { id, user_id: 1, article_id: articleId };
}

// The store keeps two parallel structures (a Set of article ids + a Map of
// article_id → bookmark.id). These tests pin that they stay consistent — the
// classic place a state bug hides.
beforeEach(() => {
  bookmarkStore.reset();
});

describe("add", () => {
  it("marks the article bookmarked; bookmark id is unknown until provided", () => {
    bookmarkStore.add(99);
    expect(bookmarkStore.has(99)).toBe(true);
    // optimistic add before the POST returns → no server id yet
    expect(bookmarkStore.getBookmarkId(99)).toBeNull();
  });

  it("records the server bookmark id when supplied", () => {
    bookmarkStore.add(99, 7);
    expect(bookmarkStore.has(99)).toBe(true);
    expect(bookmarkStore.getBookmarkId(99)).toBe(7);
  });

  it("resolves the id on a second add (optimistic-add → POST-resolved)", () => {
    bookmarkStore.add(99); // optimistic
    bookmarkStore.add(99, 7); // resolved with server id
    expect(bookmarkStore.getBookmarkId(99)).toBe(7);
    expect(bookmarkStore.has(99)).toBe(true);
  });

  it("reflects into subscribers", () => {
    bookmarkStore.add(99, 7);
    const state = get(bookmarkStore);
    expect(state.bookmarkedIds.has(99)).toBe(true);
    expect(state.byArticleId.get(99)).toBe(7);
  });
});

describe("remove", () => {
  it("clears both the membership and the id mapping", () => {
    bookmarkStore.add(99, 7);
    bookmarkStore.remove(99);
    expect(bookmarkStore.has(99)).toBe(false);
    expect(bookmarkStore.getBookmarkId(99)).toBeNull();
  });

  it("is a no-op for an unknown article", () => {
    expect(() => bookmarkStore.remove(12345)).not.toThrow();
    expect(bookmarkStore.has(12345)).toBe(false);
  });
});

describe("has / getBookmarkId on unknown ids", () => {
  it("returns false / null", () => {
    expect(bookmarkStore.has(404)).toBe(false);
    expect(bookmarkStore.getBookmarkId(404)).toBeNull();
  });
});

describe("hydrate", () => {
  it("rebuilds both structures from a bookmark list", () => {
    bookmarkStore.hydrate([bm(7, 99), bm(8, 100)]);
    expect(bookmarkStore.has(99)).toBe(true);
    expect(bookmarkStore.has(100)).toBe(true);
    expect(bookmarkStore.getBookmarkId(99)).toBe(7);
    expect(bookmarkStore.getBookmarkId(100)).toBe(8);
  });

  it("replaces prior state rather than merging", () => {
    bookmarkStore.add(1, 1);
    bookmarkStore.hydrate([bm(8, 100)]);
    expect(bookmarkStore.has(1)).toBe(false); // gone after re-hydrate
    expect(bookmarkStore.has(100)).toBe(true);
  });

  it("hydrating an empty list clears the store", () => {
    bookmarkStore.add(1, 1);
    bookmarkStore.hydrate([]);
    expect(get(bookmarkStore).bookmarkedIds.size).toBe(0);
  });
});

describe("reset", () => {
  it("empties both structures (used on sign-out)", () => {
    bookmarkStore.hydrate([bm(7, 99), bm(8, 100)]);
    bookmarkStore.reset();
    const state = get(bookmarkStore);
    expect(state.bookmarkedIds.size).toBe(0);
    expect(state.byArticleId.size).toBe(0);
  });
});
