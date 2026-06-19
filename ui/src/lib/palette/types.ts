/**
 * Result classes shown in the palette. Each class has an icon + tone pairing per the
 * chrome spec (artboard 2KX-0, section 03).
 */
export type ResultClass = 'note' | 'task' | 'action';

export interface PaletteResult {
	id: string;
	/** What the user sees */
	label: string;
	/** Contextual path shown below label */
	breadcrumb: string;
	/** Where to navigate on enter (ignored for actions) */
	href?: string;
	class: ResultClass;
	/** For actions: supplementary text shown inline */
	hint?: string;
	/** For ranking — recency boost, defaults to 0 */
	recentBoost?: number;
	/** For ranking — pinned items get +10 */
	pinned?: boolean;
	/** Keywords for fuzzy matching beyond label */
	keywords?: string[];
}
