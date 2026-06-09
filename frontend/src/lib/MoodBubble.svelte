<script lang="ts">
  /**
   * MoodBubble — the aiFeelNews bubble mark whose curve expresses sentiment.
   * Shared by the header Logo (animated, score = +1 smile) and, optionally,
   * article cards (score = the article's sentiment_score). The mouth is driven
   * by a single value m ∈ [-1, 1]: +1 smile, 0 flat, -1 frown.
   *
   * Runes-mode component (Svelte 5). Interops with the legacy App shell.
   */
  import { onMount, onDestroy, untrack } from "svelte";
  import { Spring } from "svelte/motion";

  interface Props {
    /** Resting mood, -1 (frown) … +1 (smile). For articles, pass sentiment_score. */
    score?: number;
    /** Rendered px size (square). */
    size?: number;
    /** Spring the mouth in from flat on mount; otherwise render score statically. */
    animate?: boolean;
    /** Replay the morph on pointer-enter of the mark itself. */
    interactive?: boolean;
    /** Periodically dip into a gentle frown and re-smile (subtle idle motion). */
    idle?: boolean;
    /** Idle-morph interval in ms (min 1500). */
    idleInterval?: number;
    /** How deep the idle dip goes, in mood units (0 = flat, -1 = full frown). */
    idleDepth?: number;
    /** Mouth stroke colour. Defaults to the positive-sentiment emerald. */
    curveColor?: string;
    /** Speech-bubble fill. */
    bubbleColor?: string;
    /** Rounded-tile fill. Defaults to the brand accent token. */
    brandColor?: string;
    /** Accessible name. When omitted the mark is decorative (aria-hidden). */
    label?: string;
    stiffness?: number;
    damping?: number;
  }

  let {
    score = 0,
    size = 28,
    animate = false,
    interactive = false,
    idle = false,
    idleInterval = 5000,
    idleDepth = -0.8,
    curveColor = "#34D399",
    bubbleColor = "#ffffff",
    brandColor = "var(--accent)",
    label = "",
    stiffness = 0.12,
    damping = 0.55,
  }: Props = $props();

  const clamp = (n: number): number => Math.max(-1, Math.min(1, n));
  const resting = $derived(clamp(score));

  const reduced =
    typeof window !== "undefined" &&
    !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  // One spring drives the mouth value; start flat when we mean to animate it in.
  // Initial values are read once on purpose (untrack documents that intent).
  const mouth = untrack(
    () => new Spring(animate && !reduced ? 0 : resting, { stiffness, damping }),
  );

  // Endpoints rise as the control point dips (and vice-versa) → a real mouth.
  const d = $derived(
    `M30 ${50 - mouth.current * 10} Q50 ${50 + mouth.current * 10} 70 ${50 - mouth.current * 10}`,
  );

  /** Replay: snap to flat, then spring to the resting mood (or jump if reduced motion). */
  export function play(): void {
    if (reduced) {
      mouth.set(resting, { instant: true });
      return;
    }
    mouth.set(0, { instant: true });
    mouth.target = resting;
  }

  // Idle "mood": briefly ease the smile down into a gentle frown, then let it
  // re-form. Eased both ways (no snap). Skipped when the tab is hidden or the
  // user prefers reduced motion.
  let breathTimer: ReturnType<typeof setTimeout> | null = null;
  function idleBreath(): void {
    if (reduced || (typeof document !== "undefined" && document.hidden)) return;
    mouth.target = idleDepth;
    breathTimer = setTimeout(() => {
      mouth.target = resting;
    }, 1300);
  }

  // Static instances (no entrance, no idle) track score changes instantly.
  $effect(() => {
    if (!animate && !idle) mouth.set(resting, { instant: true });
  });

  let breathInterval: ReturnType<typeof setInterval> | null = null;
  onMount(() => {
    if (animate && !reduced) mouth.target = resting;
    if (idle && !reduced) {
      breathInterval = setInterval(idleBreath, Math.max(1500, idleInterval));
    }
  });

  onDestroy(() => {
    if (breathInterval !== null) clearInterval(breathInterval);
    if (breathTimer !== null) clearTimeout(breathTimer);
  });
</script>

<svg
  class="mood-bubble"
  viewBox="0 0 100 100"
  width={size}
  height={size}
  role={label ? "img" : undefined}
  aria-label={label || undefined}
  aria-hidden={label ? undefined : "true"}
  onpointerenter={interactive ? play : undefined}
>
  <rect width="100" height="100" rx="22" fill={brandColor} />
  <rect x="14" y="17" width="72" height="48" rx="15" fill={bubbleColor} />
  <polygon points="36,63 36,80 54,64" fill={bubbleColor} />
  <path d={d} fill="none" stroke={curveColor} stroke-width="10" stroke-linecap="round" />
</svg>

<style>
  .mood-bubble {
    display: inline-block;
    vertical-align: middle;
    flex-shrink: 0;
  }
</style>
