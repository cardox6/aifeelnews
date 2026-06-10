import { mergeConfig, defineConfig } from "vitest/config";
import { svelteTesting } from "@testing-library/svelte/vite";
import viteConfig from "./vite.config";

// Test config is kept separate from vite.config.ts on purpose: the production
// build (`vite build` → Firebase Hosting) must never pull in test-only tooling
// (vitest, jsdom, testing-library). Vitest auto-prefers this file over
// vite.config.ts, and we re-use the base config (svelte plugin, etc.) via
// mergeConfig so component compilation matches the real build.
export default mergeConfig(
  viteConfig,
  defineConfig({
    plugins: [
      // Resolves the browser build of Svelte and auto-cleans rendered
      // components between tests.
      svelteTesting(),
    ],
    test: {
      environment: "jsdom",
      include: ["src/**/*.{test,spec}.ts"],
      setupFiles: ["./vitest-setup.ts"],
      // Pin a deterministic API base so api.ts URL assertions don't depend on
      // the host the tests run on. Without this, jsdom reports hostname
      // "localhost" and api.ts would select the local-dev base instead.
      env: {
        VITE_API_BASE_URL: "http://test.local",
      },
    },
  }),
);
