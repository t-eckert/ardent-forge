<script lang="ts">
	import type { UserMessage } from '$lib/schemas/thread';
	import { Meta } from '$lib/typography';
	import { formatTime } from '$lib/utils/date';

	interface Props {
		message: UserMessage;
		userName?: string;
	}

	let { message, userName = 'THOMAS' }: Props = $props();
</script>

<div class="flex justify-end">
	<div class="flex flex-col gap-1.5 items-end max-w-[560px]">
		<Meta size="sm">{userName} · {formatTime(message.iso)}</Meta>
		<div
			class="px-4 py-3 bg-[var(--color-ink)] text-[var(--color-paper)] text-sm rounded-[8px] rounded-br-none"
		>
			{message.content}
		</div>
	</div>
</div>
