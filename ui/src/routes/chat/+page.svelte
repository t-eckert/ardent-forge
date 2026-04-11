<script lang="ts">
  import { onMount, tick } from "svelte";
  import { api } from "$lib/api";
  import type { ChatMessage as ChatMessageType } from "$lib/types";
  import ChatMessage from "$lib/components/chat-message.svelte";
  import ChatInput from "$lib/components/chat-input.svelte";
  import EmptyState from "$lib/components/empty-state.svelte";
  import { Trash } from "phosphor-svelte";

  let messages = $state<ChatMessageType[]>([]);
  let streamingContent = $state("");
  let sending = $state(false);
  let messagesEnd: HTMLDivElement;

  onMount(async () => {
    try {
      messages = await api.getMessages();
      await scrollToBottom();
    } catch (e) {
      console.error("Failed to load messages:", e);
    }
  });

  async function scrollToBottom() {
    await tick();
    messagesEnd?.scrollIntoView({ behavior: "smooth" });
  }

  async function sendMessage(content: string) {
    sending = true;
    streamingContent = "";

    // Optimistically add user message
    const userMsg: ChatMessageType = {
      id: crypto.randomUUID(),
      role: "user",
      content,
      task_id: null,
      created_at: new Date().toISOString(),
    };
    messages = [...messages, userMsg];
    await scrollToBottom();

    try {
      for await (const chunk of api.sendMessage(content)) {
        streamingContent += chunk;
        await scrollToBottom();
      }

      // Add the completed assistant message
      const assistantMsg: ChatMessageType = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: streamingContent,
        task_id: null,
        created_at: new Date().toISOString(),
      };
      messages = [...messages, assistantMsg];
      streamingContent = "";
    } catch (e) {
      console.error("Chat error:", e);
      streamingContent = "";
      const errorMsg: ChatMessageType = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `Error: ${e instanceof Error ? e.message : "Something went wrong"}`,
        task_id: null,
        created_at: new Date().toISOString(),
      };
      messages = [...messages, errorMsg];
    } finally {
      sending = false;
      await scrollToBottom();
    }
  }

  async function clearHistory() {
    try {
      await api.clearMessages();
      messages = [];
      streamingContent = "";
    } catch (e) {
      console.error("Failed to clear messages:", e);
    }
  }
</script>

<div class="mx-auto flex h-[calc(100vh-3rem)] max-w-3xl flex-col">
  <!-- Header -->
  <div class="flex items-center justify-between pb-4">
    <h1 class="text-2xl font-bold">Chat</h1>
    {#if messages.length > 0}
      <button
        onclick={clearHistory}
        class="flex items-center gap-1.5 rounded-lg px-2 py-1 text-sm text-neutral-500 transition-colors hover:bg-neutral-100 hover:text-neutral-700 dark:hover:bg-neutral-800 dark:hover:text-neutral-300"
      >
        <Trash size={14} />
        Clear
      </button>
    {/if}
  </div>

  <!-- Messages -->
  <div class="flex-1 space-y-4 overflow-y-auto pb-4">
    {#if messages.length === 0 && !streamingContent}
      <div class="flex h-full items-center justify-center">
        <EmptyState message="Send a message to start chatting with Ardent Forge" />
      </div>
    {:else}
      {#each messages as msg (msg.id)}
        <ChatMessage role={msg.role} content={msg.content} />
      {/each}
      {#if streamingContent}
        <ChatMessage role="assistant" content={streamingContent} />
      {/if}
    {/if}
    <div bind:this={messagesEnd}></div>
  </div>

  <!-- Input -->
  <div class="border-t border-neutral-200 pt-4 dark:border-neutral-800">
    <ChatInput onsubmit={sendMessage} disabled={sending} />
  </div>
</div>
