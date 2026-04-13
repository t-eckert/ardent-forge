import { WorkoutsPayload, type WorkoutsPayload as WorkoutsPayloadT } from '$lib/schemas/widgets/workouts';

export function makeWorkouts(overrides: Partial<WorkoutsPayloadT> = {}): WorkoutsPayloadT {
	return WorkoutsPayload.parse({
		tool: 'health.workouts',
		blockLabel: 'half-marathon build · wk 08/14',
		goal: 'Sub-1:45 half',
		daysToEvent: 42,
		eventLabel: '24 May',
		weekVolumeLabel: '46 km',
		weekVolumeDelta: '+8%',
		longRunLabel: '18.5 km',
		thresholdPaceLabel: '5:08 /km',
		thresholdPaceDelta: '−10s',
		recent: [
			{ dateLabel: 'Apr 10', title: 'Tempo 6×1km', volumeLabel: '10.2 km · 48:21', intensityLabel: '172 bpm · Z4', source: 'strava' },
			{ dateLabel: 'Apr 10', title: 'Upper · Pull · A', volumeLabel: '18 sets · 52 min', intensityLabel: 'RPE 7', source: 'notebook' },
			{ dateLabel: 'Apr 09', title: 'Easy 8 km · Canal loop', volumeLabel: '8.1 km · 45:30', intensityLabel: '148 bpm · Z2', source: 'strava' }
		],
		sourcesLine: 'sources: strava (live) · notebook (synced)',
		...overrides
	});
}
