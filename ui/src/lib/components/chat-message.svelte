<script lang="ts">
  import { cn } from "$lib/utils";
  import { Robot, User } from "phosphor-svelte";

  interface Props {
    role: "user" | "assistant";
    content: string;
  }

  let { role, content }: Props = $props();
</script>

<div
  class={cn(
    "flex gap-3",
    role === "user" ? "flex-row-reverse" : "flex-row",
  )}
>
  <div
    class={cn(
      "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
      role === "user"
        ? "bg-orange-100 text-orange-600 dark:bg-orange-950 dark:text-orange-400"
        : "bg-neutral-200 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400",
    )}
  >
    {#if role === "user"}
      <User size={16} weight="fill" />
    {:else}
      <Robot size={16} weight="fill" />
    {/if}
  </div>
  <div
    class={cn(
      "max-w-[75%] rounded-lg px-4 py-2.5 text-sm",
      role === "user"
        ? "bg-orange-500 text-white"
        : "bg-neutral-100 text-neutral-900 dark:bg-neutral-800 dark:text-neutral-100",
    )}
  >
    <p class="whitespace-pre-wrap">{content}</p>
  </div>
</div>
