---
title: "Phase 4: Runtime prose: analyst and skills"
status: completed
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

- [x] **T4.2 Analyst prose: Step 1, Step 4, Step 7.5b, Step 10.3, output rules** `[activity: prompt-authoring]`

  1. Prime: T4.1; `tomo/dot_claude/agents/inbox-analyst.md` Step 1, Step 4, Step 7.5, Step 10.3, Step 11, output rules; `tests/test_inbox_analyst_no_condition_b.py`; `tests/test_inbox_analyst_segmentation.py`; `tests/test_034_t2_2_analyst_contract.py:76`; `tests/test_read_shared_ctx.py` `TestAgainstTheRealContract` `[ref: SDD/ADR-3; SDD/Runtime View]`
  2. Test (prose contract):
     - RED: Step 4 names `--moc-names` and `--field placeholder_targets`, each with `--run-id {run_id}`, and never `--field mocs`; a `### Step 7.5b` heading sits between `### Step 7.5` and `### Step 8`, runs `item-result-filename.py` before writing, names `{items_dir}/<result stem>.moc-names.txt`, "at most 20", "thread order", and `--mocs-from`, and says to skip the read when nothing was nominated; Step 10.3 reuses the captured filename instead of computing it; Step 4 states the nomination cap (6 per thread), score as confidence by meaning with 0.15 / 0.5 kept, and the four-row decision table in order; a non-zero reader exit → Step 11 failure with an issue; unresolved names are dropped with an issue; anchor tiers read the fetched detail
     - deliberate test change: `placeholder_links` → `placeholder_targets` and retire "absent or empty" in `test_inbox_analyst_no_condition_b.py`, with the reason
     - guard: "Classification Guard", "is_classification", "needs_new_moc", "Placeholder link trigger", "verbatim", "casing", "takes precedence" still in Step 4; state-update block count unchanged; every `shared_ctx.<path>` named resolves in the contract fixture
  3. Implement: edit the runtime prose (imperatives only); bump `# version`
  4. Validate: RED on `main`; GREEN here; all prose-contract tests green
  5. Success: `[ref: PRD/F2-AC1, F2-AC3, F2-AC4, F2-AC5, F3-AC2, F3-AC3, F6-AC2 (analyst side), S1-AC2]`; F3-AC1 is proven in the live run (T6.3)

  6. Deviations recorded during implementation (2026-10-24):
     - Path placeholders follow the file's own convention: `<items_dir>/<result_stem>.moc-names.txt`, not the SDD's `{items_dir}/…`.
     - Nomination covers only threads that become a `create_atomic_note`. The reducer gives suppressed atomics no MOC framing, and a pure daily item should pay only for the name list. The Step-4 wording separates "read every name now" from "nominate once Step 7.5 has formed the threads", because Step 4 is read before Step 7.5 runs.
     - Row 2 of the decision table keeps an already-fetched MOC. The name-check therefore runs at nomination time ("also nominate any thematic name that covers a MOC you would otherwise propose"), so the covering MOC is in the single Step-7.5b fetch.
     - A failing reader is recorded with `--error-kind shared_ctx_unavailable` (free string, no enum in `state-update.py`).
     - Step 4 now opens with a precedence line: its rules replace `lyt-patterns`' MOC Matching Algorithm and Placeholder link awareness for this agent. The skill is shared with `moc-architect` and `vault-explorer`, which read the cache, so it stays unchanged.
     - The "old shared-ctx artifact → omit anchor" paragraph is removed. That case can no longer reach the analyst, and TIER-4 covers an entry without inventory.
     - Deliberate test changes, each with its reason in the test: `test_034_t2_2_analyst_contract.py` (the helper call moved to Step 7.5b); `test_inbox_analyst_no_condition_b.py` (`placeholder_targets`, "empty" instead of "absent or empty"); `test_read_shared_ctx.py` (the Phase-4 tripwire fired as designed and is removed).
     - RED: 16 of 16 in `tests/test_040_analyst_prose.py` fail against `main`'s agent.

- [x] **T4.3 Skills: delete-before-build, run-id reads, Step 7 relay** `[activity: prompt-authoring]`

  1. Prime: T4.1; `tomo/dot_claude/skills/suggest-handling/SKILL.md` setup (`:35-59`), dispatch (`:99-121`), Step 7 (`:165-169`); `tomo/dot_claude/skills/force-atomic-handling/SKILL.md` setup (`:31-54`), dispatch (`:76-99`), report; `scripts/reset-tomo-tmp.sh` `reset_pass1` `[ref: SDD/ADR-8; PRD/F6]`
  2. Test (prose contract):
     - RED: both skills run `rm -f tomo-tmp/shared-ctx.json` before the builder; both Step 7 reports relay `duplicate_proposals_converted` from the reducer's summary line
     - guard: both builder commands are identical; both relay builder WARN lines; `reset-tomo-tmp.sh --pass1` leaves no `shared-ctx.json` and no `items/*.moc-names.txt` (temp instance dir)
  3. Implement: edit both skills; bump versions
  4. Validate: RED on `main`; GREEN here
  5. Success: `[ref: PRD/F6-AC1, F6-AC3, F4-AC4 (relay)]`

  6. Notes recorded during implementation (2026-10-24):
     - The count is reported only when it is above zero (WHY in `docs/tomo/dot_claude/skills/suggest-handling.md`).
     - RED: 5 of 9 tests in `tests/test_040_skill_prose.py` fail against `main`. The 4 that pass there are the planned guards: identical builder commands, the WARN relay (×2), and reset clearing the context and the names files.

- [x] **T4.4 Phase Validation** `[activity: validate]`

  - Full suite green, ruff clean. Read the analyst file top to bottom once as the model would: no reference to `shared_ctx.mocs`, `--field mocs`, `placeholder_links` or the lexical formula as the decider remains. `rg -n "placeholder_links|--field mocs" tomo/dot_claude tomo/scripts` (untruncated) — only the cache-side producer may still mention `placeholder_links`.
  - Result (2026-10-24, at e2c00454): 5087 passed, 5 skipped. The skips are environment-dependent: an offline upstream schema fetch, gitignored or absent fixtures, no whisper model. None is a spec 040 test. Ruff is clean. Read-through: the analyst file has no `shared_ctx.mocs`, `--field mocs`, `placeholder_links` or overlap formula left. Step 5's "keyword-overlap" is classification and unchanged. The untruncated `rg` over `tomo/dot_claude tomo/scripts` leaves three kinds of hits:
    - the cache-side producers (`moc-tree-builder`, `cache-builder`, `shared-ctx-builder`'s cache filter, `vault-summary`)
    - `lyt-patterns:90`, which is cache-side and correct for `moc-architect`/`vault-explorer`; the analyst's Step 4 states it is overridden
    - two historical measurements in `read-shared-ctx.py`'s header docstring
