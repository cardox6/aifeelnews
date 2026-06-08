import { writable } from "svelte/store";

export type Theme = "dark" | "light";

const STORAGE_KEY = "aifeelnews-theme";

function readInitial(): Theme {
  if (typeof window === "undefined") return "dark";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "dark" || stored === "light") return stored;
  // Default to dark (the design is dark-first); honour an explicit OS light pref.
  const prefersLight = window.matchMedia?.("(prefers-color-scheme: light)").matches;
  return prefersLight ? "light" : "dark";
}

function applyTheme(theme: Theme): void {
  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("data-theme", theme);
  }
}

const initial = readInitial();
applyTheme(initial);

export const theme = writable<Theme>(initial);

theme.subscribe((value) => {
  applyTheme(value);
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, value);
  }
});

export function toggleTheme(): void {
  theme.update((t) => (t === "dark" ? "light" : "dark"));
}
