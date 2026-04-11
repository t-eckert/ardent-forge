<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "$lib/api";
  import type { Schedule } from "$lib/types";
  import ScheduleRow from "$lib/components/schedule-row.svelte";
  import EmptyState from "$lib/components/empty-state.svelte";
  import { Plus, X } from "phosphor-svelte";

  let schedules = $state<Schedule[]>([]);
  let loading = $state(true);
  let showForm = $state(false);

  let newName = $state("");
  let newCron = $state("");
  let newType = $state("report");
  let creating = $state(false);

  onMount(loadSchedules);

  async function loadSchedules() {
    try {
      schedules = await api.listSchedules();
    } catch (e) {
      console.error("Failed to load schedules:", e);
    } finally {
      loading = false;
    }
  }

  async function createSchedule() {
    if (!newName.trim() || !newCron.trim()) return;
    creating = true;
    try {
      await api.createSchedule({
        name: newName.trim(),
        cron_expr: newCron.trim(),
        task_type: newType,
      });
      showForm = false;
      newName = "";
      newCron = "";
      await loadSchedules();
    } catch (e) {
      console.error("Failed to create schedule:", e);
    } finally {
      creating = false;
    }
  }

  async function toggleSchedule(id: string, enabled: boolean) {
    try {
      await api.toggleSchedule(id, enabled);
      await loadSchedules();
    } catch (e) {
      console.error("Failed to toggle schedule:", e);
    }
  }

  async function deleteSchedule(id: string) {
    try {
      await api.deleteSchedule(id);
      await loadSchedules();
    } catch (e) {
      console.error("Failed to delete schedule:", e);
    }
  }
</script>

<div class="mx-auto max-w-3xl space-y-6">
  <div class="flex items-center justify-between">
    <h1 class="text-2xl font-bold">Schedule</h1>
    <button
      onclick={() => (showForm = !showForm)}
      class="flex items-center gap-1.5 rounded-lg bg-orange-500 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-orange-600"
    >
      {#if showForm}
        <X size={16} />
        Cancel
      {:else}
        <Plus size={16} />
        New Schedule
      {/if}
    </button>
  </div>

  {#if showForm}
    <form
      onsubmit={(e) => { e.preventDefault(); createSchedule(); }}
      class="space-y-3 rounded-lg border border-neutral-200 p-4 dark:border-neutral-800"
    >
      <div>
        <label for="sched-name" class="mb-1 block text-sm font-medium">Name</label>
        <input
          id="sched-name"
          type="text"
          bind:value={newName}
          placeholder="Weekly report"
          required
          class="w-full rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        />
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label for="sched-cron" class="mb-1 block text-sm font-medium">Cron Expression</label>
          <input
            id="sched-cron"
            type="text"
            bind:value={newCron}
            placeholder="0 9 * * 1"
            required
            class="w-full rounded-md border border-neutral-300 bg-white px-3 py-1.5 font-mono text-sm dark:border-neutral-700 dark:bg-neutral-900"
          />
        </div>
        <div>
          <label for="sched-type" class="mb-1 block text-sm font-medium">Task Type</label>
          <select
            id="sched-type"
            bind:value={newType}
            class="w-full rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          >
            <option value="report">Report</option>
            <option value="notebook">Notebook</option>
            <option value="code">Code</option>
            <option value="research">Research</option>
            <option value="triage">Triage</option>
          </select>
        </div>
      </div>
      <button
        type="submit"
        disabled={creating || !newName.trim() || !newCron.trim()}
        class="rounded-lg bg-orange-500 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-orange-600 disabled:opacity-50"
      >
        {creating ? "Creating..." : "Create Schedule"}
      </button>
    </form>
  {/if}

  {#if loading}
    <p class="text-neutral-400">Loading...</p>
  {:else if schedules.length === 0}
    <EmptyState message="No scheduled tasks" />
  {:else}
    <div class="space-y-2">
      {#each schedules as schedule (schedule.id)}
        <ScheduleRow
          {schedule}
          ontoggle={toggleSchedule}
          ondelete={deleteSchedule}
        />
      {/each}
    </div>
  {/if}
</div>
