<script lang="ts">
  import { page } from "$app/stores";
  import { onMount } from "svelte";
  import { api } from "$lib/api";
  import type { Task } from "$lib/types";
  import StatusBadge from "$lib/components/status-badge.svelte";
  import { ArrowLeft, GitBranch, Clock, ArrowClockwise } from "phosphor-svelte";

  let task = $state<Task | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(true);

  onMount(async () => {
    try {
      task = await api.getTask($page.params.id);
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load task";
    } finally {
      loading = false;
    }
  });

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleString();
  }
</script>

<div class="mx-auto max-w-3xl space-y-6">
  <a
    href="/tasks"
    class="inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200"
  >
    <ArrowLeft size={14} />
    Back to tasks
  </a>

  {#if loading}
    <p class="text-neutral-400">Loading...</p>
  {:else if error}
    <p class="text-red-500">{error}</p>
  {:else if task}
    <div class="space-y-6">
      <!-- Header -->
      <div>
        <div class="flex items-start justify-between gap-3">
          <h1 class="text-2xl font-bold">{task.title}</h1>
          <StatusBadge status={task.status} />
        </div>
        <p class="mt-2 text-neutral-600 dark:text-neutral-400">
          {task.description}
        </p>
      </div>

      <!-- Metadata -->
      <div
        class="grid grid-cols-2 gap-4 rounded-lg border border-neutral-200 p-4 dark:border-neutral-800"
      >
        <div>
          <p class="text-xs font-medium uppercase text-neutral-400">Type</p>
          <p class="mt-0.5 text-sm">{task.type}</p>
        </div>
        <div>
          <p class="text-xs font-medium uppercase text-neutral-400">Source</p>
          <p class="mt-0.5 text-sm">{task.source}</p>
        </div>
        {#if task.repo}
          <div>
            <p class="text-xs font-medium uppercase text-neutral-400">Repository</p>
            <p class="mt-0.5 flex items-center gap-1 text-sm">
              <GitBranch size={14} />
              {task.repo}
            </p>
          </div>
        {/if}
        <div>
          <p class="text-xs font-medium uppercase text-neutral-400">Retries</p>
          <p class="mt-0.5 flex items-center gap-1 text-sm">
            <ArrowClockwise size={14} />
            {task.retries}
          </p>
        </div>
        <div>
          <p class="text-xs font-medium uppercase text-neutral-400">Created</p>
          <p class="mt-0.5 flex items-center gap-1 text-sm">
            <Clock size={14} />
            {formatDate(task.created_at)}
          </p>
        </div>
        <div>
          <p class="text-xs font-medium uppercase text-neutral-400">Updated</p>
          <p class="mt-0.5 text-sm">{formatDate(task.updated_at)}</p>
        </div>
        {#if task.completed_at}
          <div>
            <p class="text-xs font-medium uppercase text-neutral-400">Completed</p>
            <p class="mt-0.5 text-sm">{formatDate(task.completed_at)}</p>
          </div>
        {/if}
      </div>

      <!-- Result -->
      {#if task.result}
        <div>
          <h2 class="mb-2 text-lg font-semibold">Result</h2>
          <pre
            class="overflow-x-auto rounded-lg bg-neutral-100 p-4 text-sm dark:bg-neutral-900">{JSON.stringify(task.result, null, 2)}</pre>
        </div>
      {/if}

      <!-- Handler Data -->
      {#if Object.keys(task.handler_data).length > 0}
        <div>
          <h2 class="mb-2 text-lg font-semibold">Handler Data</h2>
          <pre
            class="overflow-x-auto rounded-lg bg-neutral-100 p-4 text-sm dark:bg-neutral-900">{JSON.stringify(task.handler_data, null, 2)}</pre>
        </div>
      {/if}

      <!-- ID -->
      <p class="font-mono text-xs text-neutral-400">ID: {task.id}</p>
    </div>
  {/if}
</div>
