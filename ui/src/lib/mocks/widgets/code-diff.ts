import { faker } from '@faker-js/faker';
import { CodeDiffPayload, type CodeDiffPayload as CodeDiffPayloadT } from '$lib/schemas/widgets/code-diff';

/**
 * Mock factory for code.diff payloads.
 *
 * Returns a wire-valid payload that parses cleanly through the Zod schema.
 * Partial overrides merged on top let stories tweak specific fields without
 * re-specifying the whole shape.
 */
export function makeCodeDiff(overrides: Partial<CodeDiffPayloadT> = {}): CodeDiffPayloadT {
	const payload: CodeDiffPayloadT = {
		tool: 'code.diff',
		context: 'cloudv2 / apps/controlplane-api/internal/coordinator',
		branch: 'rename/t-client',
		additions: 14,
		deletions: 14,
		files: [
			{
				path: 'coordinator.go',
				changes: 6,
				additions: 6,
				deletions: 6,
				hunk: {
					lines: [
						{ kind: 'remove', line: 42, content: 'func NewCoordinator(tClient temporal.Client, cfg Config) *Coordinator {' },
						{ kind: 'add', line: 42, content: 'func NewCoordinator(temporalClient temporal.Client, cfg Config) *Coordinator {' },
						{ kind: 'context', line: 43, content: '  return &Coordinator{' },
						{ kind: 'remove', line: 44, content: '    tClient: tClient,' },
						{ kind: 'add', line: 44, content: '    temporalClient: temporalClient,' },
						{ kind: 'context', line: 45, content: '    cfg:     cfg,' }
					]
				}
			},
			{ path: 'tick.go', changes: 4, additions: 4, deletions: 4 },
			{ path: 'watcher.go', changes: 3, additions: 3, deletions: 3 },
			{ path: 'coordinator_test.go', changes: 1, additions: 1, deletions: 1 }
		],
		footerMeta: 'tests green · lint clean',
		actions: [
			{ kind: 'view-diff', label: 'View full diff' },
			{ kind: 'commit', label: 'Commit' },
			{ kind: 'open-pr', label: 'Apply & open PR' }
		],
		...overrides
	};
	// Validate — throws if the factory drifts out of sync with the schema.
	return CodeDiffPayload.parse(payload);
}

/** Return a payload with a long file list and random paths, for volume stress tests. */
export function makeLargeCodeDiff(fileCount = 24): CodeDiffPayloadT {
	faker.seed(42);
	const files = Array.from({ length: fileCount }, () => {
		const additions = faker.number.int({ min: 1, max: 40 });
		const deletions = faker.number.int({ min: 1, max: 40 });
		return {
			path: faker.system.filePath(),
			additions,
			deletions,
			changes: additions + deletions
		};
	});
	const additions = files.reduce((n, f) => n + f.additions, 0);
	const deletions = files.reduce((n, f) => n + f.deletions, 0);
	return makeCodeDiff({
		context: 'galley / galley-frontend',
		branch: 'refactor/inbox-layout',
		additions,
		deletions,
		files,
		footerMeta: 'tests green · 1 lint warning'
	});
}
