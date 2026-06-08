import { writable } from "svelte/store";

export type Theme = "dark" | "light";

const STORAGE_KEY = "aifeelnews-theme";

function readInitial(): Theme {
  if (typeof window === "undefined") return "dark";
  // Dark-first by design: a first-time visitor always sees the intended dark
  // theme (we deliberately do NOT follow the OS prefers-color-scheme, so the
  // app's designed look is the first impression). Returning visitors keep
  // whatever they explicitly toggled to, persisted in localStorage.
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === "light" ? "light" : "dark";
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
