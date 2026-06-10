// Vitest global setup. Registers the jest-dom matchers (toBeDisabled,
// toHaveTextContent, …) on `expect` for component tests. Auto-cleanup of
// rendered Svelte components is handled by the `svelteTesting()` plugin in
// vitest.config.ts, so it is not repeated here.
import "@testing-library/jest-dom/vitest";
