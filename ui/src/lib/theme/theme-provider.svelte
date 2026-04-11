<script lang="ts">
  import type { Snippet } from "svelte";
  import { initThemeStore, type Theme } from "./theme-store.svelte";

  interface Props {
    theme?: Theme;
    children: Snippet;
  }

  let { theme = "system", children }: Props = $props();
  initThemeStore(theme);
</script>

{@render children()}
