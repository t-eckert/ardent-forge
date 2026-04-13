/**
 * Design tokens for Ardent Forge.
 *
 * Source of truth for the palette, type scale, radii, and spacing conventions.
 * Mirror these in `app.css` @theme block so Tailwind utilities (bg-paper, text-ink, font-display)
 * resolve to the same values.
 *
 * Palette derives from the Paper mood board artboard (1-0).
 */

export const palette = {
	/** page background */
	paper: '#FAF7F1',
	/** raised surface (sidebar, card fills) */
	bench: '#F1ECE0',
	/** muted text, meta labels */
	graphite: '#8A7F72',
	/** primary text, dense surfaces */
	ink: '#1A1714',
	/** accent — active state, CTAs, widget hero */
	ember: '#E34E18',
	/** accent dark variant — gradient ends, links */
	emberDeep: '#C73D0F',
	/** secondary accent — info, notebook widget */
	signal: '#2D4A6A',
	/** success, live */
	moss: '#4A8A5A',
	/** warning, blocked */
	warn: '#A8754A',
	/** subtle border */
	border: '#E6DFD1',
	/** secondary muted text */
	slate: '#5A5048',
	/** disabled bg / line fill */
	stone: '#D6CEBE'
} as const;

export const fonts = {
	display: '"Playfair Display", ui-serif, Georgia, serif',
	body: '"Inter", ui-sans-serif, system-ui, sans-serif',
	mono: '"JetBrains Mono", ui-monospace, Menlo, monospace'
} as const;

export const radii = {
	xs: '2px',
	sm: '3px',
	md: '4px',
	lg: '6px',
	xl: '8px'
} as const;

export type PaletteKey = keyof typeof palette;
export type FontKey = keyof typeof fonts;
