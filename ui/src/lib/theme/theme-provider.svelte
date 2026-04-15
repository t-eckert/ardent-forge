<script lang="ts">
  import type { Snippet } from "svelte";
  import { initThemeStore, type Theme } from "./theme-store.svelte";

  interface Props {
    theme?: Theme;
    children: Snippet;
  }

  let { theme = "system", children }: Props = $props();

  // Initialize only once with the initial preference; the store listens to
  // prefers-color-scheme + localStorage internally, so subsequent prop
  // changes shouldn't re-create it. untrack() suppresses the warning about
  // reading `theme` during setup (we deliberately only want the first value).
  import { untrack } from "svelte";
  untrack(() => initThemeStore(theme));
</script>

{@render children()}
