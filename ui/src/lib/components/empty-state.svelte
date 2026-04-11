<script lang="ts">
  interface Props {
    message: string;
  }

  let { message }: Props = $props();
</script>

<div
  class="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-neutral-200 py-12 dark:border-neutral-800"
>
  <p class="text-sm text-neutral-400 dark:text-neutral-500">{message}</p>
</div>
