---
title: "Phase 4: Runtime prose: analyst and skills"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Runtime prose: analyst and skills

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-3]` — Step 4 names, Step 7.5b fetch, score by meaning
- `[ref: SDD/Runtime View; Primary Flow, Decision table]`
- `[ref: SDD/ADR-8]` — delete-before-build, `--run-id`
- `[ref: SDD/Implementation Gotchas]` — prose tests and headings
- CLAUDE.md rules: runtime files carry only imperatives; WHY to `docs/tomo/` **first**, strip second

**Key Decisions**:
- No STRICT block is added by default. The existing Step-1 STRICT is rewritten (it now forbids `--field mocs`), because that is the observed failure mode it already guards.
- The name-check is decision-table row 2, before `needs_new_moc` is finalised; it covers the zero-match case today's prose leaves open.

**Dependencies**: Phase 2 (reader modes) and Phase 3 (count to relay).

---

## Tasks

The analyst reads names, nominates by meaning, fetches detail once, and checks proposals; both inbox paths build a fresh context and relay the duplicate count.

- [ ] **T4.1 WHY first: analyst and skill docs** `[activity: technical-writing]`

  1. Prime: `docs/tomo/dot_claude/agents/inbox-analyst.md:220, 399-483`; `docs/tomo/dot_claude/skills/suggest-handling.md:101-203`; `docs/tomo/dot_claude/skills/force-atomic-handling.md` `[ref: SDD/ADR-3, ADR-8; CLAUDE.md WHY-persistence rule]`
  2. Test: n/a (document). Checklist: why the full list is never read (spill, cost, recall data); why names come from a file; why detail is fetched after Step 7.5; why score is by meaning (25 of 52 zero-overlap picks); why the name-check sits before `needs_new_moc`; why the context is deleted before build and checked by run id
  3. Implement: the three docs pages updated
  4. Validate: every rationale that T4.2/T4.3 will remove from runtime files is present here
  5. Success: no institutional knowledge lost by the prose edits `[ref: CLAUDE.md rule]`

- [ ] **T4.2 Analyst prose: Step 1, Step 4, Step 7.5b, output rules** `[activity: prompt-authoring]`

  1. Prime: `tomo/dot_claude/agents/inbox-analyst.md:65-75, 129-249, 300-371, 720-752`; `tests/test_inbox_analyst_no_condition_b.py`; `tests/test_inbox_analyst_segmentation.py`; `tests/test_034_t2_2_analyst_contract.py:76`; `tests/test_read_shared_ctx.py` `TestAgainstTheRealContract` `[ref: SDD/ADR-3; SDD/Runtime View]`
  2. Test (RED, prose-contract): Step 4 names `--moc-names` and `--field placeholder_targets`, each with `--run-id {run_id}`, and never `--field mocs`; a `### Step 7.5b` heading exists between `### Step 7.5` and `### Step 8` and names `Write` to `{items_dir}/{item_key}.moc-names.txt` and `--mocs-from`; Step 7.5b says to skip the call when no names were nominated; Step 4 states the nomination cap (6 per thread), score as confidence by meaning with 0.15 / 0.5 kept, and the four-row decision table in order (placeholder, name-check against thematic names, needs_new_moc, otherwise); unresolved names are dropped with an issue; anchor tiers read the fetched detail; every `shared_ctx.<path>` the prose names resolves in the contract fixture; required strings in Step 4 still present ("Classification Guard", "is_classification", "needs_new_moc", "Placeholder link trigger", "verbatim", "casing") with `placeholder_links` → `placeholder_targets` changed in the test with its reason; state-update block count unchanged
  3. Implement: edit the runtime prose (imperatives only); bump `# version`
  4. Validate: RED on main; GREEN here; all prose-contract tests green; ruff clean (tests)
  5. Success: `[ref: PRD/F2-AC1, F2-AC3, F2-AC4, F2-AC5, F3-AC1, F3-AC2, F3-AC3, S1-AC2]`

- [ ] **T4.3 Skills: delete-before-build, run-id reads, Step 7 relay** `[activity: prompt-authoring]` `[parallel: true]`

  1. Prime: `tomo/dot_claude/skills/suggest-handling/SKILL.md:36-59, 99-121, 130-175`; `tomo/dot_claude/skills/force-atomic-handling/SKILL.md:36-50, 72-104`; `scripts/reset-tomo-tmp.sh:155-167` `[ref: SDD/ADR-8; PRD/F6]`
  2. Test (RED, prose-contract): both skills run `rm -f tomo-tmp/shared-ctx.json` before the builder; both builder commands are identical; both Step 7 reports relay `duplicate_proposals_converted` from the reducer's summary line; both relay builder WARN lines (existing behaviour kept); `reset-tomo-tmp.sh --pass1` leaves no `shared-ctx.json` and no `items/*.moc-names.txt` (test against a temp instance dir)
  3. Implement: edit both skills; bump versions
  4. Validate: RED on main; GREEN here
  5. Success: `[ref: PRD/F6-AC1, F6-AC2, F6-AC3, F4-AC4 (relay)]`

- [ ] **T4.4 Phase Validation** `[activity: validate]`

  - Full suite green, ruff clean. Re-read the analyst file top to bottom once as the LLM would: no reference to `shared_ctx.mocs`, `--field mocs`, `placeholder_links` or the lexical formula as the decider remains. Grep `tomo/dot_claude` and `tomo/scripts` for `placeholder_links` and `--field mocs` — only the cache-side producer may still mention `placeholder_links`.
