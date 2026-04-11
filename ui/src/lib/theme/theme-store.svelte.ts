import { getContext, setContext } from "svelte";

export type Theme = "light" | "dark" | "system";

const THEME_KEY = Symbol("theme");
const STORAGE_KEY = "ardent-forge-theme";

class ThemeStore {
  preference: Theme = $state("system");
  systemDark: boolean = $state(false);

  effectiveTheme: "light" | "dark" = $derived(
    this.preference === "system"
      ? this.systemDark
        ? "dark"
        : "light"
      : this.preference,
  );

  constructor(initial: Theme = "system") {
    this.preference = initial;

    if (typeof window !== "undefined") {
      const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
      if (stored) this.preference = stored;

      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      this.systemDark = mq.matches;
      mq.addEventListener("change", (e) => {
        this.systemDark = e.matches;
      });

      $effect(() => {
        document.documentElement.setAttribute("data-theme", this.effectiveTheme);
        localStorage.setItem(STORAGE_KEY, this.preference);
      });
    }
  }

  setTheme(theme: Theme) {
    this.preference = theme;
  }
}

export function initThemeStore(initial: Theme = "system"): ThemeStore {
  return setContext(THEME_KEY, new ThemeStore(initial));
}

export function getThemeStore(): ThemeStore {
  return getContext<ThemeStore>(THEME_KEY);
}
