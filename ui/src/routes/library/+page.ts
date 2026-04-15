import type { PageLoad } from './$types';
import { api } from '$lib/api/typed';

export const ssr = false;

export const load: PageLoad = async () => {
	const counts = await api.notebook.counts().catch(() => null);
	const agents = await api.agents.list().catch(() => []);
	const connectors = await api.connectors.list().catch(() => []);
	const memory = await api.memory.list().catch(() => []);

	return {
		counts,
		agentCount: agents.length,
		connectorCount: connectors.length,
		memoryCount: memory.length
	};
};
