# WHY: garden-audit-render.py

> Rationale for decisions in `tomo/scripts/garden-audit-render.py`.
> The script is the deterministic renderer for the garden-audit skill (spec 030 Phase 3).
> It takes `garden-audit-doc.json` (from `garden-audit.py`) and emits two artifacts:
> a severity-ordered markdown review report and `garden-audit-wire.json`.

## Version 0.9.2 — dead_link remove wording = UNLINK (2026-07-22, user-confirmed)

WHY `_fix_summary` and the dead_link `**Replace with:**` field hint now say "Unlink every [[X]]
(removes the [[ ]] brackets, keeps the text)" / "leave empty to unlink (keeps the text, drops the
[[ ]])" instead of "Remove every [[X]] link": the parser now DE-LINKS on empty-replace (keeps the
word, drops the brackets) rather than deleting the whole link, so the report must describe the same
user-visible effect. The repoint wording ("fill Replace with: to repoint to a different note") is
unchanged. No wire/schema change — this is display copy only. (0.9.1: `_split_cache_entries` DRY
extraction, no behaviour change.)

## Version 0.9.0 — Tomo-Editor wire channel (spec 030 extension, 2026-07-22)

WHY the wire's `decision` now carries `file_under` (unparented/orphan filing target, parallel to
`repoint`/`replace`), `candidates: []` (display-only scored LLM picks the Tomo-Editor renders —
empty at first render, populated by `--suggest`), and `suggest_requested: false` (the editor's flag
marking findings that want candidates), plus a top-level `approved: false`: the Tomo-Editor works
from the JSON (Hashi's channel), so those decisions must live in the wire, not only the markdown.

WHY `build_wire_payload` computes `emit_digest` via `compute_garden_audit_digest` (not
`compute_payload_digest`): the change signal must reflect ONLY user apply-decisions
(`selected`/`repoint`/`replace`/`file_under`). Hashing the whole payload would flip the digest when
`--suggest` writes Tomo-generated `candidates`, falsely marking the wire "user-edited". The
garden-audit digest projects each finding to `id` + the four apply-decision keys and excludes
`candidates`, `suggest_requested`, `action`, `detail`, and the top-level `approved`. The suggestions
wire is byte-for-byte unaffected — it still uses `compute_payload_digest`.

WHY `enrich_wire_with_candidates` + `_suggest_requested_ids` live here (alongside
`enrich_report_with_suggestions`): candidate computation is SSoT'd via `_candidates_for_block`, so
the markdown pick lists and the wire `candidates` are always derived from the same scoring. Findings
are selected for enrichment from the UNION of markdown Suggest ticks and wire `suggest_requested`.
`{target,score}` from the suggest helpers is mapped to the wire's `{stem,score}` shape.

WHY `enrich_wire_with_candidates` also stamps `decision.suggested: true` and returns
`(wire, processed)` (0.10.0, 2026-07-23 Hashi handoff): without a ran-marker, a finding awaiting a
suggest run and one whose run returned empty were wire-identical
(`{suggest_requested: true, candidates: []}`) — the Tomo-Editor could not render its
"no suggestions found" state (Hashi spec-005 T5.4). The marker is stamped on every processed
finding regardless of candidate count and CLEARED (`pop`) on findings not requested in the latest
run — mirroring the candidates-clearing so un-ticking restores the default state on re-run.
`suggested` is excluded from `compute_garden_audit_digest` by construction (apply-decision
allowlist), so stamping never makes the wire read user-edited. The `processed` count feeds
`garden-audit-suggest.py`'s honest enriched-count contract (a zero-candidate run still changed
both artifacts and must be re-uploaded — see docs/tomo/scripts/garden-audit-suggest.md 0.4.0).

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

## Suggest opt-in box + --suggest enrichment (Phase 7, T7.2)

WHY every fixable `dead_link`/`broken_up` block renders a `- [ ] Suggest targets` box, but
NOT advisory findings and NOT unparented/orphan: unparented/orphan already carry candidate
MOCs from the scan (`candidate_mocs`), and advisory findings have no fix. Only the two typeable
checks (Replace / Repoint) benefit from on-demand candidates. Per D1 the box is SEPARATE from
Apply (ticking Apply must not trigger computation), and per D2 Pass-1 renders ONLY the static
box — zero per-finding candidate computation, because a real scan has hundreds of findings and
fuzzy-matching every one against the vault on every scan violates the perf constitution.

WHY `enrich_report_with_suggestions(report_md, wire, entries)` operates on the FULL report text
and rewrites blocks in place rather than re-rendering from the doc: the `--suggest` pass runs on
the ALREADY-published report (the doc.json is long gone), so it must preserve the user's edits
(Apply ticks, typed values) and the Approved gate byte-for-byte. It splits the report at
`### F<id>` boundaries, rewrites ONLY Suggest-ticked dead_link/broken_up blocks (structure joined
from the wire by F-id, stems from the cache), and rejoins. It is idempotent (strips a prior run's
pick list before inserting a fresh one) and emits no stray `Pick one:` header when there are no
candidates. STRUCTURE comes from the wire, never re-derived — consistent with the two-artifact split.

## cwd-relative STABLE defaults (spec 030, 2026-07-21)

WHY `main()` defaults `--input` (`tomo-tmp/garden-audit-doc.json`), `--output`
(`tomo-tmp/garden-audit-report.md`), `--json-output` (`tomo-tmp/garden-audit-wire.json`) to
STABLE cwd-relative names and ALWAYS writes the wire: the agent calls the renderer bare (Tomo
default-path standard). The RUN_ID that distinguishes runs belongs on the VAULT filename (set by
`kado-write-file --vault` at upload), NOT on the local render output — so the render output name
is stable and the agent stamps RUN_ID only in the transport step. The wire is the always-read
STRUCTURE source (two-artifact split), so it is written unconditionally, not gated behind an
optional `--json-output`.

## Integrity headers say "in:"; structure gets File-under + Suggest; no-suggestions note

WHY integrity finding headers (broken_up, dead_link) read `<label> in: [[note]]` while structure /
advisory read `<label>: [[note]]`: for an integrity check the broken link lives INSIDE the note, so
`Broken up:: link: [[021 Fleeting MOC]]` misreads as if the MOC IS the broken link. `... in: [[...]]`
makes the note the container. For structure/advisory the note IS the subject (an orphan note, a
duplicate stem), so a plain colon is correct. The join is decided by `f["tier"] == "integrity"`.

WHY unparented/orphan now render a `- [ ] Suggest targets` box AND an editable `- **File under:**`
field (Change 2): the scan supplies at most one candidate MOC and often "(no candidate)" — the user
needs a way to file the note under a MOC of their choosing. "File under:" is a distinct label from
"Repoint to:" because filing an orphan (add up:: + MOC bullet) is a different intent than repointing
a broken up::. The `_fix_summary` for a no-candidate orphan points the user at both affordances
instead of the old ugly "Add `up:: (no candidate)`".

WHY `enrich_report_with_suggestions` renders an explicit `_No suggestions found …_` note when zero
candidates clear the cutoff (Change 3), rather than leaving the Suggest-ticked block unchanged: an
untouched block looks broken — the user ticked Suggest and ran `--suggest` and apparently nothing
happened (the real F08 report). The note gives feedback for EVERY ticked finding (all check types).
`_strip_existing_pick_list` strips the note too, so re-running stays idempotent.

## Version 0.8.0

WHY: 0.8.0 (spec 030 live-report refinements) — integrity `in:` headers; structure (unparented/orphan)
Suggest box + `File under:` field + candidate suggestions (below-threshold, via
`target_suggest.suggest_file_under_mocs`); explicit "No suggestions found" note when nothing clears
the cutoff (Change 3). 0.7.0 cwd-relative STABLE defaults for `--input`/`--output`/`--json-output`;
the wire is always written (agent calls bare, stamps RUN_ID only on the vault target).

## Version 0.6.0

WHY: 0.6.0 (spec 030 Phase 7 T7.2) — added the `- [ ] Suggest targets` opt-in box for fixable
dead_link/broken_up and the `enrich_report_with_suggestions` `--suggest` second-pass path (pick
lists computed via `lib/target_suggest.py`, Suggest-ticked blocks only, byte-for-byte otherwise).

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
