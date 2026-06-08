<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import type { SourceDto } from "./api";

  export let sentiment: string = "";
  export let category: string = "";
  export let sourceId: number | "" = "";
  export let search: string = "";
  export let categories: string[] = [];
  export let sources: SourceDto[] = [];

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
    <option value="">All sentiments</option>
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
    <option value="">All categories</option>
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
    <option value="">All sources</option>
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

  /* Narrow phones: stack each control full-width instead of wrapping the
     8rem-min selects into a cramped, uneven grid with an auto-margin gap. */
  @media (max-width: 600px) {
    .filter-select,
    .search-wrap {
      flex: 1 1 100%;
      min-width: 0;
      max-width: none;
      margin-left: 0;
    }
  }
</style>
