# 2026-05-21 — F-47.P5 Token-Cost Measurement + Full PRD AC E2E Validation

**Context**: F-47.P5 (Phase 6) closes the spec. T6.3 (token-cost measurement vs PRD §7 baselines) and T6.4 (full PRD AC E2E verification) require live runs against Privat-Test. T6.3 **instrumentation + tooling are now permanent** (see "What's already shipped" below); operator just runs the measurement on demand.

**Status**: Operator-side runs remain deferred. T6.3 infra is live (commit `4849545`).

---

## T6.3 — Token-cost measurement (instrumentation SHIPPED, ongoing observability)

**Targets per PRD §7**:
- Steady-state `/inbox` discovery: **≤ 2,000 tokens**
- Heavy-state `/inbox` discovery: **≤ 6,000 tokens**

### What's already shipped (2026-05-21, commit `4849545`)

1. **`inbox-discovery.py` v0.3.0** emits a structured JSON `lifecycle.discovery` event to stderr on every `/inbox` run, with all PRD §7 properties (`token_estimate`, `byFrontmatter_hits`, `listDir_hits`, `pending_body_reads`, `bucket_counts`, `drift_hint_emitted`, `phase_a_duration_ms`, `run_id`).
2. **`scripts/measure-f47-token-cost.py` v0.1.0** parses a captured stderr trace OR a Claude Code session JSONL transcript, finds the events, aggregates `token_estimate` against PRD §7 budgets, auto-classifies steady vs heavy from bucket counts.

This is **permanent observability infrastructure**, not throwaway F-47 tooling. Keep it in the repo and re-run periodically to catch cost regressions when vault size grows, new doc-types ship, or renderer payloads change.

### Procedure

1. **Setup** (prerequisite: Privat-Test reset per `2026-05-21_F-47-privat-test-reset.md`):
   - Steady scenario: Privat-Test inbox has only 1-2 captured docs (post-reset clean state).
   - Heavy scenario: 3 instructions + 2 suggestions + 1 moc-proposal + 5 source items manually placed.

2. **Run** — no special stderr capture needed; Claude Code records every tool call (including `inbox-discovery.py` stderr) in the session JSONL automatically.
   ```bash
   # In tomo-instance container:
   /inbox
   # repeat after re-populating inbox for the heavy scenario
   ```

3. **Measure** — from host repo (`/Volumes/Moon/Coding/MiYo/Tomo`):
   ```bash
   # Latest session (auto-discovers most recent tomo-instance jsonl)
   python3 scripts/measure-f47-token-cost.py --session-latest

   # Or explicit session jsonl
   python3 scripts/measure-f47-token-cost.py --session tomo-home/.claude/projects/.../UUID.jsonl

   # Or captured stderr trace (if you piped it during a manual run)
   python3 scripts/measure-f47-token-cost.py --stderr /tmp/F47-trace.log

   # Override auto-classified scenario if needed
   python3 scripts/measure-f47-token-cost.py --session-latest --scenario heavy
   ```

   Output per event: `token_estimate`, all bucket counts, phase-A duration, drift status, PASS/FAIL verdict vs budget.

4. **Pass criteria**:
   - Steady `total_token_estimate` ≤ 2,000
   - Heavy `total_token_estimate` ≤ 6,000

5. **On failure**: investigate dominant cost (likely candidates: Kado response shape carrying too much frontmatter content per hit; body-reads on too many pending docs). File as a F-47 follow-up to `docs/XDD/backlog.md`.

---

## T6.4 — Full PRD AC E2E verification

**Four PRD §6 flow diagrams** must each verify end-to-end on Privat-Test:

### §6.1 — Best-case `/inbox` (single fresh source)

1. Drop one fresh `.md` into Privat-Test inbox.
2. Run `/inbox`.
3. Verify:
   - `<ts>_suggestions.md` produced with `tomo.state=pending-approval, tomo.doc_type=suggestions`.
   - Source carries `tomo.state=captured, tomo.doc_type=source`.
4. Tick `- [x] Approved` in the suggestions doc.
5. Run `/inbox`.
6. Verify:
   - Suggestions `tomo.state` flips to `approved`.
   - `<ts>_instructions.md` produced with `tomo.state=pending-apply, tomo.source_suggestions=<suggestions-path>`.
7. (If Hashi 0.3.0+ adopted — out of F-47 scope) Apply via Hashi → verify cleanup chain.

### §6.2 — Best-case `/moc-propose` (single accepted cluster)

1. Tag 5+ Privat-Test notes with `#topic-test-mode-tag`.
2. Run `/moc-propose tag:topic-test-mode-tag`.
3. Verify proposal-doc `tomo.state=pending-accept, tomo.doc_type=moc-proposal`.
4. Tick `- [x] Accept` on MOC01 (3 children).
5. Run `/inbox`.
6. Verify:
   - Bundled instructions doc with 1× `create_moc` + 3× `add_relationship`.
   - `tomo.source_moc_proposal=<proposal-path>`.
   - Proposal-doc flips to `accepted`.

### §6.3 — Mixed-state run

Prepare inbox:
- (a) Old captured source (from prior run).
- (b) Pending-apply instructions (manual placement).
- (c) Pending-approval suggestions (manual placement) with `[x] Approved` ticked.
- (d) Pending-accept moc-proposal (manual placement) with `[x] Accept` ticked on one cluster.
- (e) Fresh untagged source.

Run `/inbox`. Verify:
- Discovery returns 3 pending hits + 1 captured + 1 newSource.
- Sequential state-promoter dispatches Pass-2 for (c) and (d).
- Pass-1 runs for (e).
- Final summary lists ≥ 1 pending-apply path via parallel-instructions warning text.

### §6.4 — Drift recovery

1. Inbox has 3 captured sources, 0 pending docs.
2. Run `/inbox` (without `--recover`).
3. Verify drift hint emitted verbatim with count=3 + recover command.
4. Run `/inbox --recover`.
5. Verify:
   - Captured docs treated as fresh sources.
   - New suggestions docs produced.
   - Captured tags idempotently re-asserted (no exception on second write).

---

## Recording results

For each scenario passing: tick the corresponding PRD AC checkbox in `tomo/docs/XDD/specs/017-tomo-lifecycle-tags/requirements.md` (search for `- [ ] **AC-...**` and flip to `- [x]`).

For each scenario failing: file as a F-47 follow-up to `docs/XDD/backlog.md` AND log in `_outbox/for-claude/` for the next session to triage.

After all four scenarios pass: spec 017 is functionally validated. T6.6 then closes the spec (Current Phase → COMPLETE, Status → COMPLETE, final Decisions Log entry).

---

## References

- PRD §6 (flow diagrams) + §7 (Success Metrics).
- SDD Quality Requirements lines 1107-1109 (performance targets).
- Phase 3 deliverable `lifecycle.discovery` event with `token_estimate` property.
- Sibling evolution entries:
  - `2026-05-21_F-47-privat-test-reset.md` (T3.5 prerequisite — clean vault).
  - `2026-05-21_F-47-P4-moc-consumption-launch-gate.md` (T5.4 sibling — F-43 modes).
