<script lang="ts">
  // EN/DE content-language toggle rendered as two rounded SVG flags.
  // SVG (not flag emoji) is used because Windows browsers render the
  // regional-indicator emoji as plain letters ("GB"/"DE") instead of flags.
  // Inline SVG renders identically on every platform.
  //
  // Svelte 5 runes API (matches Logo.svelte): props via $props(), callback
  // invoked through the `onchange?.(...)` accessor, native `onclick`.
  interface Props {
    language?: string;
    onchange?: (lang: string) => void;
  }
  let { language = "en", onchange }: Props = $props();
</script>

<div class="flag-toggle" role="group" aria-label="Content language">
  <button
    type="button"
    class="flag-btn"
    class:flag-active={language === "en"}
    onclick={() => onchange?.("en")}
    aria-pressed={language === "en"}
    aria-label="English news"
    title="English"
  >
    <!-- Union Jack. Drawn in a 60x30 box, clipped to a circle. White diagonals
         first, then the counterchanged red diagonals, then the white+red upright
         cross on top. -->
    <svg viewBox="0 0 60 30" aria-hidden="true">
      <clipPath id="uk-round"><circle cx="30" cy="15" r="15" /></clipPath>
      <g clip-path="url(#uk-round)">
        <rect width="60" height="30" fill="#012169" />
        <!-- white diagonals -->
        <path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" stroke-width="6" />
        <!-- red counterchanged diagonals (each half offset so they read as the
             real Union Jack rather than a plain X) -->
        <path d="M0,0 L30,15 M30,15 L60,30" stroke="#C8102E" stroke-width="2"
          transform="translate(2,0)" />
        <path d="M60,0 L30,15 M30,15 L0,30" stroke="#C8102E" stroke-width="2"
          transform="translate(-2,0)" />
        <!-- upright cross: white then red -->
        <path d="M30,0 V30 M0,15 H60" stroke="#fff" stroke-width="10" />
        <path d="M30,0 V30 M0,15 H60" stroke="#C8102E" stroke-width="6" />
      </g>
    </svg>
  </button>

  <button
    type="button"
    class="flag-btn"
    class:flag-active={language === "de"}
    onclick={() => onchange?.("de")}
    aria-pressed={language === "de"}
    aria-label="German news"
    title="Deutsch"
  >
    <!-- Germany: black / red / gold horizontal bands -->
    <svg viewBox="0 0 60 30" aria-hidden="true">
      <clipPath id="de-round"><circle cx="30" cy="15" r="15" /></clipPath>
      <g clip-path="url(#de-round)">
        <rect width="60" height="10" y="0" fill="#000" />
        <rect width="60" height="10" y="10" fill="#DD0000" />
        <rect width="60" height="10" y="20" fill="#FFCE00" />
      </g>
    </svg>
  </button>
</div>

<style>
  .flag-toggle {
    display: inline-flex;
    align-items: center;
    gap: var(--sp-2);
  }
  .flag-btn {
    width: 28px;
    height: 28px;
    padding: 0;
    border: 1px solid var(--border-med);
    border-radius: 50%;        /* round flags */
    background: var(--bg-raised);
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    cursor: pointer;
    opacity: 0.5;              /* inactive flags read as "off" */
    transition: all var(--transition);
  }
  .flag-btn svg {
    width: 100%;
    height: 100%;
    display: block;
    border-radius: 50%;
  }
  .flag-btn:hover { opacity: 0.85; border-color: var(--border-hi); }
  .flag-active {
    opacity: 1;                /* full-colour = selected */
    border-color: var(--accent);
    box-shadow: var(--accent-glow);
  }
</style>
