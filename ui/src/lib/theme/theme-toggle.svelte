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

<div class="flex gap-1 rounded-lg bg-neutral-200 p-1 dark:bg-neutral-800">
  {#each options as opt}
    <button
      onclick={() => store.setTheme(opt.value)}
      class="rounded-md p-1.5 transition-colors {store.preference === opt.value
        ? 'bg-white text-neutral-900 shadow-sm dark:bg-neutral-700 dark:text-neutral-100'
        : 'text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300'}"
      aria-label="Set theme to {opt.value}"
    >
      <opt.icon size={16} />
    </button>
  {/each}
</div>
