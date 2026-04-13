/**
 * Centralised icon exports.
 *
 * Ardent Forge uses Phosphor Icons via `phosphor-svelte`. Re-exporting here lets us
 * swap weights/variants globally and serves as the discoverable list of icons in the
 * design system. Import from `$lib/icons` rather than from `phosphor-svelte` directly.
 *
 * Sidebar spine mapping is locked (see memory/project_phosphor_icons.md):
 *   Today → Sun · Threads → ChatCircle · Library → Books · Agents → Robot
 */

export {
	// Spine
	Sun,
	ChatCircle,
	Books,
	Robot,

	// Chrome + palette
	MagnifyingGlass,
	CaretRight,
	CaretDown,
	CaretUp,
	X,
	Plus,
	PushPin,
	Star,
	Gear,
	ArrowRight,
	CheckCircle,
	XCircle,
	WarningCircle,

	// Widget tool glyphs
	Code,
	Heartbeat,
	MapPin,
	CloudSun,
	Receipt,
	CalendarBlank,
	ListChecks,

	// Agent/run markers
	Lightning,
	Clock,
	ArrowsClockwise,
	GitBranch,

	// Misc semantic
	Check,
	Circle,
	Dot,
	Sparkle
} from 'phosphor-svelte';
