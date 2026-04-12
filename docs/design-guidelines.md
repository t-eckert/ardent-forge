# Ardent Forge — Design Guidelines

**An elegant power tool for a well-lit bench.**

The feel is editorial workshop meets Linear-density meets Marathon-plastic confidence. Bright surfaces, confident type, restrained colour, dense information. We are designing an instrument for operators — not a consumer app.

---

## Principles

1. **Editorial restraint.** Whitespace is structural. Type does the heavy lifting. Decoration earns its place or goes.
2. **Dense by default.** Built for people who live in this tool daily. Small type, tight rhythm, keyboard-first. Reward repeated use.
3. **Plastic confidence.** Crisp edges, saturated accents used sparingly, atmospheric surfaces for hero moments. Never moody — always well-lit.

When in doubt: remove an element. Restraint wins.

---

## Colour

Light-first. Dark mode is a translation, not a parallel identity.

### Palette

| Token      | Hex        | Role                                                            |
|------------|------------|-----------------------------------------------------------------|
| Paper      | `#FAF7F1`  | Default surface. The page.                                      |
| Bench      | `#F1ECE0`  | Recessed / nested surface. Row stripes, input wells, sidebar.   |
| Graphite   | `#8A7F72`  | Muted foreground. Metadata, labels, placeholder text.           |
| Ink        | `#1A1714`  | Primary text. Dark surfaces (code, hero cards).                 |
| Ember      | `#E24E1B`  | The one hot accent. Primary action, running state, emphasis.    |
| Signal     | `#2B4A6B`  | Cool informational. Review states, links, reference data.       |
| Workshop   | `#4A7340`  | Success. Additions. Verification passed.                        |
| Destructive| `#B8301A`  | Failure. Removals. Danger.                                      |

### Secondary tones

- `#4A4139` — body text on Paper when muted (captions, descriptions).
- `#D8CFBF` — default border (hairline on Paper).
- `#E4DDD0` — softer interior border (table row rules, soft dividers).
- `#F5B089` — Ember tint used for text on dark surfaces ("TASK-0142 · CODE").

### When to use which accent

- **Ember** — the single moment of emphasis on a screen. Primary action, `running` status, active nav item indicator, the hot atmospheric surface (Heat gradient). One Ember per view, usually.
- **Signal** — informational secondary: `review` states, links, reference labels, Linear IDs.
- **Workshop** — success states only. Verification pass, additions, positive deltas.
- **Destructive** — failures and removals. Nothing else. Never as decoration.

---

## Typography

Three faces, each with a single job:

| Family             | Role                | Usage                                                        |
|--------------------|---------------------|--------------------------------------------------------------|
| Playfair Display   | Display / editorial | H1, hero, page titles, section headings, personal moments.   |
| Inter              | Body / UI           | All running text, UI labels, buttons, descriptions.          |
| JetBrains Mono     | Meta / code         | Timestamps, IDs, diffs, metrics, labels, code, key commands. |

### Scale (Inter unless noted)

- **H1 / display** — Playfair 36–44px · `font-weight: 500` · `letter-spacing: -0.01em`
- **H2 / section** — Playfair 20–22px · 500
- **H3 / subsection** — Inter 15px · 600
- **Body** — Inter 14px · `line-height: 1.55`
- **Body muted** — Inter 13px · `color: #4A4139`
- **UI label** — Inter 13px · 500
- **Caption / meta** — JetBrains Mono 10–11px · `letter-spacing: 0.08–0.12em` · `text-transform: uppercase` · `color: #8A7F72`

### Numbers are always monospace

All numerals — timestamps, counts, diffs, metrics, IDs, version numbers, file sizes, currencies — render in **JetBrains Mono**. Never mix a number with Inter.

If a number sits inside a prose sentence, still set it in mono (inline span).

```html
<p>Shipped <span class="mono">7</span> tasks in the last <span class="mono">24h</span>.</p>
```

### Italic

Playfair italic is reserved for editorial moments — tagline, standfirst, hero subhead. Do not italicize body text.

---

## Spacing & sizing

Tight by default. Components feel like precision instruments, not friendly widgets.

- **Control height** — 30px default, 24px small, 36px large. 48px is only for full-page CTAs.
- **Button padding** — `0 12px` default, `0 8–10px` small, `0 16px` large.
- **Input height** — 32px default, same padding rules as buttons.
- **Card padding** — 16px default, 20px for feature cards, 12–14px for dense internal cards.
- **Section gap** — 20–28px between sibling sections. Less for related items.
- **Gutter** — 24px main content, 40px only for hero surfaces.

### Radius

- **3px** — status pills, small chips, internal dividers
- **4px** — buttons, inputs, kbd keys, nav items
- **8px** — cards, panels, code blocks, widgets
- No radius larger than 10px. Never fully rounded except avatars.

### Borders

Hairline `1px solid #D8CFBF` is the default. Focus state uses `1.5px solid #1A1714` with an Ember caret. Error states: `1.5px solid #B8301A`.

---

## Surfaces & atmosphere

Most of the app is Paper. Atmosphere (gradients, noise, blur, glass) earns its place for **hero moments** only — never behind dense data.

| Surface | Treatment                                                                        | Use                                              |
|---------|----------------------------------------------------------------------------------|--------------------------------------------------|
| Paper   | `#FAF7F1` flat                                                                   | Default                                          |
| Bench   | `#F1ECE0` flat                                                                   | Nested, recessed, sidebar                        |
| Ink     | `#1A1714` flat                                                                   | Code blocks, dark pills                          |
| Heat    | `linear-gradient(135deg, #FFB199, #E24E1B, #8A1E00)` + radial Ember blur overlay | Active task card, weather widget, splash         |
| Plasma  | `radial-gradient(circle, #7FA5C9, #2B4A6B, #0F1F33)`                             | Informational hero, review-state widgets         |
| Smoke   | `linear-gradient(200deg, #3A3329, #1A1714, #000)`                                | Dark-mode surfaces                               |
| Glass   | `rgba(250,247,241,0.55)` + `backdrop-filter: blur(16px)` + hairline white border | Command palette, modals, floating panels on hero |
| Aura    | Blurred ember × signal blobs on Paper                                            | Empty states, splash, login                      |

### Noise

All large atmospheric surfaces get a subtle grain overlay (opacity 0.08–0.18) to prevent banding and add tactility. Use an SVG `feTurbulence` filter.

### Glow / depth

No drop shadows in the flat UI layer. Depth comes from surface colour (Paper → Bench → Ink) and borders, not shadows.

---

## Components

### Buttons

| Variant     | Surface                  | Border                 | Text         |
|-------------|--------------------------|------------------------|--------------|
| Primary     | `#E24E1B`                | none                   | `#FAF7F1`    |
| Ink         | `#1A1714`                | none                   | `#FAF7F1`    |
| Secondary   | transparent              | `1px solid #1A1714`    | `#1A1714`    |
| Tertiary    | transparent              | `1px solid #D8CFBF`    | `#1A1714`    |
| Ghost       | transparent              | none                   | `#4A4139`    |
| Destructive | `#FAF7F1`                | `1px solid #B8301A`    | `#B8301A`    |

Primary (Ember) is for the single most important action on the screen. If there's nothing at that level of importance, use Ink. Avoid two Embers in the same view.

### Inputs

Bench wells (`#FAF7F1` on Paper, or `#FAF7F1` on Bench page) with `#D8CFBF` hairline. Focus bumps border to `1.5px solid #1A1714` and shows an Ember caret. Labels are mono captions above the input.

### Status pills

22px height, 3px radius, mono 11px label. Dot on the left. The semantic contract:

- `QUEUED` — Bench fill, graphite dot
- `RUNNING` — Ember tint `rgba(226,78,27,0.1)` + `1px solid #E24E1B` + Ember dot + destructive-red text
- `REVIEW` — Signal tint + Signal border + Signal dot + Signal text
- `SUCCEEDED` — Ink fill + Workshop dot + Paper text
- `FAILED` — Destructive fill + Paper text + Paper dot
- `BLOCKED` — Bench fill + dashed graphite border + graphite dot

### Cards

`#FAF7F1` with `1px solid #D8CFBF`, `8px` radius, `16px` padding. Nested cards use Bench (`#F1ECE0`) instead.

### Tables

36px dense rows. Header row is Bench (`#F1ECE0`) with mono uppercase caption labels. Row separator `1px solid #E4DDD0`. Alternate row stripe (Bench) reserved for highlighting a specific row state (e.g. awaiting review).

### Keyboard hints

Inline `<kbd>` with Bench fill, `1px solid #D8CFBF` sides + `2px solid #D8CFBF` bottom (gives a key feel), 4px radius, mono 11px. Small variant for sidebar hints: 16px tall, 9–10px type.

### Code block

Ink (`#1A1714`) surface, 8px radius, 16–20px padding, JetBrains Mono 12–13px, `line-height: 1.65`. Syntax colour reference:

- Keywords — `#77A7CF`
- Identifiers / self — `#F5B089`
- Literals (numbers, "magic" values) — `#E24E1B`
- Comments / muted — `#8A7F72`
- Body — `#FAF7F1`

### Diff

Added lines: background `rgba(74,115,64,0.22)`, gutter `+` in Workshop green.
Removed lines: background `rgba(184,48,26,0.18)`, gutter `−` in Destructive.
Inline diff counts: `+N` Workshop, `−N` Destructive, with a muted slash separator.

---

## Iconography

**Phosphor Icons** throughout. Default to the `regular` weight. 14px in nav and compact controls, 16px in default controls, 20px in widgets.

Line style only. Never fill icons except in illustrative hero moments.

---

## Data display rules

1. **Numbers are always mono.** Without exception. (See Typography.)
2. **Additions are green (`#4A7340`), removals are red (`#B8301A`).** Code diffs, file deltas, metric changes.
3. **Timestamps in local time in mono.** `HH:MM:SS` for logs, `HH:MM` for UI labels, `12 April 2026` for verbose dates.
4. **IDs, branches, commands, file paths — all mono.** Even when embedded in prose sentences.
5. **Relative time for human-facing UI.** Absolute time in tooltips and audit logs.

---

## Writing

- Sentence case for headings. Title Case is reserved for proper nouns.
- First-person address where appropriate. "Good afternoon, Thomas." not "Dashboard." in personal moments.
- Status sentences are declarative: "Three tasks running. Two awaiting review. The forge is warm."
- Labels are terse. "Request changes," not "Would you like to request changes?"
- The agent has a voice: measured, confident, never apologetic.

---

## What we don't do

- No drop shadows in flat UI.
- No colour purely for decoration. Every hue carries semantic weight.
- No emoji.
- No rounded pill buttons (pills are status indicators, not actions).
- No gradients behind data-dense content.
- No light-grey hairlines on pure white — our hairlines are warm (`#D8CFBF`).
- No mixing of Inter and a number.
- No system fonts. Playfair / Inter / JetBrains Mono always load.

---

## Notebook rendering

The Notebook surface reads a local Obsidian vault (PARA + Zettelkasten) and renders its markdown as first-class UI — never as a raw editor view.

### Wiki-links

Markdown `[[Name]]` and `[[Path/Name|Display]]` render as inline chips:

- Height 20–22px, radius 3px, padding `0 6–10px`
- Surface: Bench (`#F1ECE0`), hairline `1px solid #D8CFBF`
- Text: Signal (`#2B4A6B`), Inter 12px (11px in compact contexts)
- Never underlined. The chip *is* the link affordance.

In prose paragraphs, chips sit inline with the text baseline. In metadata strips ("Linked from"), they flow as a wrap-group.

### Task checkbox states

Markdown task notation maps 1:1 to a visual state. 16px square, 3px radius:

| Notation | State     | Visual                                                               |
|----------|-----------|----------------------------------------------------------------------|
| `[ ]`    | Open      | Paper fill, `1.5px solid #8A7F72`                                    |
| `[x]`    | Done      | Ink fill, Paper checkmark, text struck through in Graphite           |
| `[>]`    | Deferred  | Paper fill, `1.5px solid #2B4A6B`, Signal arrow glyph, muted text    |
| `[<]`    | Paused    | Paper fill, `1.5px solid #E24E1B`, Ember pause bars glyph            |
| `[~]`    | Partial   | Paper fill, `1.5px solid #E24E1B`, Ember dash glyph, live text       |
| `[!]`    | Dropped   | Paper fill, `1.5px solid #B8301A`, Destructive × glyph, struck text  |

Inline time markers (`@ 9`, `@ 14:30`) render in JetBrains Mono 12px Graphite.

### Daily log

Header: mono caption (`SATURDAY · DAY 102 OF 2026`), Playfair date display (numerals in mono inside the Playfair line), stat pills for open/done/deferred counts.

Body sections: Playfair 22px section headings with a right-extending hairline `#E4DDD0` rule. Section heading may carry a mono range indicator (e.g. `08:00 — 16:00` for Work).

Footer: `LINKED FROM · N` caption followed by a wrap of wiki-link chips.

### Frontmatter

YAML frontmatter is never shown raw. It becomes:

- **Stat counters** in the page header (mono numerals, Workshop for positive categories, Signal for neutral, Ember for active/urgent)
- **Tag chips** next to the title (mono 10px, Bench fill, 3px radius, e.g. `fiction` `gothic`)
- **Status pills** next to the title using the standard status vocabulary
- **Metadata rail** on the right of long-form pages (author, source, dates)

### Collections

Generic pattern for any Collection (Books, Films, Places, Repositories, Job openings, Links):

1. **Header** — `COLLECTION · N ENTRIES` caption, Playfair title, short description, stat counters aligned right.
2. **Filter row** — All + status subsets as tertiary buttons, sort control at right.
3. **Feature section** — rich cards for "active" items (currently reading, currently watching, etc.). Editorial typography inside the card — Playfair title, italic author/creator, progress bar, tags.
4. **Archive table** — dense 36px rows for finished/past entries with editorial type (Playfair title cell, Playfair italic secondary cell) and mono metadata.

### Markdown primitives

- **Headings** — H1 rendered in Playfair 36–44px · H2 in Playfair 20–22px · H3 in Inter 15–16px 600
- **Paragraphs** — Inter 14px, `line-height: 1.65` inside long-form reading columns (720px max width)
- **Emphasis** — `*italic*` renders in Playfair italic at the same optical size, for editorial voice within prose
- **Strong** — `**bold**` stays in Inter 600
- **Blockquote** — left rule in Ember (`3px solid #E24E1B`), 16px left padding, Inter italic at 15px
- **Inline code** — JetBrains Mono 13px, Bench pill background (`#F1ECE0`), 2px horizontal padding, 2px radius, no border
- **Code block** — see Components · Code block
- **Callouts** (`> [!note]`, `> [!warning]`) — see Status pills for color vocabulary; render as a rounded card with matching tinted surface and a mono uppercase kind label at the top

### Reading width

Long-form prose content (daily log, wiki, field pages) renders in a **720px centered column** with 40px top/bottom padding. This is a strict ceiling — even on wide viewports, we do not widen the reading column past 720px. Denser structured pages (collections, people) use the full main-content width.

---

## Source of truth

Visual mocks live in the Paper design file (`Ardent Forge`). This document is the written counterpart — if the two disagree, update both and decide which to follow deliberately.
