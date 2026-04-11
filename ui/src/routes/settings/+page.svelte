<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "$lib/api";
  import { Heartbeat } from "phosphor-svelte";

  let health = $state<{ status: string } | null>(null);

  onMount(async () => {
    try {
      health = await api.health();
    } catch (e) {
      console.error("Failed to check health:", e);
    }
  });
</script>

<div class="mx-auto max-w-3xl space-y-6">
  <h1 class="text-2xl font-bold">Settings</h1>

  <div class="space-y-4">
    <!-- System Status -->
    <div class="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <h2 class="mb-3 font-semibold">System Status</h2>
      {#if health}
        <div class="flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
          <Heartbeat size={16} weight="fill" />
          Backend: {health.status}
        </div>
      {:else}
        <p class="text-sm text-red-500">Unable to reach backend</p>
      {/if}
    </div>

    <!-- Info -->
    <div class="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <h2 class="mb-3 font-semibold">About</h2>
      <dl class="space-y-2 text-sm">
        <div class="flex justify-between">
          <dt class="text-neutral-500 dark:text-neutral-400">Version</dt>
          <dd class="font-mono">0.1.0</dd>
        </div>
        <div class="flex justify-between">
          <dt class="text-neutral-500 dark:text-neutral-400">Backend Port</dt>
          <dd class="font-mono">7030</dd>
        </div>
        <div class="flex justify-between">
          <dt class="text-neutral-500 dark:text-neutral-400">Database</dt>
          <dd class="font-mono">SQLite</dd>
        </div>
      </dl>
    </div>

    <p class="text-xs text-neutral-400 dark:text-neutral-500">
      Handler settings, model preferences, and repo configuration will be added here.
      Configure environment variables via 1Password + systemd for now.
    </p>
  </div>
</div>
