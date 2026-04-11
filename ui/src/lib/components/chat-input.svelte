<script lang="ts">
  import { PaperPlaneRight } from "phosphor-svelte";

  interface Props {
    onsubmit: (message: string) => void;
    disabled?: boolean;
  }

  let { onsubmit, disabled = false }: Props = $props();
  let value = $state("");

  function handleSubmit(e: Event) {
    e.preventDefault();
    if (!value.trim() || disabled) return;
    onsubmit(value.trim());
    value = "";
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }
</script>

<form onsubmit={handleSubmit} class="flex gap-2">
  <textarea
    bind:value
    onkeydown={handleKeydown}
    {disabled}
    placeholder="Send a message..."
    rows="1"
    class="flex-1 resize-none rounded-lg border border-neutral-300 bg-white px-4 py-2.5 text-sm focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500 dark:border-neutral-700 dark:bg-neutral-900"
  ></textarea>
  <button
    type="submit"
    disabled={disabled || !value.trim()}
    class="rounded-lg bg-orange-500 px-4 text-white transition-colors hover:bg-orange-600 disabled:opacity-50"
    aria-label="Send message"
  >
    <PaperPlaneRight size={18} />
  </button>
</form>
