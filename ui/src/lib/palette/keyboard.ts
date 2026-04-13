import { palette } from './state/palette.state.svelte';

/** Bind ⌘K (and Ctrl+K on non-Mac) globally to toggle the palette. Esc is handled by
 *  Bits UI's Command primitive internally. Call this once from app-shell.svelte. */
export function mountPaletteKeybinding(): () => void {
	const onKeyDown = (e: KeyboardEvent) => {
		if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
			e.preventDefault();
			palette.toggle();
		} else if (e.key === 'Escape' && palette.open) {
			palette.hide();
		}
	};
	window.addEventListener('keydown', onKeyDown);
	return () => window.removeEventListener('keydown', onKeyDown);
}
