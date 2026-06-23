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

## Cold-Path / AC-5 Byte-Identity Note

WHY: The `If handled[] is absent or empty, do NOT load this skill` gate in the runtime file is the only mechanism needed for AC-5 compliance from the skill side. The conductor's Step 3a mirrors this gate. When the tag-handler registry is empty or no item matched, `routing-plan.json` omits the `handled` key entirely (triage emits nothing rather than an empty array — SDD §5 schema-change note). Both absent-key and empty-array are guarded by the same `do NOT load` condition, so a zero-handler run never enters the interpreter code path.
