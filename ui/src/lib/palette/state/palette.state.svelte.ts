/**
 * Command palette state.
 *
 * Controls open/close of the ⌘K overlay. The Bits UI `Command` primitive handles
 * its own internal query + filter state — we only drive the shell.
 */

const state = $state({ open: false });

export const palette = {
	get open() {
		return state.open;
	},
	toggle() {
		state.open = !state.open;
	},
	show() {
		state.open = true;
	},
	hide() {
		state.open = false;
	}
};
