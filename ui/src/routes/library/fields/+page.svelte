<script lang="ts">
	import { FieldsIndex } from '$lib/library';
	import type { PageData } from './$types';

	interface Props {
		data: PageData;
	}
	let { data }: Props = $props();
</script>

<FieldsIndex fields={data.fields} />
