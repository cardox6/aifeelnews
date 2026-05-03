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
  <span class="pagination-page">Page {pageNumber}</span>
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
