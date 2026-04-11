<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "$lib/api";
  import type { Task, TaskStatus, CreateTaskRequest } from "$lib/types";
  import TaskCard from "$lib/components/task-card.svelte";
  import EmptyState from "$lib/components/empty-state.svelte";
  import { Plus, X } from "phosphor-svelte";

  let tasks = $state<Task[]>([]);
  let statusFilter = $state<string>("");
  let loading = $state(true);
  let showCreateForm = $state(false);

  // Create form fields
  let newType = $state("code");
  let newTitle = $state("");
  let newDescription = $state("");
  let newRepo = $state("");
  let creating = $state(false);

  let filteredTasks = $derived(
    statusFilter
      ? tasks.filter((t) => t.status === statusFilter)
      : tasks,
  );

  const statuses: TaskStatus[] = [
    "queued",
    "triaging",
    "executing",
    "verifying",
    "delivering",
    "completed",
    "failed",
  ];

  onMount(() => {
    loadTasks();
  });

  async function loadTasks() {
    try {
      tasks = await api.listTasks();
    } catch (e) {
      console.error("Failed to load tasks:", e);
    } finally {
      loading = false;
    }
  }

  async function createTask() {
    if (!newTitle.trim()) return;
    creating = true;
    try {
      const req: CreateTaskRequest = {
        type: newType,
        title: newTitle.trim(),
        description: newDescription.trim(),
      };
      if (newRepo.trim()) req.repo = newRepo.trim();
      await api.createTask(req);
      showCreateForm = false;
      newTitle = "";
      newDescription = "";
      newRepo = "";
      await loadTasks();
    } catch (e) {
      console.error("Failed to create task:", e);
    } finally {
      creating = false;
    }
  }
</script>

<div class="mx-auto max-w-5xl space-y-6">
  <div class="flex items-center justify-between">
    <h1 class="text-2xl font-bold">Tasks</h1>
    <button
      onclick={() => (showCreateForm = !showCreateForm)}
      class="flex items-center gap-1.5 rounded-lg bg-orange-500 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-orange-600"
    >
      {#if showCreateForm}
        <X size={16} />
        Cancel
      {:else}
        <Plus size={16} />
        New Task
      {/if}
    </button>
  </div>

  <!-- Create Form -->
  {#if showCreateForm}
    <form
      onsubmit={(e) => { e.preventDefault(); createTask(); }}
      class="space-y-3 rounded-lg border border-neutral-200 p-4 dark:border-neutral-800"
    >
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label for="task-type" class="mb-1 block text-sm font-medium">Type</label>
          <select
            id="task-type"
            bind:value={newType}
            class="w-full rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          >
            <option value="code">Code</option>
            <option value="research">Research</option>
            <option value="report">Report</option>
            <option value="notebook">Notebook</option>
            <option value="triage">Triage</option>
          </select>
        </div>
        <div>
          <label for="task-repo" class="mb-1 block text-sm font-medium">Repository</label>
          <input
            id="task-repo"
            type="text"
            bind:value={newRepo}
            placeholder="owner/repo (optional)"
            class="w-full rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          />
        </div>
      </div>
      <div>
        <label for="task-title" class="mb-1 block text-sm font-medium">Title</label>
        <input
          id="task-title"
          type="text"
          bind:value={newTitle}
          placeholder="Task title"
          required
          class="w-full rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        />
      </div>
      <div>
        <label for="task-desc" class="mb-1 block text-sm font-medium">Description</label>
        <textarea
          id="task-desc"
          bind:value={newDescription}
          placeholder="Describe the task..."
          rows="3"
          class="w-full rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        ></textarea>
      </div>
      <button
        type="submit"
        disabled={creating || !newTitle.trim()}
        class="rounded-lg bg-orange-500 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-orange-600 disabled:opacity-50"
      >
        {creating ? "Creating..." : "Create Task"}
      </button>
    </form>
  {/if}

  <!-- Filter -->
  <div class="flex flex-wrap gap-2">
    <button
      onclick={() => (statusFilter = "")}
      class="rounded-full px-3 py-1 text-sm transition-colors {statusFilter === ''
        ? 'bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900'
        : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200 dark:bg-neutral-800 dark:text-neutral-400 dark:hover:bg-neutral-700'}"
    >
      All ({tasks.length})
    </button>
    {#each statuses as s}
      {@const count = tasks.filter((t) => t.status === s).length}
      {#if count > 0}
        <button
          onclick={() => (statusFilter = s)}
          class="rounded-full px-3 py-1 text-sm transition-colors {statusFilter === s
            ? 'bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900'
            : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200 dark:bg-neutral-800 dark:text-neutral-400 dark:hover:bg-neutral-700'}"
        >
          {s} ({count})
        </button>
      {/if}
    {/each}
  </div>

  <!-- Task List -->
  {#if loading}
    <p class="text-neutral-400">Loading...</p>
  {:else if filteredTasks.length === 0}
    <EmptyState message="No tasks found" />
  {:else}
    <div class="space-y-2">
      {#each filteredTasks as task (task.id)}
        <TaskCard {task} />
      {/each}
    </div>
  {/if}
</div>
