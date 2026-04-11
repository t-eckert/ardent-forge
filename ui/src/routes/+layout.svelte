<script lang="ts">
  import type { Snippet } from "svelte";
  import "../app.css";
  import ThemeProvider from "$lib/theme/theme-provider.svelte";
  import Nav from "$lib/components/nav.svelte";

  interface Props {
    children: Snippet;
  }

  let { children }: Props = $props();
</script>

<ThemeProvider>
  <div class="flex min-h-screen">
    <Nav />
    <main class="flex-1 overflow-y-auto p-6">
      {@render children()}
    </main>
  </div>
</ThemeProvider>
