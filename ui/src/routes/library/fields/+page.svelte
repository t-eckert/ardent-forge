<script lang="ts">
	import { FieldsIndex } from '$lib/library';
	import { makeFields } from '$lib/mocks';

	const fields = makeFields();
</script>

<FieldsIndex {fields} />
