<script lang="ts">
  /** Header logo lockup: the animated MoodBubble + the aiFeelNews wordmark. */
  import MoodBubble from "./MoodBubble.svelte";

  interface Props {
    /** Invoked when the logo is clicked (navigate home). */
    onhome?: () => void;
  }
  let { onhome }: Props = $props();

  let mark = $state<MoodBubble>();
</script>

<button
  class="wordmark"
  onclick={onhome}
  onpointerenter={() => mark?.play()}
  aria-label="aiFeelNews — go to home"
><MoodBubble bind:this={mark} score={1} size={26} animate idle />ai<span>Feel</span>News</button>

<style>
  .wordmark :global(svg.mood-bubble) {
    margin-right: 7px;
  }
</style>
