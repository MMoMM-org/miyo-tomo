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

## Version 0.1.1

WHY: Initial spec-030 Phase 3 implementation (0.1.0) plus a `replace` slot fix on the
dead-link wire decision block added during T4.1 follow-up (0.1.1). `update-tomo.sh`
skips unchanged versions.
