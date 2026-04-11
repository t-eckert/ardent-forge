<script lang="ts">
  import type { Task } from "$lib/types";
  import StatusBadge from "./status-badge.svelte";

  interface Props {
    task: Task;
  }

  let { task }: Props = $props();

  function timeAgo(iso: string): string {
    const seconds = Math.floor(
      (Date.now() - new Date(iso).getTime()) / 1000,
    );
    if (seconds < 60) return "just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }
</script>

<a
  href="/tasks/{task.id}"
  class="block rounded-lg border border-neutral-200 p-4 transition-colors hover:border-neutral-300 hover:bg-neutral-50 dark:border-neutral-800 dark:hover:border-neutral-700 dark:hover:bg-neutral-900"
>
  <div class="flex items-start justify-between gap-2">
    <div class="min-w-0 flex-1">
      <h3 class="truncate font-medium">{task.title}</h3>
      <p class="mt-1 truncate text-sm text-neutral-500 dark:text-neutral-400">
        {task.type}{task.repo ? ` · ${task.repo}` : ""}
      </p>
    </div>
    <StatusBadge status={task.status} />
  </div>
  <p class="mt-2 text-xs text-neutral-400 dark:text-neutral-500">
    {timeAgo(task.updated_at)}
  </p>
</a>
