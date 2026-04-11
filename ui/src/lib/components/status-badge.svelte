<script lang="ts">
  import { cn } from "$lib/utils";
  import type { TaskStatus } from "$lib/types";

  interface Props {
    status: TaskStatus;
  }

  let { status }: Props = $props();

  const colors: Record<TaskStatus, string> = {
    queued: "bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400",
    triaging: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-400",
    executing: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400",
    verifying: "bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-400",
    delivering: "bg-cyan-100 text-cyan-700 dark:bg-cyan-950 dark:text-cyan-400",
    completed: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-400",
    failed: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400",
  };
</script>

<span
  class={cn(
    "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
    colors[status],
  )}
>
  {status}
</span>
