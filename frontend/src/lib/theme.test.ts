import { describe, it, expect, beforeEach, vi } from "vitest";
import { get } from "svelte/store";

const STORAGE_KEY = "aifeelnews-theme";

// theme.ts runs side effects (read storage, apply data-theme, subscribe-persist)
// at module-load. To exercise the initial-read branches under different
// preconditions we reset the module registry and re-import per test.
beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  vi.resetModules();
});

describe("initial theme", () => {
  it("defaults to dark when nothing is stored (dark-first by design)", async () => {
    const { theme } = await import("./theme");
    expect(get(theme)).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("restores an explicit 'light' choice from localStorage", async () => {
    localStorage.setItem(STORAGE_KEY, "light");
    const { theme } = await import("./theme");
    expect(get(theme)).toBe("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("falls back to dark for any non-'light' stored value", async () => {
    localStorage.setItem(STORAGE_KEY, "garbage");
    const { theme } = await import("./theme");
    expect(get(theme)).toBe("dark");
  });
});

describe("toggleTheme", () => {
  it("flips dark → light, persisting and applying the DOM attribute", async () => {
    const { theme, toggleTheme } = await import("./theme");
    toggleTheme();
    expect(get(theme)).toBe("light");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("flips back to dark on a second toggle", async () => {
    const { theme, toggleTheme } = await import("./theme");
    toggleTheme();
    toggleTheme();
    expect(get(theme)).toBe("dark");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("dark");
  });
});
