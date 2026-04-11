<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "$lib/api";
  import type { Task, Schedule, HealthResponse } from "$lib/types";
  import TaskCard from "$lib/components/task-card.svelte";
  import EmptyState from "$lib/components/empty-state.svelte";
  import { Lightning, CheckCircle, XCircle, Heartbeat, CalendarBlank } from "phosphor-svelte";

  let tasks = $state<Task[]>([]);
  let schedules = $state<Schedule[]>([]);
  let health = $state<HealthResponse | null>(null);
  let loading = $state(true);

  let activeTasks = $derived(
    tasks.filter(
      (t) =>
        !["completed", "failed", "queued"].includes(t.status),
    ),
  );
  let recentCompleted = $derived(
    tasks.filter((t) => t.status === "completed").slice(0, 5),
  );
  let recentFailed = $derived(
    tasks.filter((t) => t.status === "failed").slice(0, 5),
  );
  let queuedCount = $derived(
    tasks.filter((t) => t.status === "queued").length,
  );

  onMount(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  });

  async function loadData() {
    try {
      const [taskList, scheduleList, healthResp] = await Promise.all([
        api.listTasks(),
        api.listSchedules(),
        api.health(),
      ]);
      tasks = taskList;
      schedules = scheduleList;
      health = healthResp;
    } catch (e) {
      console.error("Failed to load dashboard data:", e);
    } finally {
      loading = false;
    }
  }
</script>

<div class="mx-auto max-w-5xl space-y-8">
  <div class="flex items-center justify-between">
    <h1 class="text-2xl font-bold">Dashboard</h1>
    {#if health}
      <div class="flex items-center gap-1.5 text-sm text-green-600 dark:text-green-400">
        <Heartbeat size={16} weight="fill" />
        Online
      </div>
    {/if}
  </div>

  <!-- Stats -->
  <div class="grid grid-cols-3 gap-4">
    <div class="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <div class="flex items-center gap-2 text-sm text-neutral-500 dark:text-neutral-400">
        <Lightning size={16} />
        Active
      </div>
      <p class="mt-1 text-2xl font-bold">{activeTasks.length}</p>
    </div>
    <div class="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <div class="flex items-center gap-2 text-sm text-neutral-500 dark:text-neutral-400">
        <CheckCircle size={16} />
        Completed
      </div>
      <p class="mt-1 text-2xl font-bold">{recentCompleted.length}</p>
    </div>
    <div class="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <div class="flex items-center gap-2 text-sm text-neutral-500 dark:text-neutral-400">
        <XCircle size={16} />
        Failed
      </div>
      <p class="mt-1 text-2xl font-bold">{recentFailed.length}</p>
    </div>
  </div>

  <!-- Active Tasks -->
  <section>
    <h2 class="mb-3 text-lg font-semibold">
      Active Tasks
      {#if queuedCount > 0}
        <span class="text-sm font-normal text-neutral-400">
          ({queuedCount} queued)
        </span>
      {/if}
    </h2>
    {#if activeTasks.length === 0}
      <EmptyState message="No active tasks" />
    {:else}
      <div class="space-y-2">
        {#each activeTasks as task (task.id)}
          <TaskCard {task} />
        {/each}
      </div>
    {/if}
  </section>

  <!-- Recent Completed -->
  {#if recentCompleted.length > 0}
    <section>
      <h2 class="mb-3 text-lg font-semibold">Recently Completed</h2>
      <div class="space-y-2">
        {#each recentCompleted as task (task.id)}
          <TaskCard {task} />
        {/each}
      </div>
    </section>
  {/if}

  <!-- Recent Failed -->
  {#if recentFailed.length > 0}
    <section>
      <h2 class="mb-3 text-lg font-semibold">Recent Failures</h2>
      <div class="space-y-2">
        {#each recentFailed as task (task.id)}
          <TaskCard {task} />
        {/each}
      </div>
    </section>
  {/if}

  <!-- Upcoming Schedules -->
  {#if schedules.filter((s) => s.enabled).length > 0}
    <section>
      <h2 class="mb-3 text-lg font-semibold">Upcoming Schedules</h2>
      <div class="space-y-2">
        {#each schedules.filter((s) => s.enabled) as schedule (schedule.id)}
          <a
            href="/schedule"
            class="flex items-center gap-3 rounded-lg border border-neutral-200 p-3 transition-colors hover:bg-neutral-50 dark:border-neutral-800 dark:hover:bg-neutral-900"
          >
            <CalendarBlank size={16} class="text-neutral-400" />
            <div class="min-w-0 flex-1">
              <p class="text-sm font-medium">{schedule.name}</p>
              <p class="text-xs text-neutral-400">
                <span class="font-mono">{schedule.cron_expr}</span> &middot; {schedule.task_type}
              </p>
            </div>
          </a>
        {/each}
      </div>
    </section>
  {/if}
</div>
