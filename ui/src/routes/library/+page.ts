import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';

export const ssr = false;

export const load: PageLoad = async () => {
	const [agents, connectors, memory, schedules] = await Promise.all([
		api.agents.list().catch(() => []),
		api.connectors.list().catch(() => []),
		api.memory.list().catch(() => []),
		api.schedules.list().catch(() => [])
	]);

	return {
		agentCount: agents.length,
		connectorCount: connectors.length,
		memoryCount: memory.length,
		scheduleCount: schedules.length
	};
};
