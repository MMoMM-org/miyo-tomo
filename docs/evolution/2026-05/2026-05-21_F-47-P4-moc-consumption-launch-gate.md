# 2026-05-21 — F-47.P4 Phase 5 MOC-Consumption Launch Gate

**Context**: F-47.P4 (MOC-consumption) closes the F-43 acceptance gap. T5.1+T5.2+T5.3 ship the parser MOC-dispatch + instruction-builder MOC-branch + squelch persistence. T5.4 is the F-43 T6.2/T6.4 launch gate — runtime smoke against Privat-Test for all 5 paused modes.

**Status**: **DEFERRED — operator action required.** Cannot run from inside the Tomo container or orchestrator session. The operator must run the smoke matrix manually.

---

## What this unblocks

Per the F-43 PAUSED tasks (`docs/XDD/specs/013-moc-creation-skill/plan/phase-6.md` T6.2 + T6.4):
- T6.2 = manual smoke for 5 `/moc-propose` modes (folder, class, title, free-text, scan)
- T6.4 = final launch gate (6 happy-path E2E runs including tag-mode regression)

Both were paused on F-47.P2 (consumer cut-over — shipped in Phase 3) and F-47.P4 (MOC-consumption — shipped in Phase 5). All upstream code is now live; this is the final acceptance pass.

---

## Smoke matrix (operator-side)

For each `/moc-propose` mode below: prepare Privat-Test → run command → verify proposal-doc → tick accept → run /inbox → verify bundled instructions → simulate Hashi apply → verify final MOC artifact.

### Mode 1: tag-mode (regression — F-43's original happy path)

1. Prepare: ensure 5+ notes in Privat-Test carry tag `#topic-test-mode1` (any topic).
2. Run: `/moc-propose tag:topic-test-mode1`.
3. Verify proposal-doc:
   - Lands in inbox folder as `<ts>_tomo-moc-proposal-tag-topic-test-mode1.md` (or current naming pattern).
   - Frontmatter carries `tomo: {doc_type: moc-proposal, state: pending-accept, run_id, updated_at}`.
4. Tick `- [x] Accept` on the first MOC cluster (`### MOC01`) in Obsidian.
5. Run: `/inbox`.
6. Expected:
   - Orchestrator discovers proposal-doc via byFrontmatter (`tomo.state=pending-accept`).
   - State-promoter dispatches instruction-builder MOC-branch.
   - Bundled instructions doc produced with 1× `create_moc` + N× `add_relationship` (one per child).
   - `tomo.source_moc_proposal=<proposal-doc-path>` set on instructions doc.
   - Proposal-doc `tomo.state` flips to `accepted`.
7. Simulate Hashi apply (or wait for Hashi 0.2.0 destination-collision guard from F-43 T1.1):
   - New MOC file in inbox folder: `<YYYY-MM-DD>_<slugified-title>.md`.
   - Children each carry `up:: [[<moc-title>]]`.
   - Instructions doc + proposal-doc trashed.

### Mode 2: folder-mode

Run: `/moc-propose folder:<path-to-folder>`. Repeat steps 3-7 above. Expected same shape.

### Mode 3: class-mode

Run: `/moc-propose class:<obsidian-class>`. Repeat 3-7.

### Mode 4: title-mode (regex)

Run: `/moc-propose title:<regex-pattern>`. Repeat 3-7.

### Mode 5: free-text

Run: `/moc-propose <natural language description>`. Repeat 3-7.

### Mode 6: scan-mode

Run: `/moc-propose --scan`. Verify scan produces proposal-doc covering the whole vault scope. Repeat 4-7 for at least one cluster.

### Multi-cluster acceptance (AC-5.2 bundling check)

For ONE of the above modes (tag-mode is fine):
1. Prepare: ensure the proposal-doc has 3+ clusters.
2. Tick `[x] Accept` on MOC01 and MOC03 only; leave MOC02 unticked.
3. Run `/inbox`.
4. Expected:
   - ONE bundled instructions doc with 2× `create_moc` (MOC01 + MOC03) + N× `add_relationship`.
   - MOC02 NOT in instructions; its topic_signature persisted to `state/moc-squelch.json` (per AC-5.2 + OQ12).
   - Proposal-doc `tomo.state` = `accepted` (single transition; no file-level `rejected` state on MOC02).

---

## What to record

For each mode that passes: tick the corresponding checkbox in `docs/XDD/specs/013-moc-creation-skill/plan/phase-6.md` T6.2 + T6.4.

For each mode that fails: file as a F-47.P4 deviation under T5.4 in this file (or as a `_outbox/for-claude/` handoff). Do NOT label it as a F-43 regression — F-43 was paused expecting F-47 changes.

---

## Token-cost note

Per PRD §7, the heavy /inbox token budget is **6,000 tokens**. After the smoke run, check stderr for the `lifecycle.discovery` event to confirm the run stayed within budget. Out-of-budget = flag as a follow-up; not a launch blocker unless catastrophic.

---

## References

- `docs/XDD/specs/013-moc-creation-skill/plan/phase-6.md` (T6.2 + T6.4 — F-43 paused tasks).
- `docs/XDD/specs/017-tomo-lifecycle-tags/requirements.md` AC-5.1, AC-5.2, AC-5.3, AC-5.4.
- `docs/XDD/specs/017-tomo-lifecycle-tags/solution.md` Cross-Spec Coordination lines 956-960.
- Memory: `reference_test_vault_path`.
- Sibling evolution entry: `docs/evolution/2026-05/2026-05-21_F-47-privat-test-reset.md` (T3.5 prerequisite — clean vault BEFORE this gate).
