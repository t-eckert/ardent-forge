<script lang="ts">
  import { getThemeStore, type Theme } from "./theme-store.svelte";
  import { Sun, Moon, Monitor } from "phosphor-svelte";

  let store = getThemeStore();

  const options: { value: Theme; icon: typeof Sun }[] = [
    { value: "light", icon: Sun },
    { value: "system", icon: Monitor },
    { value: "dark", icon: Moon },
  ];
</script>

<div
  class="flex gap-1 rounded-lg p-1"
  style="background: var(--color-bench); border: 1px solid var(--color-border);"
>
  {#each options as opt}
    <button
      onclick={() => store.setTheme(opt.value)}
      class="cursor-pointer rounded-md p-1.5 transition-colors"
      style={store.preference === opt.value
        ? 'background: var(--color-paper); color: var(--color-ink);'
        : 'color: var(--color-slate);'}
      aria-label="Set theme to {opt.value}"
      aria-pressed={store.preference === opt.value}
    >
      <opt.icon size={16} />
    </button>
  {/each}
</div>
