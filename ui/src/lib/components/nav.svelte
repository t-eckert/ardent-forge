<script lang="ts">
  import { page } from "$app/stores";
  import { cn } from "$lib/utils";
  import {
    Gauge,
    ListChecks,
    ChatCircle,
    CalendarBlank,
    GearSix,
  } from "phosphor-svelte";
  import ThemeToggle from "$lib/theme/theme-toggle.svelte";

  const links = [
    { href: "/", label: "Dashboard", icon: Gauge },
    { href: "/tasks", label: "Tasks", icon: ListChecks },
    { href: "/chat", label: "Chat", icon: ChatCircle },
    { href: "/schedule", label: "Schedule", icon: CalendarBlank },
    { href: "/settings", label: "Settings", icon: GearSix },
  ];
</script>

<nav
  class="flex h-screen w-56 flex-col border-r border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900"
>
  <div class="flex items-center gap-2 px-4 py-5">
    <span class="text-lg font-bold text-orange-500">Ardent Forge</span>
  </div>

  <div class="flex flex-1 flex-col gap-1 px-2">
    {#each links as link}
      {@const active =
        link.href === "/"
          ? $page.url.pathname === "/"
          : $page.url.pathname.startsWith(link.href)}
      <a
        href={link.href}
        class={cn(
          "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
          active
            ? "bg-orange-50 text-orange-600 dark:bg-orange-950 dark:text-orange-400"
            : "text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800",
        )}
      >
        <link.icon size={20} weight={active ? "fill" : "regular"} />
        {link.label}
      </a>
    {/each}
  </div>

  <div class="border-t border-neutral-200 px-4 py-3 dark:border-neutral-800">
    <ThemeToggle />
  </div>
</nav>
