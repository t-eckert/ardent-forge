<script lang="ts">
  import type { Schedule } from "$lib/types";
  import { Trash, ToggleLeft, ToggleRight } from "phosphor-svelte";

  interface Props {
    schedule: Schedule;
    ontoggle: (id: string, enabled: boolean) => void;
    ondelete: (id: string) => void;
  }

  let { schedule, ontoggle, ondelete }: Props = $props();
</script>

<div
  class="flex items-center justify-between rounded-lg border border-neutral-200 px-4 py-3 dark:border-neutral-800"
>
  <div class="min-w-0 flex-1">
    <div class="flex items-center gap-2">
      <h3 class="font-medium">{schedule.name}</h3>
      {#if !schedule.enabled}
        <span class="text-xs text-neutral-400">(disabled)</span>
      {/if}
    </div>
    <p class="mt-0.5 text-sm text-neutral-500 dark:text-neutral-400">
      <span class="font-mono text-xs">{schedule.cron_expr}</span>
      &middot; {schedule.task_type}
    </p>
  </div>
  <div class="flex items-center gap-2">
    <button
      onclick={() => ontoggle(schedule.id, !schedule.enabled)}
      class="rounded p-1.5 text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-600 dark:hover:bg-neutral-800 dark:hover:text-neutral-300"
      aria-label={schedule.enabled ? "Disable schedule" : "Enable schedule"}
    >
      {#if schedule.enabled}
        <ToggleRight size={20} weight="fill" class="text-green-500" />
      {:else}
        <ToggleLeft size={20} />
      {/if}
    </button>
    <button
      onclick={() => ondelete(schedule.id)}
      class="rounded p-1.5 text-neutral-400 transition-colors hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950"
      aria-label="Delete schedule"
    >
      <Trash size={16} />
    </button>
  </div>
</div>
