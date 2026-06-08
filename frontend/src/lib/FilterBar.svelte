<script lang="ts">
  import { createEventDispatcher, onDestroy } from "svelte";
  import type { SourceDto } from "./api";

  export let sentiment: string = "";
  export let category: string = "";
  export let sourceId: number | "" = "";
  export let search: string = "";
  export let categories: string[] = [];
  export let sources: SourceDto[] = [];

  // On narrow phones the three dropdowns sit 3-across, where the full
  // "All sentiments/categories/sources" labels would clip. Use short labels
  // there ("Sentiment"/"Category"/"Source") and the full ones on wider screens.
  // <option> text can't be CSS-toggled, so we pick it reactively via matchMedia.
  let isNarrow = false;
  if (typeof window !== "undefined" && window.matchMedia) {
    const mq = window.matchMedia("(max-width: 600px)");
    isNarrow = mq.matches;
    const onChange = (e: MediaQueryListEvent) => (isNarrow = e.matches);
    mq.addEventListener("change", onChange);
    onDestroy(() => mq.removeEventListener("change", onChange));
  }

  const dispatch = createEventDispatcher<{
    change: {
      sentiment: string;
      category: string;
      sourceId: number | "";
      search: string;
    };
  }>();

  // Debounce the search input so we don't fire one fetch per keystroke.
  let searchDebounce: ReturnType<typeof setTimeout> | null = null;

  function emitChange() {
    dispatch("change", {
      sentiment,
      category,
      sourceId,
      search,
    });
  }

  function handleSelectChange() {
    // selects are non-debounced — change fires once per user pick.
    emitChange();
  }

  function handleSearchInput(event: Event) {
    const target = event.target as HTMLInputElement;
    search = target.value;
    if (searchDebounce !== null) clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
      emitChange();
      searchDebounce = null;
    }, 300);
  }

  function handleSourceChange(event: Event) {
    const target = event.target as HTMLSelectElement;
    sourceId = target.value === "" ? "" : Number(target.value);
    emitChange();
  }
</script>

<div class="filter-bar" role="search" aria-label="Filter articles">
  <select
    class="filter-select"
    bind:value={sentiment}
    on:change={handleSelectChange}
    aria-label="Filter by sentiment"
  >
    <option value="">{isNarrow ? "Sentiment" : "All sentiments"}</option>
    <option value="positive">Positive</option>
    <option value="negative">Negative</option>
    <option value="neutral">Neutral</option>
  </select>

  <select
    class="filter-select"
    bind:value={category}
    on:change={handleSelectChange}
    aria-label="Filter by category"
  >
    <option value="">{isNarrow ? "Category" : "All categories"}</option>
    {#each categories as cat}
      <option value={cat}>{cat.charAt(0).toUpperCase() + cat.slice(1)}</option>
    {/each}
  </select>

  <select
    class="filter-select"
    value={sourceId === "" ? "" : String(sourceId)}
    on:change={handleSourceChange}
    aria-label="Filter by source"
  >
    <option value="">{isNarrow ? "Source" : "All sources"}</option>
    {#each sources as src}
      <option value={String(src.id)}>{src.name}</option>
    {/each}
  </select>

  <div class="search-wrap">
    <span class="search-icon" aria-hidden="true">⌕</span>
    <input
      type="search"
      class="search-input"
      placeholder="Search titles…"
      value={search}
      on:input={handleSearchInput}
      aria-label="Search article titles"
    />
  </div>
</div>

<style>
  .filter-bar {
    display: flex;
    align-items: center;
    /* row-gap > column-gap so wrapped rows aren't cramped together */
    gap: var(--sp-3) var(--sp-4);
    flex-wrap: wrap;
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: var(--sp-4) var(--sp-5);
    margin-bottom: var(--sp-6);
    box-shadow: var(--shadow);
  }
  .filter-select {
    min-width: 8rem;
    flex: 0 1 auto;
  }
  .search-wrap {
    position: relative;
    flex: 1 1 200px;
    min-width: 180px;
    max-width: 320px;
    margin-left: auto;
  }
  .search-wrap .search-input { width: 100%; padding-left: 30px; }
  .search-icon {
    position: absolute;
    left: 9px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-ter);
    font-size: 14px;
    pointer-events: none;
  }

  /* Narrow phones: lay the bar out as an explicit 2-row grid — the three short
     dropdowns share one row (3 columns), the search spans the full width below.
     This is half the height of four stacked controls and avoids the uneven
     flex-wrap. Touch targets stay 44px (set on the controls themselves). */
  @media (max-width: 600px) {
    .filter-bar {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: var(--sp-2);
      padding: var(--sp-3);
    }
    /* 2 dropdowns per row gives each ~190px — enough for the short labels
       plus the arrow without clipping. The 3rd select and the search each
       span the full width below. Three compact rows, ~half the original
       four-stack height. */
    .filter-select {
      min-width: 0;
      max-width: none;
    }
    .filter-select:nth-of-type(3) {
      grid-column: 1 / -1;
    }
    .search-wrap {
      grid-column: 1 / -1;
      min-width: 0;
      max-width: none;
      margin-left: 0;
    }
  }
</style>
