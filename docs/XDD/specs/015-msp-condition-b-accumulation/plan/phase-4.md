---
phase: 4
title: "Consumer + orchestration + docs"
status: in_progress
---

# Phase 4: Consumer + orchestration + docs

## Phase Context

**GATE**: Read all referenced files before starting.

**Specification References**:
- `[ref: SDD/Runtime View/Secondary Flow]` — Step 4 Condition-B block + A7 precedence
- `[ref: SDD/Directory Map]` — vault-explorer Step 9 invocation, version bumps
- `[ref: PRD/A3, A7, A9]` — Step-4 trigger, C-over-B precedence, docs + version bumps

**Key Decisions**: Step 4 block mirrors the existing `placeholder_mocs` trigger; Condition C
wins on conflict (A7). These are runtime LLM-loaded files — imperatives only, rationale to
`docs/tomo/` (CLAUDE.md runtime-file rule). Version bumps are number-only (memory
`feedback_version_comments_number_only`).

**Dependencies**: Phase 3 (`shared_ctx.accumulation_index` must exist before the consumer can read it).

## Tasks

### T4.1 — inbox-analyst Step 4 Condition-B trigger `[activity: agent-spec]`

1. **Prime**: Read `tomo/dot_claude/agents/inbox-analyst.md` Step 4 in full (the MOC scoring, Classification Guard, and the `placeholder_mocs` trigger block ~113-150). Read `[ref: SDD/Runtime View/Secondary Flow]` and `[ref: PRD/A3, A7]`. Read memory `feedback_verbatim_strings_need_strict_comments` if any PRD-locked wording is involved.
2. **Test**: Author `tests/fixtures/` shared-ctx fixtures + a parser-level check (mirror existing inbox-analyst test style): `accumulation_index` present + item topic matches a key → expected `needs_new_moc: true`, `proposed_moc_topic = <key>`, `candidate_mocs[]` preserved; item topic no match → no trigger; BOTH placeholder + accumulation match same item → placeholder wins (A7); `accumulation_index` absent → silent skip (A6). (Validation is against the documented contract + a fixture-driven dry check, since this is an agent spec — memory `feedback_mock_at_orchestrator_not_helper`.)
3. **Implement**: Add an "Accumulation cluster trigger" block to Step 4 AFTER MOC scoring and AFTER the placeholder block, BEFORE finalising `needs_new_moc`. Imperatives: when `shared_ctx.accumulation_index` present, compare each item topic (case-insensitive, whitespace-normalised) to index keys; on match set `needs_new_moc: true`, `proposed_moc_topic = <key>`, keep `candidate_mocs[]`. STRICT precedence note: **if the placeholder block already set `proposed_moc_topic`, do NOT overwrite** (A7 — C wins). Absent/empty → skip silently. Bump `# version:`.
4. **Validate**: run the fixture checks; re-run the inbox-analyst authoring audit (memory `feedback_audit_skills_agents_after_edits`); confirm the instance copy bumps on sync (memory `feedback_bump_version_on_managed_file_edit`).
5. **Success**: Condition B fires on key match `[ref: PRD/A3]`; C beats B `[ref: PRD/A7]`; absent index → no behaviour change `[ref: PRD/A6]`.

### T4.2 — vault-explorer Step 9 runs the scanner `[activity: agent-spec]`

1. **Prime**: Read `tomo/dot_claude/agents/vault-explorer.md` Step 9 (moc-tree-builder → cache-builder invocation, ~550-580). Read `[ref: SDD/Directory Map]` + `[ref: SDD/Deployment View]`.
2. **Test**: N/A automated (orchestration spec); validation is the Step-9 command running end-to-end in Phase 5 (T5.1). Document the expected command shape here.
3. **Implement**: In Step 9, add the scanner invocation before cache-builder and pass its output in:
   ```
   python3 scripts/atomic-note-indexer.py --config config/vault-config.yaml > "tomo-tmp/accumulation-output.json"
   python3 scripts/cache-builder.py --structure "tomo-tmp/scan-output.json" \
     --mocs "tomo-tmp/moc-output.json" --accumulation "tomo-tmp/accumulation-output.json" \
     --output config/discovery-cache.yaml --start-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
   ```
   Keep STRICT cache rules intact. If the scanner fails, surface to stderr and proceed with cache-builder WITHOUT `--accumulation` (graceful: empty index, not a failed scan — SDD Error Handling). Bump `# version:`.
4. **Validate**: dry-read the Step-9 block for correctness; confirm no `2>&1`-into-JSON (memory `feedback_never_redirect_stderr_into_json`); full check in T5.1.
5. **Success**: `/explore-vault` produces `unclassified_topic_clusters` in the cache `[ref: PRD/A1]`; scanner failure degrades gracefully `[ref: SDD/Error Handling]`.

### T4.3 — Documentation + Tier-3 spec `[activity: docs]`

1. **Prime**: Read `docs/XDD/reference/` Tier-3 "New MOC Proposal" spec (Conditions A–D). Read the CLAUDE.md runtime-file/docs-mirror rule. Identify the `docs/tomo/` mirror path for the new script.
2. **Test**: N/A (docs). Validation = link/anchor check + reviewer read.
3. **Implement**: (a) Create `docs/tomo/scripts/atomic-note-indexer.md` — WHY-persistence for the runtime script (why a separate script per ADR-1, why per-candidate `up::` per ADR-5, the Kado-release dependency). (b) Update the Tier-3 New MOC Proposal spec: mark Condition B **implemented**, point at XDD 015. (c) Update `docs/XDD/backlog.md` F-34 (code-complete pending live validation). `[ref: PRD/A9]`
4. **Validate**: links resolve; Tier-3 audit shows no "missing" entry for Condition B; backlog F-34 reflects status.
5. **Success**: Tier-3 marks B shipped, points at 015 `[ref: PRD/A9]`; runtime WHY captured in `docs/tomo/`.
