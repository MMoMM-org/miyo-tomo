---
title: "Phase 4: Runtime prose: analyst and skills"
status: in_progress
version: "1.1"
phase: 4
---

# Phase 4: Runtime prose: analyst and skills

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-3]` — Step 4 names, Step 7.5b fetch, score by meaning
- `[ref: SDD/Runtime View; Primary Flow, Decision table, Error Handling]`
- `[ref: SDD/ADR-8]` — delete-before-build, `--run-id`
- `[ref: SDD/Implementation Gotchas]` — prose tests and headings
- CLAUDE.md rules: runtime files carry only imperatives; WHY to `docs/tomo/` **first**, strip second

**Key Decisions**:
- No STRICT block is added. The existing Step-1 STRICT is retargeted (it now forbids `--field mocs`), because that is the observed failure it already guards.
- The name-check is decision-table row 2, before `needs_new_moc` is finalised; it covers the zero-match case today's prose leaves open.
- Classification MOCs may be nominated and become unticked candidates, as today (owner, 2026-10-24).
- T4.2 and T4.3 start only after T4.1 (WHY first).

**Dependencies**: Phase 2 (reader modes), Phase 3 (count to relay).

---

## Tasks

The analyst reads names, nominates by meaning, fetches detail once, and checks proposals; both inbox paths build a fresh context and relay the duplicate count.

- [x] **T4.1 WHY first: analyst and skill docs** `[activity: technical-writing]`

  1. Prime: `docs/tomo/dot_claude/agents/inbox-analyst.md` (Step-1 and read-shared-ctx sections); `docs/tomo/dot_claude/skills/suggest-handling.md`; `docs/tomo/dot_claude/skills/force-atomic-handling.md` `[ref: SDD/ADR-3, ADR-8; CLAUDE.md WHY-persistence rule]`
  2. Test: n/a (document). Checklist: why the full list is never read (spill, cost, recall data); why names come from a file named by `to_filename`; why detail is fetched after Step 7.5 and capped at 20 in thread order; why score is by meaning (25 of 52 zero-overlap picks); why the name-check sits before `needs_new_moc` and excludes classification names; why any reader failure fails the item; why the context is deleted before build and checked by run id
  3. Implement: the three docs pages
  4. Validate: every rationale that T4.2/T4.3 will remove from runtime files is present here
  5. Success: no institutional knowledge lost by the prose edits `[ref: CLAUDE.md rule]`

- [ ] **T4.2 Analyst prose: Step 1, Step 4, Step 7.5b, Step 10.3, output rules** `[activity: prompt-authoring]`

  1. Prime: T4.1; `tomo/dot_claude/agents/inbox-analyst.md` Step 1, Step 4, Step 7.5, Step 10.3, Step 11, output rules; `tests/test_inbox_analyst_no_condition_b.py`; `tests/test_inbox_analyst_segmentation.py`; `tests/test_034_t2_2_analyst_contract.py:76`; `tests/test_read_shared_ctx.py` `TestAgainstTheRealContract` `[ref: SDD/ADR-3; SDD/Runtime View]`
  2. Test (prose contract):
     - RED: Step 4 names `--moc-names` and `--field placeholder_targets`, each with `--run-id {run_id}`, and never `--field mocs`; a `### Step 7.5b` heading sits between `### Step 7.5` and `### Step 8`, runs `item-result-filename.py` before writing, names `{items_dir}/<result stem>.moc-names.txt`, "at most 20", "thread order", and `--mocs-from`, and says to skip the read when nothing was nominated; Step 10.3 reuses the captured filename instead of computing it; Step 4 states the nomination cap (6 per thread), score as confidence by meaning with 0.15 / 0.5 kept, and the four-row decision table in order; a non-zero reader exit → Step 11 failure with an issue; unresolved names are dropped with an issue; anchor tiers read the fetched detail
     - deliberate test change: `placeholder_links` → `placeholder_targets` and retire "absent or empty" in `test_inbox_analyst_no_condition_b.py`, with the reason
     - guard: "Classification Guard", "is_classification", "needs_new_moc", "Placeholder link trigger", "verbatim", "casing", "takes precedence" still in Step 4; state-update block count unchanged; every `shared_ctx.<path>` named resolves in the contract fixture
  3. Implement: edit the runtime prose (imperatives only); bump `# version`
  4. Validate: RED on `main`; GREEN here; all prose-contract tests green
  5. Success: `[ref: PRD/F2-AC1, F2-AC3, F2-AC4, F2-AC5, F3-AC2, F3-AC3, F6-AC2 (analyst side), S1-AC2]`; F3-AC1 is proven in the live run (T6.3)

- [ ] **T4.3 Skills: delete-before-build, run-id reads, Step 7 relay** `[activity: prompt-authoring]`

  1. Prime: T4.1; `tomo/dot_claude/skills/suggest-handling/SKILL.md` setup (`:35-59`), dispatch (`:99-121`), Step 7 (`:165-169`); `tomo/dot_claude/skills/force-atomic-handling/SKILL.md` setup (`:31-54`), dispatch (`:76-99`), report; `scripts/reset-tomo-tmp.sh` `reset_pass1` `[ref: SDD/ADR-8; PRD/F6]`
  2. Test (prose contract):
     - RED: both skills run `rm -f tomo-tmp/shared-ctx.json` before the builder; both Step 7 reports relay `duplicate_proposals_converted` from the reducer's summary line
     - guard: both builder commands are identical; both relay builder WARN lines; `reset-tomo-tmp.sh --pass1` leaves no `shared-ctx.json` and no `items/*.moc-names.txt` (temp instance dir)
  3. Implement: edit both skills; bump versions
  4. Validate: RED on `main`; GREEN here
  5. Success: `[ref: PRD/F6-AC1, F6-AC3, F4-AC4 (relay)]`

- [ ] **T4.4 Phase Validation** `[activity: validate]`

  - Full suite green, ruff clean. Read the analyst file top to bottom once as the model would: no reference to `shared_ctx.mocs`, `--field mocs`, `placeholder_links` or the lexical formula as the decider remains. `rg -n "placeholder_links|--field mocs" tomo/dot_claude tomo/scripts` (untruncated) — only the cache-side producer may still mention `placeholder_links`.
