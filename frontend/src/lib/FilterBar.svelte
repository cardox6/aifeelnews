<script lang="ts">
  import { createEventDispatcher, onDestroy } from "svelte";
  import type { SourceDto } from "./api";

  export let sentiment: string = "";
  export let category: string = "";
  export let sourceId: number | "" = "";
  export let search: string = "";
  // ISO-8601 datetime strings (or "" when unset) — already-resolved bounds the
  // parent forwards to the API. The UI below (preset dropdown + custom range)
  // owns how they're produced.
  export let publishedAfter: string = "";
  export let publishedBefore: string = "";
  export let categories: string[] = [];
  export let sources: SourceDto[] = [];

  // Date filtering is driven by a single dropdown:
  //   • "" = any time
  //   • "1" / "7" / "30" = rolling-day presets → published_after computed from
  //     the current clock, published_before left open.
  //   • "custom" = reveal a From/To pair of <input type="date">, normalised to
  //     start-of-day / end-of-day so "to the 9th" includes all of the 9th.
  // Seed from any incoming bounds so a range restored by the parent (e.g. from
  // the URL in a later change) shows up; ISO datetime → its yyyy-mm-dd.
  const isoToDateInput = (iso: string): string => (iso ? iso.slice(0, 10) : "");
  let customFrom: string = isoToDateInput(publishedAfter); // yyyy-mm-dd
  let customTo: string = isoToDateInput(publishedBefore); // yyyy-mm-dd
  let datePreset: string = customFrom || customTo ? "custom" : "";

  $: showCustomRange = datePreset === "custom";

  function resolveDateBounds(): { after: string; before: string } {
    if (datePreset === "custom") {
      // Send local start/end-of-day so the inclusive backend bounds cover the
      // whole picked day.
      const after = customFrom ? new Date(`${customFrom}T00:00:00`).toISOString() : "";
      const before = customTo ? new Date(`${customTo}T23:59:59.999`).toISOString() : "";
      return { after, before };
    }
    if (datePreset) {
      const days = Number(datePreset);
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - days);
      return { after: cutoff.toISOString(), before: "" };
    }
    return { after: "", before: "" };
  }

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
      publishedAfter: string;
      publishedBefore: string;
    };
  }>();

  // Debounce the search input so we don't fire one fetch per keystroke.
  let searchDebounce: ReturnType<typeof setTimeout> | null = null;

  function emitChange() {
    const { after, before } = resolveDateBounds();
    dispatch("change", {
      sentiment,
      category,
      sourceId,
      search,
      publishedAfter: after,
      publishedBefore: before,
    });
  }

  function handleSelectChange() {
    // selects are non-debounced — change fires once per user pick.
    emitChange();
  }

  function handlePresetChange() {
    // Leaving "custom" discards the From/To values so a later re-select starts
    // clean and a rolling preset never carries a stale range underneath it.
    if (datePreset !== "custom") {
      customFrom = "";
      customTo = "";
    }
    emitChange();
  }

  function handleCustomDateChange() {
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

  <select
    class="filter-select"
    bind:value={datePreset}
    on:change={handlePresetChange}
    aria-label="Filter by date range"
  >
    <option value="">{isNarrow ? "Date" : "Any time"}</option>
    <option value="1">Last 24 hours</option>
    <option value="7">Last 7 days</option>
    <option value="30">Last 30 days</option>
    <option value="custom">Custom range…</option>
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

  {#if showCustomRange}
    <div class="custom-range">
      <label class="range-field">
        <span class="range-label">From</span>
        <input
          type="date"
          class="filter-select date-input"
          bind:value={customFrom}
          on:change={handleCustomDateChange}
          max={customTo || undefined}
          aria-label="Published from date"
        />
      </label>
      <label class="range-field">
        <span class="range-label">To</span>
        <input
          type="date"
          class="filter-select date-input"
          bind:value={customTo}
          on:change={handleCustomDateChange}
          min={customFrom || undefined}
          aria-label="Published to date"
        />
      </label>
    </div>
  {/if}
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

  /* Custom from/to range: revealed only when "Custom range…" is picked. Its own
     full-width row, set off from the controls above by a hairline + top padding
     so it reads as a sub-panel rather than crowding the dropdowns. */
  .custom-range {
    flex: 1 1 100%;
    display: flex;
    align-items: center;
    gap: var(--sp-3) var(--sp-5);
    flex-wrap: wrap;
    padding-top: var(--sp-3);
    border-top: 1px solid var(--border);
  }
  .range-field {
    display: inline-flex;
    align-items: center;
    gap: var(--sp-2);
  }
  .range-label {
    color: var(--text-sec);
    font-size: 0.8rem;
    font-weight: 500;
  }
  /* Native date inputs collapse very narrow without a floor; keep them legible
     and matched in width. */
  .date-input {
    min-width: 9.5rem;
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
       plus the arrow without clipping. Sentiment + category share row 1;
       source + date-preset share row 2; the search and the custom range each
       span the full width below. */
    .filter-select {
      min-width: 0;
      max-width: none;
    }
    .search-wrap {
      grid-column: 1 / -1;
      min-width: 0;
      max-width: none;
      margin-left: 0;
    }
    .custom-range {
      grid-column: 1 / -1;
    }
    /* Each From/To field takes one grid column so the two date inputs sit
       side-by-side instead of stacking. */
    .range-field {
      flex: 1 1 0;
      min-width: 0;
    }
    .date-input {
      flex: 1 1 0;
      width: 100%;
    }
  }
</style>
