# WHY: garden-audit-render.py

> Rationale for decisions in `tomo/scripts/garden-audit-render.py`.
> The script is the deterministic renderer for the garden-audit skill (spec 030 Phase 3).
> It takes `garden-audit-doc.json` (from `garden-audit.py`) and emits two artifacts:
> a severity-ordered markdown review report and `garden-audit-wire.json`.

## Both Artifacts from One Dict — No Drift by Construction (ADR-4)

WHY the report and the wire are both projected from the same in-memory `d` dict without
reading the same data twice: ADR-4 explicitly requires that the two artifacts are
"projected from the same dict — no drift". The renderer loops over `d["findings"]` once
for the report sections and once for `build_wire_payload`, both reading the same Python
object. Any code path that reads findings differently for the two outputs (e.g. reading
`garden-audit-doc.json` twice from disk) would be a drift risk — a re-read could pick
up a concurrent write, or a format discrepancy between the two loops could produce
structurally incompatible artifacts without a runtime error.

## emit_digest as the ADR-026 Change Signal

WHY `build_wire_payload` computes `emit_digest` over the payload with `emit_digest`
absent (the ADR-026 pattern from `suggestions-render.py`): the digest must cover the
editable content the user will modify — not itself. Including `emit_digest` in the
computation would make the digest depend on the digest, creating a circular dependency.
Excluding it (by computing before inserting) ensures `compute_payload_digest` produces
a stable fingerprint of the wire findings. `garden-audit-parser.load_changed_wire` then
re-computes the digest over the loaded wire (also with `emit_digest` absent) and
compares; a mismatch means the user edited the wire, triggering Pass-2 rebuild.

## Dead Link Wire Carries an Editable `replace` Slot (ADR-3 / ADR-026)

WHY the wire's `decision` block for `dead_link` findings includes a `replace: ""`
field that the markdown report does not render: the user must supply the replacement
wikilink (e.g. `[[New Note Name]]`) or confirm removal (empty string) in the machine-
editable wire. The markdown report is human-readable review; it cannot capture a
replacement target without becoming a structured data format. The `replace` slot on the
wire is the user's edit surface for dead-link fixes — `garden-audit-parser._dead_link_action`
reads `decision.get("replace", "")` to build the `edit_note_text` action. This is the
key design decision that lets the parser handle dead-link fix vs. dead-link remove as a
single action type (ADR-3).

## Fixable Findings Raise Hard on Missing Decision Block

WHY `_render_finding` raises `ValueError` when a fixable finding lacks a `decision`
block rather than emitting a silent skip or an advisory note: a fixable finding without
a decision block is a contract violation from the producer (`garden-audit.py`), not a
normal data case. Silently skipping it would produce an incomplete report without a
checkbox — the user would see the finding but have no way to confirm or skip it, and
the Pass-2 parser would silently produce no action for it. Failing loudly catches a
`garden-audit.py` regression at render time, where the error message is attributable.

## Frontmatter Stamps `tomo_skip_inbox_analysis: true` (ADR-1)

WHY the rendered frontmatter always sets `tomo_skip_inbox_analysis: true` regardless
of finding count: the garden-audit report must bypass Pass-1 LLM analysis — it is
pre-structured, not a raw inbox note to be classified. Routing it through inbox-analyst
would waste tokens, potentially corrupt the structured sections, and introduce a
non-deterministic LLM step into a deterministic pipeline. The skip flag is ADR-1's
mechanism: it is the same flag used by the FAN resolve doc and other structured inbox
artifacts that must be applied directly in Pass-2.

## Section Order is Strict and Omit-When-Empty

WHY empty tiers (integrity / structure / advisory) are omitted from the report rather
than shown as empty sections: a "## Integrity" section with no findings would read as
a broken render. The report must be scannable by the user at a glance; an empty section
adds cognitive noise without information. The `_render_tier_section` helper returns `[]`
when no findings exist for the tier, so the main `render_report` loop produces no output
for it. The Summary block shows per-tier counts, so the user sees the tally regardless
of whether the tier section appears.

## Report is Human-Facing Only — Structure Lives in the Wire (spec 030)

WHY the markdown report carries NO `<!-- garden-audit ... -->` comment (the earlier
round-trip payload was removed): the user approved a cleaner two-artifact split. The report
is purely human-facing — heading (with the F-id), the detail line, the Fix summary, the
`- [x] Apply` tick, and the `Repoint to:` / `Replace with:` fields. ALL machine STRUCTURE
(path, detail, candidate_mocs, decision defaults) lives in the wire (`build_wire_payload`),
which is always generated + cached and which `garden-audit-parser` ALWAYS reads. The two
artifacts are joined by the F-id in each `### F<id>` heading — the wire finding with the same
id supplies the structure, the markdown block supplies the decision. This removes the parity
hazard entirely: there is no invisible machine payload in the markdown to keep byte-identical
with the parser, so the renderer no longer needs `up_line()` / `bare_stem()` at all (the
parser reconstructs `match` from the wire's `up_target` / `dead_target`).

## Editable Replace with: / Repoint to: Fields

WHY dead_link blocks render a `**Replace with:** [[]]` field and EVERY broken_up block renders
a `**Repoint to:** [[]]` field: these are the user's decision surface for a fix that needs a
target the scan cannot supply (which MOC to repoint to, which note to substitute). The parser
reads the typed value back — a non-empty target repoints/substitutes, an empty/untouched `[[]]`
placeholder removes. The `←` hint text after the placeholder is stripped by the parser, so it
is safe to keep it inline as guidance. Filing findings (unparented/orphan) get no editable
field in v1 — only the Apply tick; their MOC comes from the wire's `candidate_mocs[0]`.

## Top-Level How-to-Apply Banner

WHY one instruction line renders directly under the H1: the report is a standalone review
surface; the user must know that unticking skips, that Replace/Repoint fields are fillable,
and that `/inbox` applies the kept fixes via Hashi — without reading the skill docs. Advisory
findings are called out as read-only so the user does not look for a missing checkbox.

## Top-level Approved gate (ADR-1 revised, 2026-07-21)

WHY the report renders a single top-level `- [ ] Approved` box under the how-to-apply
banner (mirroring `suggestions-render.py`): the user wanted a document-level review gate
before any fix lands. ADR-1 originally picked garden-audit up unconditionally (the wire
digest was the only signal); the live retest reversed that. Now `inbox-triage.py` routes
the doc to `approved_garden_audits[]` only when `_RE_APPROVED` matches, and
`state-promoter.check_tick` treats garden-audit like suggestions. The per-finding Apply
ticks + the wire still decide WHICH fixes apply; the top-level box decides WHETHER the doc
is picked up at all. The box wording/shape is copied from suggestions so the two docs read
identically to the user.

## Repoint offered for every broken_up (FIX 3, 2026-07-21)

WHY the editable `- **Repoint to:** [[]]` field renders for EVERY fixable `broken_up`
finding, not just ones pre-marked `action=add_relationship`: the user asked how to set the
`up::` correctly rather than only removing it ("nicht nur remove"). A broken `up::` has two
legitimate resolutions — repoint to a real MOC, or remove the dangling line — and only the
user knows the right MOC. Rendering the field for all broken_up (and the `_fix_summary`
describing both options) lets the parser's existing discriminator do its job: a non-empty
Repoint value ⇒ `add_relationship` (up_line from it), an empty `[[]]` ⇒ `edit_note_text`
removal. The parser already read the field for all broken_up blocks; only the renderer was
withholding it for removals.

## Defensive list-repr unwrap (FIX 2, 2026-07-21)

WHY `_wikilink` (and the shared `up_line`/`bare_stem` in `render_md.py`) unwrap a
stringified list-repr like `"['020 Active MOC']"` before formatting: the ROOT fix is in
`up_parse.py` (fresh caches are clean), but existing caches stay dirty until re-explored,
so a stale `up_target` would otherwise render as `[[['020 Active MOC']]]`. The renderers
yaml.safe_load a bracketed non-wikilink string to its list and take the first element,
guaranteeing a clean `[[020 Active MOC]]` even off a dirty cache. Guarded to strings that
start with `[` but not `[[`, so wikilinks and bare stems pass through untouched.

## Version 0.5.0

WHY: 0.5.0 (spec 030 two-artifact split 2026-07-21) — removed the per-finding
`<!-- garden-audit ... -->` structural comment entirely (`_structural_comment` deleted).
The report is now purely human-facing; ALL structure lives in the wire, joined to the
markdown by F-id. The renderer no longer imports `up_line` / `bare_stem` (only the parser
reconstructs `match`). 0.4.0 (spec 030 live-retest fixes) — top-level `- [ ] Approved` gate
(ADR-1 revised), `Repoint to:` field for every broken_up (FIX 3), and defensive list-repr
unwrap in `_wikilink` (FIX 2). 0.3.1 addressed the code-quality review — extracted the
duplicated `up_line()` / `bare_stem()` helpers to `lib/render_md.py` (shared with the
parser; parity now enforced by a single home). 0.3.0 was the spec-030 Feature 3 vertical
fix — added the per-finding structural HTML comment (parser round-trip), editable
`Replace with:` / `Repoint to:` fields, and the top-level how-to-apply banner. Earlier:
0.1.0 initial, 0.1.1 dead-link `replace` slot, 0.2.0 clickable wikilinks + fix summaries.
`update-tomo.sh` skips unchanged versions.
