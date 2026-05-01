---
from: tomo
to: hashi
date: 2026-04-30
topic: link-placement-mode-response
status: done
status_note:
priority: medium
requires_action: true
---

# Response — `link_to_moc` placement + new `add_relationship` action

Closing Ask 1 from `2026-04-30_hashi-to-tomo_link-placement-mode`.
Asks 2-4 (implementation, doc, tests) are in-flight on Tomo's side and
will land on a feature branch in a follow-up session.

The handoff's "Open question" — *"Is the placement distinction already
implicit in Tomo's emission?"* — answer is **no, but it's a deeper gap
than placement alone.** The discussion converged on a broader contract
change rather than the binary `placement` field as originally proposed.

A note on framing: most of the visible I24/I25 placement issues in the
2026-04-30 walk traced to Hashi-side `sectionLocator` behaviour, not
Tomo emission. The contract gaps below are real but were partially
masked by the locator bug. Both ends benefit from tightening the spec.

---

## Why broaden the contract instead of adding `placement` only

Three findings from the Tomo code-deep:

1. **`link_to_moc` today emits one shape only.** The renderer's
   `resolve_section_names` (instruction-render.py:942) always picks an
   editable callout — never a heading, never a line. Headings-as-target
   is dead code on both sides today.

2. **`up::`/`related::` are not `link_to_moc` actions.** They live in
   the profile (`tomo/profiles/miyo.yaml:106-113`) as relationship
   markers and are rendered by the atomic-note **template** via the
   `{{up}}` token (instruction-render.py:912). The `connect` callout is
   explicitly demoted in section_name resolution because navigation
   links don't belong in content-bullet position. So inline-field-in-
   callout placement is already its own code path; it just isn't
   exposed as an instruction-set action.

3. **Parent-MOC up-links go through `link_to_moc` as bullets.**
   `_build_link_to_moc_actions` Pass 1 (line 484-498) emits
   `line_to_add: "- [[Source]]"` for every parent_mocs entry. On a
   navigation-only target MOC (no `[!blocks]`-style content callout),
   `resolve_section_names` falls back to whatever editable callout
   exists — which on a `[!compass]`-only MOC means the bullet lands
   inside the nav callout body. This is the I24/I25 pattern.

The clean fix is two-part: (a) expand `link_to_moc`'s anchor model so
it stops being callout-only, and (b) split navigation links into a
separate action that uses inline-field syntax instead of bullet
syntax. Putting both into one `placement` field would conflate
"where to write" with "what shape to write."

---

## Final contract

### Action 1 — `link_to_moc` (broadened)

Content links into existing or new MOC structure (down-links,
supporting_items, content bullets).

```json
{
  "action": "link_to_moc",
  "target_moc": "Brettspiele (MOC)",
  "target_moc_path": "Atlas/200 Maps/Brettspiele (MOC).md",
  "anchor": {
    "type": "callout" | "heading" | "line",
    "value": "[!blocks] Key Concepts"
  },
  "placement": "inside" | "after",
  "line_to_add": "- [[Catan Strategien]]"
}
```

**Anchor types:**

| Type | `value` shape | Match behaviour |
|---|---|---|
| `callout` | callout type + title (e.g. `[!blocks] Key Concepts`) | match the callout opening line in the MOC body |
| `heading` | heading text without `#` (e.g. `Sources` for `## Sources`) | match heading text at any heading level |
| `line` | literal line content (substring match) | match any line whose stripped content equals or contains `value` |

**Placement:**

- `inside` — insert as the last line of the matched anchor's content
  range. Valid only when `anchor.type == "callout"` (heading/line
  anchors have no defined "inside"). Hashi adds `> ` prefix to
  `line_to_add` before writing.
- `after` — insert immediately after the matched anchor line (for
  callouts: after the callout closes; for headings: after the heading
  line; for lines: after the matched line). Verbatim, no `> ` prefix.

**Default behaviour change (vs today):** default placement flips from
"inside callout" to **`after`**. Tomo emits `placement` explicitly on
every `link_to_moc` action — no defaulting on Hashi's side.

**Field changes:**

- `section_name` (string|null) is **removed**. Replaced by structured
  `anchor` object.
- `line_to_add` is **pre-formatted by Tomo** — bullet style (`-` vs
  `*`), prefix conventions, etc. all live on Tomo's side. Hashi writes
  `line_to_add` verbatim (with `> ` prefix iff `inside` + callout).

**Schema:** `link_to_moc` shape changes; schema_version stays at 1 per
the migration call (Hashi notified out-of-band, Marcus regenerates the
test inbox before re-walking).

### Action 2 — `add_relationship` (new)

Navigation links written as Dataview inline fields (`up::`,
`related::`) on the target MOC.

```json
{
  "action": "add_relationship",
  "target_moc_path": "Atlas/200 Maps/Brettspiele (MOC).md",
  "marker": "up::"  | "related::",
  "line": "up:: [[Hobbies (MOC)]]"
}
```

**Hashi behaviour:**

1. Read target MOC via the Plugin API.
2. Locate the line whose stripped content **starts with `marker`**
   (after stripping any leading `> ` callout prefix and whitespace).
3. Replace that whole line with `line` (Hashi preserves the line's
   leading `> ` prefix if the marker was inside a callout).
4. **Hard fail** if no line starting with `marker` is found in the
   target MOC. Hashi emits a runtime error in its walk log; Tomo will
   regenerate with a `create_marker_line` step (or template fix) once
   the failure surfaces. Acceptable for v0.1 — every Tomo-rendered MOC
   includes the navigation callout with `up::`/`related::` placeholder
   lines via the standard template, so the marker line is always
   present in the common path.

**Why marker-only locator (no anchor object):** the marker IS the
anchor. `up:: [[X]]` lives wherever its marker line lives — there is
no "after the marker" or "before the marker" distinction; there's just
the marker line itself, which Hashi replaces wholesale. Multi-link
aggregation for `related::` (`related:: [[A]], [[B]], [[C]]`) is done
**Tomo-side** before emission — Tomo reads the target MOC's existing
`related::` value, computes the new combined value, and emits one
`add_relationship` action with the final `line`.

**Why `marker` AND `line` (apparent redundancy):** `marker` is purely
a locator (Hashi's grep prefix); `line` is the verbatim content to
write. They serve different purposes — Hashi never parses `line`,
Tomo never inspects `marker` after emission. This keeps Tomo in
control of formatting (spacing, comma-sep style, future markers) and
Hashi's writing rule trivially small.

---

## Hashi-side expectations

### `link_to_moc`

1. **Drop `section_name` parsing.** Replace with `anchor` object reader:
   `{type: "callout"|"heading"|"line", value: string}`.
2. **Implement three anchor matchers:**
   - `callout`: locate the line `> [!<type>][...] <title>` matching
     `anchor.value` byte-for-byte (after `> ` strip).
   - `heading`: locate any `# <value>` / `## <value>` / etc. line.
   - `line`: locate the first non-callout, non-heading line whose
     stripped content equals or contains `anchor.value`.
3. **Implement two placement modes:**
   - `inside` (callout only): insert as last line of callout body,
     adding `> ` prefix to `line_to_add`.
   - `after` (any anchor type): insert immediately after the matched
     anchor's terminal line (for callouts: after the closing `>` line;
     for headings: after the heading line; for lines: after the matched
     line itself). No `> ` prefix.
4. **Schema reject:** `placement: "inside"` with non-callout anchor
   type. Hashi can either runtime-error or treat as `after` — Tomo
   won't emit this combination, so behaviour on this is open to
   Hashi's preference.

### `add_relationship`

1. **New handler.** Locate marker line, replace with `line` verbatim
   (preserve leading `> ` callout prefix if marker was inside a
   callout).
2. **Hard fail on missing marker.** Surface in run log with
   target_moc_path + marker. No fallback placement.

### Old `link_to_moc` behaviour deprecated

The current `section_name` (string) field will not appear on any
new emission. Old instruction sets in flight are disposable —
Marcus regenerates the test inbox after this contract lands. No
back-compat reader needed on Hashi's side.

---

## Tomo-side implementation plan (in-flight)

Will land on a Tomo feature branch in a follow-up session. Scope:

1. **Schema** (`tomo/schemas/instructions.schema.json`):
   - `link_to_moc`: drop `section_name`; add required `anchor` object,
     required `placement` enum.
   - Add `add_relationship` definition.
2. **Renderer** (`tomo/scripts/instruction-render.py`):
   - `_build_link_to_moc_actions`: stop emitting parent_mocs up-links;
     emit `add_relationship` actions instead (Pass 1 → new builder).
   - `_build_link_to_moc_actions` Pass 2 (supporting_items down-links):
     emit `anchor: {type: "callout", value: ...}` + `placement: "inside"`.
   - `resolve_section_names` → `resolve_anchors`: extend to populate
     `anchor.value` for the chosen target. Default `placement: "after"`
     for now, callout-content links keep `inside`.
   - New `_build_add_relationship_actions` builder: emits one action
     per (parent_moc, child_moc) pair, with marker `up::` and pre-
     aggregated `line` value.
3. **Doc** (`docs/instructions-json.md`):
   - Full rewrite of § `link_to_moc` covering anchor types, placement,
     Tomo-side responsibilities, Hashi-side responsibilities.
   - New § `add_relationship` mirroring the structure.
4. **Tests** (`tests/`):
   - Anchor-type matrix (callout/heading/line × inside/after) for
     `link_to_moc`.
   - `add_relationship` emission for parent_mocs up-links + multi-link
     aggregation for `related::`.
   - Regression: every action emitted by today's renderer translates
     to a valid new-shape action (no silent drops).

Implementation will land as one feature branch (`feat/link-anchor-and-
relationship-actions` or similar). Marcus regens the test inbox post-
merge for Hashi's next walk.

---

## References

- Original handoff: `Tomo/_inbox/from-hashi/2026-04-30_hashi-to-tomo_link-placement-mode.md`
- Current renderer: `Tomo/tomo/scripts/instruction-render.py`
  - `_build_link_to_moc_actions`: lines 451-516
  - `resolve_section_names`: lines 942-1067
- Current schema: `Tomo/tomo/schemas/instructions.schema.json` § `link_to_moc` lines 77-91
- Profile relationship markers: `Tomo/tomo/profiles/miyo.yaml:106-113`
- Doc to rewrite: `Tomo/docs/instructions-json.md` § `link_to_moc` (full) + new § `add_relationship`
