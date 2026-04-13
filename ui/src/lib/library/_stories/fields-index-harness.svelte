<script lang="ts">
	import FieldsIndex from '../views/fields-index.svelte';
	import { makeFields } from '$lib/mocks';

	const fields = makeFields();
</script>

<div class="min-h-screen bg-[var(--color-paper)]">
	<FieldsIndex {fields} />
</div>
