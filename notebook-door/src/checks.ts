// What the door checks on every write, mechanically, before anything touches the Notebook. The Notebook's own
// CLAUDE.md is the full set of conventions; these are the ones a program can check.
import { posix } from "node:path";
import type { Grant } from "./grants.ts";

/** Emoji and pictographs. The Notebook's notes have none. */
const EMOJI = /[\p{Extended_Pictographic}\u{1F1E6}-\u{1F1FF}]/u;

/** Markdown and HTML that load a URL the moment a note is viewed. Callers check this themselves; the door again. */
const MARKDOWN_IMAGE = /!\[[^\]]*\]\(\s*<?([^)\s>]+)/g;
const REFERENCE_IMAGE = /!\[[^\]]*\]\[[^\]]*\]/;
const HTML_TAG = /<\/?[a-zA-Z][\w-]*(\s[^>]*)?\/?>/;
const LINK_TARGET = /\]\(\s*<?([^)\s>]+)|^\s*\[[^\]]+\]:\s*<?(\S+?)>?\s*$/gm;
const UNSAFE_SCHEME = /^(javascript|data|vbscript|file):/i;

/** Text outside fenced and inline code, where markup is only text. */
function outsideCode(text: string): string {
	return text.replace(/^(```|~~~)[\s\S]*?^\1/gm, "").replace(/`[^`\n]*`/g, "");
}

function decoded(target: string): string {
	return target
		.replace(/&#x([0-9a-f]+);?/gi, (_, hex: string) => String.fromCodePoint(Number.parseInt(hex, 16)))
		.replace(/&#(\d+);?/g, (_, dec: string) => String.fromCodePoint(Number(dec)))
		.replace(/&colon;/gi, ":")
		.replace(/[\u0000- \u007f]/g, "")
		.toLowerCase();
}

/** Why outgoing markdown is refused, or nothing when it is fine. */
export function markdownRefusals(text: string): string[] {
	const refusals: string[] = [];
	const body = outsideCode(text);
	for (const match of body.matchAll(MARKDOWN_IMAGE)) {
		refusals.push(`an image embed loads ${hostOf(match[1] ?? "")} when the note is opened`);
	}
	if (REFERENCE_IMAGE.test(body)) {
		refusals.push("a reference-style image embed");
	}
	if (HTML_TAG.test(body)) {
		refusals.push("raw HTML");
	}
	for (const match of body.matchAll(LINK_TARGET)) {
		const target = decoded(match[1] ?? match[2] ?? "");
		if (UNSAFE_SCHEME.test(target)) {
			refusals.push(`a ${target.split(":")[0]}: link`);
		}
	}
	return refusals;
}

function hostOf(target: string): string {
	try {
		return new URL(target).host || "a local file";
	} catch {
		return "a relative URL";
	}
}

/** The frontmatter's keys and values, flat. */
export function frontmatter(text: string): Record<string, string> | undefined {
	const block = /^---\r?\n([\s\S]*?)\r?\n---(\r?\n|$)/.exec(text);
	if (block === null) {
		return undefined;
	}
	const fields: Record<string, string> = {};
	for (const line of (block[1] ?? "").split(/\r?\n/)) {
		const field = /^([A-Za-z_][\w-]*):\s*(.*)$/.exec(line);
		if (field !== null) {
			fields[field[1] as string] = (field[2] ?? "").trim();
		}
	}
	return fields;
}

/**
 * Everything wrong with a write, or nothing. `siblings` are the Markdown files already in the note's folder, used to
 * tell whether the folder names its notes `YYYY-MM-DD Title.md`.
 */
export function writeRefusals(options: {
	readonly grant: Grant;
	readonly path: string;
	readonly text: string;
	readonly creating: boolean;
	readonly siblings: readonly string[];
}): string[] {
	const refusals: string[] = [];
	// New notes follow the Notebook's frontmatter conventions. An update keeps a note's own shape: some older notes,
	// such as the slug-named journal profiles, have other keys or none, and the door does not rewrite them.
	const fields = frontmatter(options.text);
	if (options.creating) {
		if (fields === undefined) {
			refusals.push("the note has no frontmatter");
		} else {
			for (const key of ["type", "field", "created"]) {
				if (!fields[key]) {
					refusals.push(`the frontmatter has no ${key}`);
				}
			}
			if (fields.author !== options.grant.frontmatterAuthor) {
				refusals.push(`a note ${options.grant.caller} creates must say author: ${options.grant.frontmatterAuthor}`);
			}
		}
	}
	if (EMOJI.test(options.text) || EMOJI.test(options.path)) {
		refusals.push("emoji");
	}
	const name = posix.basename(options.path);
	const dated = options.siblings.filter((s) => /^\d{4}-\d{2}-\d{2} /.test(s)).length;
	if (options.creating && options.siblings.length >= 3 && dated * 2 > options.siblings.length && !/^\d{4}-\d{2}-\d{2} \S/.test(name)) {
		refusals.push("notes in this folder are named YYYY-MM-DD Title.md");
	}
	if ((options.grant.requireReference ?? []).some((folder) => options.path.startsWith(folder)) && !/^## Reference\s*$/m.test(options.text)) {
		refusals.push("a research note needs a ## Reference section listing its sources");
	}
	refusals.push(...markdownRefusals(options.text));
	return refusals;
}
