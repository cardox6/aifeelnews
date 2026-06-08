<script lang="ts">
  import { createEventDispatcher } from "svelte";

  export let current: number = 0; // skip value (offset, zero-based)
  export let pageSize: number = 20; // limit
  export let hasMore: boolean = false;

  const dispatch = createEventDispatcher<{ prev: void; next: void }>();

  $: pageNumber = Math.floor(current / pageSize) + 1;
  $: prevDisabled = current === 0;
  $: nextDisabled = !hasMore;

  function handlePrev() {
    if (!prevDisabled) dispatch("prev");
  }

  function handleNext() {
    if (!nextDisabled) dispatch("next");
  }
</script>

<nav class="pagination" aria-label="Article feed pagination">
  <button
    class="pagination-button"
    disabled={prevDisabled}
    on:click={handlePrev}
    aria-label="Previous page"
    type="button"
  >
    ← Prev
  </button>
  <span class="pagination-page mono">Page {pageNumber}</span>
  <button
    class="pagination-button"
    disabled={nextDisabled}
    on:click={handleNext}
    aria-label="Next page"
    type="button"
  >
    Next →
  </button>
</nav>

<style>
  .pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--sp-3);
    padding: var(--sp-4) 0;
  }
  .pagination-button {
    padding: 6px 14px;
    border-radius: var(--r-md);
    border: 1px solid var(--border-med);
    background: var(--bg-raised);
    color: var(--text-sec);
    font-size: 13px;
    font-weight: 500;
    font-family: var(--font-ui);
    transition: all var(--transition);
  }
  .pagination-button:hover:not(:disabled) {
    border-color: var(--accent);
    color: var(--accent);
    background: var(--accent-dim);
  }
  .pagination-button:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
  .pagination-page {
    font-size: 13px;
    color: var(--text-sec);
    min-width: 5rem;
    text-align: center;
  }
</style>
