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

<div class="filter-bar">
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

  <input
    type="search"
    class="search-input"
    placeholder="Search titles..."
    value={search}
    on:input={handleSearchInput}
    aria-label="Search article titles"
  />
</div>
