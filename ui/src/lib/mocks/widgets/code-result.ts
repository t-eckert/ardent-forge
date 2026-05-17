import type { CodeResultPayload } from '$lib/schemas/widgets';

export function makeCodeResultPayload(): CodeResultPayload {
	return {
		tool: 'code.result',
		prUrl: 'https://github.com/t-eckert/ardent-forge/pull/42',
		branch: 'forge/rename-tclient',
		summary: 'Swapped the `tClient` identifier across the coordinator package.',
		claudeOutput:
			'Found 12 occurrences of `tClient` in the coordinator package. Replaced ' +
			'all of them with `temporalClient` to match the convention in the rest of ' +
			'the codebase. Verified tests still pass locally, then pushed the branch ' +
			'and opened a pull request.'
	};
}
