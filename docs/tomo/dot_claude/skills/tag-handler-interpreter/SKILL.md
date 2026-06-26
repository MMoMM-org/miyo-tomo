# WHY: tag-handler-interpreter (skill)

> Rationale for decisions in `tomo/dot_claude/skills/tag-handler-interpreter/SKILL.md`.
> Spec: docs/XDD/specs/024-tag-handler-framework/ SDD §5, §10.

## Why a Separate Interpreter Skill

WHY: The interpreter is a conditional extension to the suggest flow, not a replacement for it. Loading it only when `routing-plan.handled[]` is non-empty keeps the cold path (empty or absent `handled`) byte-identical to today (AC-5 from spec 024 requirements). A separate skill is the correct Tomo mechanism for a conditional sub-flow — it can be loaded by the conductor at the right decision point without polluting the `suggest-handling` skill with tag-handler logic. The conductor's `skills:` list declares it at startup so it is ready when needed.

## Why Lean In-Skill Compose (SDD §10 decision)

WHY: SDD §10 explicitly decided against dispatching a separate analyst subagent for compose. The interpreter skill does the synthesis itself (one LLM call per group for the directive path). The rationale: the groups are small, the compose prompt is well-defined (the handler's own directive string), and the overhead of spawning a full inbox-analyst subagent per group is unjustified. A dedicated lean compose call in the main skill context keeps the token budget bounded and avoids the subagent-spawning overhead for what is a single focused synthesis task.

## Why One Merged Block per Group (FR-8 / AC-3)

WHY: FR-8 from spec 024 requirements requires that a group of N captures for the same (handler, target_path) produces exactly ONE merged status-update block — not N separate blocks. AC-3 states the acceptance criterion explicitly: three captures for one repo → one merged suggestion. The `# STRICT` block in step 3 of the runtime skill enforces this cardinality. The failure mode it guards against is the natural LLM tendency to produce one block per source item (the "natural" loop output shape), which would flood the target note with N insertions instead of one.

## Group-Result Contract and Exchange Directory

WHY: The interpreter writes one `tomo-tmp/tag-handler-groups/<i>.json` per group, conforming to `tomo/schemas/tag-handler-group.schema.json`. This is the skill→reducer interface. The exchange directory (`tomo-tmp/tag-handler-groups/`) is a scratch location under `tomo-tmp/` (all interpreter scratch lives there per the conductor's Constraints). The schema carries `compose_mode` (`llm_directive` vs `field_template`) so the reducer can reflect the compose path in the suggestion item without re-inspecting the original handler config. Null `target_path` groups are written and surfaced — the reducer guards against missing targets (FR-11) rather than silently dropping them here.

## LLM Directive vs Field Template: Two Compose Modes

WHY: A handler's `compose` field is either a free-text LLM directive (string) or a
mechanical field list (array of strings). The interpreter branches on `compose_mode`
from the group-result JSON, which mirrors the handler schema's `oneOf` shape:

- **LLM directive** — the interpreter assembles all captures in the group (title,
  category, Summary, body snippet) into a single prompt prefixed with the handler's
  directive string and makes one inference call. The output is a free-form markdown
  block that synthesises the batch into a logical status update. This is the path used
  by the Tsukai reference handler ("Synthesize the batch's captures into one dated
  status update, grouped by category").
- **Field template** — the interpreter performs a mechanical join of the declared
  fields across the group items, no model call. Useful when the handler output is
  formulaic (e.g. a bullet list of `[[link]] — category`).

The two modes are mutually exclusive by schema design (string xor array) so the
interpreter never has to guess which path to take. The `compose_mode` key in the
group-result JSON is the resolver's declaration of which path was active for the
match — the interpreter reads it rather than re-inspecting the original handler file.
Surfacing it in the group-result schema keeps the interpreter decoupled from the
registry read.

## Cold-Path / AC-5 Byte-Identity Note

WHY: The `If handled[] is absent or empty, do NOT load this skill` gate in the runtime file is the only mechanism needed for AC-5 compliance from the skill side. The conductor's Step 3a mirrors this gate. When the tag-handler registry is empty or no item matched, `routing-plan.json` omits the `handled` key entirely (triage emits nothing rather than an empty array — SDD §5 schema-change note). Both absent-key and empty-array are guarded by the same `do NOT load` condition, so a zero-handler run never enters the interpreter code path.

## Structure-Aware Compose (spec 025)

> Spec: docs/XDD/specs/025-structure-aware-tag-handler-compose/ — ADR-1/ADR-3/ADR-8.

WHY (the orchestration script, ADR-3): structure parsing and row/anchor assembly MUST be deterministic and testable without an LLM (Constitution L1 Code Quality; ADR-3). The interpreter is an LLM skill and cannot call a Python function directly, so it shells out to `tomo/scripts/tag-handler-compose.py`, a thin script that imports the pure `tomo/scripts/lib/target_structure.py` helper and returns the assembled `composed_block` + `resolved_anchor` (or a typed fallback). This keeps the skill→script→lib boundary intact: the LLM produces only the `synthesize` cell values; all parsing, sanitising, row assembly, and anchor selection happen in deterministic, unit-tested code. The skill never reconstructs a table — a re-pretty-printed table would not byte-match the target's header/separator and the newest-first block anchor would silently fail to insert.

WHY (LLM produces only synth values; `granularity` scope): `field` cells are raw frontmatter/read_fields values that need no model call; only `synthesize` cells are model-driven (ADR-3 minimises the LLM surface). `per_item` granularity runs the synth directive once per source capture (N rows); `merged` runs it once over the whole batch (1 row). Reusing the cell `synthesize` directives at batch scope (ADR-5) avoids a separate merge-directive field — `per_item` vs `merged` is just the scope at which the same directive runs.

WHY (the payload hop): the skill hands the script a `tomo-tmp/compose-payload-<i>.json` with `section_lines` (the verbatim target section read in step 2), `output_format`, `cell_values_per_item`, and `marker`. Passing structured args through a payload file (not an inline interpreter one-liner) avoids quoting/`!` fragility and keeps the script's contract testable.

WHY (fallback to prose, ADR-8): when the helper signals a mismatch (cell-count ≠ columns, or no table/list under the marker), the script returns `status:"fallback"` with a typed reason. Proposal-first means the system never writes a malformed row — the interpreter degrades to a plain prose status block (today's behaviour) and records `fallback.reason` on the group-result so the reducer can surface a ⚠️ and the user approves knowingly. The deterministic helper guarantees it never emits a half-formed row.

WHY (STRICT reword, N rows ≠ N blocks): the one-block-per-group invariant (024 FR-8/AC-3) still holds for structure-aware groups, but the failure mode inverts — instead of the LLM splitting a merged update into N blocks, it must understand that N table rows / list items all live inside ONE `composed_block` (one group-result, one insertion). The STRICT line is reworded so the model does not emit one group-result per row.

WHY (compose-path PRECEDENCE, SKILL 0.2.1, live-walk fix 2026-06-26): a structure-aware handler carries BOTH `output_format` AND a `compose` string (the string is the prose-fallback wording). The first live `/inbox` walk showed the interpreter matching the familiar "compose is a STRING → prose" branch and ignoring `output_format` entirely (group-result had no output_format/resolved_anchor; it wrote a prose block). Static review couldn't catch this — both branches "matched" the dual-field stub. Fix: step 3 is now an explicit PRECEDENCE — `output_format` presence is path 1 and MANDATORY; paths 2/3 are gated on `output_format` being ABSENT; the `compose` string is demoted to fallback-wording-only inside path 1. The lesson: when a runtime branch can match on two independent fields, the SKILL must state precedence explicitly — an unordered list of "if" headers lets the LLM pick the most familiar one.
