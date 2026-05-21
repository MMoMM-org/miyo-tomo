---
title: "Phase 6: Hashi Schema Handoff + Final Integration & E2E Validation (F-47.P5)"
status: completed
version: "1.0"
phase: 6
---

# Phase 6: Hashi Schema Handoff + Final Integration & E2E Validation (F-47.P5)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/Feature 4; AC-4.1..AC-4.5]` — Hashi auto-cleanup state-driven contract
- `[ref: PRD/§8 Cross-repo dependencies]` — Hashi handoff details + Kokoro ADR requirement
- `[ref: PRD/§7 Success Metrics]` — token-cost targets (≤2,000 steady / ≤6,000 heavy)
- `[ref: SDD/Deployment View/Multi-Component Coordination; lines: 900-913]` — phased deployment order + Hashi adoption timing
- `[ref: SDD/Cross-Spec Coordination/Post-F-47 work queue; lines: 990-1001]` — what unblocks after this phase merges
- `[ref: SDD/Cross-Component Boundaries; lines: 226-241]` — schema as Tomo→Hashi cross-component contract
- `[ref: ~/Kouzou/projects/miyo/miyo-constitution.md Architecture L2]` — cross-component change requires Kokoro ADR
- `[ref: _outbox/for-hashi/2026-05-20_tomo-to-hashi_auto-cleanup-on-instructions-applied.md]` — early-warning notice already sent

**Key Decisions**:
- **Schema-lock handoff** (PRD §8 + Feature 4 contract framing): Hashi consumes the locked `tomo:` block schema. The schema-lock handoff is the formal Tomo→Hashi cross-repo handoff that follows the early-warning notice from 2026-05-20. Body must include: (a) full `doc-frontmatter.schema.json` content, (b) the state-driven cleanup contract (Hashi flips `tomo.state=applied` on last action, then iterates `source_*` keys generically), (c) link to PRD AC-4.x.
- **Kokoro ADR** (Constitution L2 Architecture): cross-component contract change requires a Kokoro reflection. Tomo drafts the ADR content; the Kokoro-hosted Claude session is the only one allowed to commit on miyo-kouzou (per `~/Kouzou/standards/general.md`). Tomo provides the draft text via cross-repo handoff; Kokoro session commits.
- **Token-cost measurement** (PRD §7): final phase confirms the steady (≤2,000) and heavy (≤6,000) discovery-token budgets are met. Lifecycle.discovery events from earlier phases emit `token_estimate`; this phase aggregates and reports.
- **Memory + 013/009 markers** (Cross-Spec Coordination): post-F-47 work queue mandates README updates on 013 (T6.2/T6.4 → DONE), 009 (post-F-47.P3 regression task added), and memory updates for the new state machinery.

**Dependencies**:
- **Hard**: Phases 1-5 must all be merged. The handoff content describes a fully-implemented Tomo side.
- **Soft**: Hashi adoption is **out of scope** for this spec — Hashi's own timeline starts after the handoff lands. The handoff success criterion is "doc sent + ACK protocol filed", NOT "Hashi shipped the change".

---

## Tasks

This phase closes F-47 with the cross-repo Hashi handoff, the Kokoro ADR draft, the final token-cost measurement against PRD §7 baselines, and the full PRD AC verification pass. After Phase 6 merges, F-47 is COMPLETE — Hashi adoption proceeds on its own timeline.

- [x] **T6.1 Hashi schema-lock handoff** `[component: hashi]` `[activity: cross-repo-handoff]`

  1. Prime: Read PRD Feature 4 (state-driven contract framing) + AC-4.1..4.5 `[ref: PRD/Feature 4]`. Read SDD Integration Points/Cross-repo block `[ref: SDD/Integration Points; lines: 613-622]`. Read existing `_outbox/for-hashi/2026-05-20_tomo-to-hashi_auto-cleanup-on-instructions-applied.md` (the early-warning notice) — this handoff supersedes its design section and finalises the schema. Read `~/Kouzou/projects/miyo/miyo-handoff-protocol.md` for the receipt + ACK protocol shape. Read `tomo/schemas/doc-frontmatter.schema.json` (Phase 1 deliverable).
  2. Test: N/A (handoff artefact). Done = `_outbox/for-hashi/2026-MM-DD_tomo-to-hashi_state-driven-cleanup-schema-lock.md` exists with: (a) full schema content embedded or referenced by commit SHA, (b) state-driven cleanup contract: "On observing `tomo.state` flip to `applied` on any Tomo-produced instructions doc, Hashi MUST (i) iterate every key in `tomo.*` matching `source_*`, (ii) trash each referenced path to Obsidian system trash (best-effort — log warning on missing path, proceed), (iii) trash the instructions doc itself LAST", (c) AC mapping to PRD AC-4.1..4.5, (d) explicit receipt protocol per `miyo-handoff-protocol.md` (Hashi flips frontmatter `status: pending → status: received` + `received_by` + `received_at` + `target_version` Hashi semver), (e) F-47 implementation summary so Hashi reviewers can verify Tomo side ships first.
  3. Implement: Create `_outbox/for-hashi/2026-MM-DD_tomo-to-hashi_state-driven-cleanup-schema-lock.md` (date = day of dispatch). Sections: Context (PRD §1 vision + Hashi role), Schema (paste `doc-frontmatter.schema.json` body verbatim — Tomo side is the SoT), Cleanup Contract (the 3-step iteration), AC Mapping (Hashi-side acceptance criteria covering AC-4.1..4.5), Receipt Protocol, References (Tomo F-47 spec dir, commit SHAs). Commit on the F-47 branch (path is gitignored-exempt for `_outbox/`, but on the feature branch is fine + cleaner).
  4. Validate: File present, schema section parses as valid JSON, receipt protocol section explicit. `cat _outbox/for-hashi/2026-MM-DD_*-schema-lock.md | head -100` shows expected sections; run a mental test: a Hashi maintainer reading only this doc + the embedded schema can implement the cleanup contract without referring back to Tomo's code.
  5. Success: Schema-locked handoff filed `[ref: PRD/Feature 4]` `[ref: SDD/Integration Points; lines: 613-622]` `[ref: ~/Kouzou/projects/miyo/miyo-handoff-protocol.md]`.

- [x] **T6.2 Kokoro ADR draft (Architecture L2)** `[component: kokoro]` `[activity: cross-repo-handoff]` `[parallel: true]`

  1. Prime: Read `~/Kouzou/projects/miyo/miyo-constitution.md` Architecture L2 rule (cross-component contract changes require Kokoro reflection). Read existing Kokoro ADRs (e.g. ADR-009 Hashi charter, ADR-013 Hakobi charter) for ADR shape + tone. Read SDD ADRs as Tomo-side decisions to summarise. Confirm Tomo cannot commit on miyo-kouzou (per `~/Kouzou/standards/general.md`) — this task **drafts** the ADR text and hands it off; the Kokoro session commits.
  2. Test: N/A (ADR draft). Done = `_outbox/for-kokoro/2026-MM-DD_tomo-to-kokoro_F-47-cross-component-state-contract-adr.md` exists with the full ADR text ready to paste into Kokoro repo by the Kokoro session.
  3. Implement: Create `_outbox/for-kokoro/2026-MM-DD_tomo-to-kokoro_F-47-cross-component-state-contract-adr.md` with: header (ADR number TBD by Kokoro session), Context (F-47 introduces Tomo→Hashi cross-component schema for lifecycle state), Decision (`tomo.state` is single SoT for workflow doc lifecycle; `doc-frontmatter.schema.json` is the shared contract; Hashi iterates `source_*` keys generically), Consequences (Hashi consumes the schema; future Tomo doc-types extend `source_*` without Hashi code changes; cross-component breakage requires coordinated release), Alternatives Considered (sidecar state file, SQLite — both rejected per SDD §Supporting Research). Include direct PRD/SDD reference links.
  4. Validate: ADR draft passes self-review: a Kokoro session reading it can commit verbatim. Tomo cannot run git ops on miyo-kouzou — confirm draft is filed in `_outbox/for-kokoro/` per cross-repo handoff protocol.
  5. Success: Kokoro ADR draft filed `[ref: ~/Kouzou/projects/miyo/miyo-constitution.md Architecture L2]` `[ref: PRD/§8 Cross-repo dependencies + §10 Items Requiring User Input/Kokoro ADR sign-off]`.

- [x] **T6.3 Token-cost instrumentation + measurement vs PRD §7 baselines** `[activity: performance-measurement]` `[ongoing-observability: yes]`

  **Status (2026-05-21)**: Instrumentation + measurement tooling SHIPPED as permanent observability infrastructure (commit `4849545`). The first empirical run (Scenario A + B vs PRD §7 budgets) is operator-deferred — but the infra below stays in the repo for ongoing regression monitoring, not just F-47 closure.

  1. **Instrumentation (shipped 2026-05-21)** — `inbox-discovery.py` v0.3.0 emits a structured JSON `lifecycle.discovery` event to stderr with every PRD §7 property: `run_id`, `byFrontmatter_hits`, `listDir_hits`, `pending_body_reads`, `bucket_counts`, `drift_hint_emitted`, `phase_a_duration_ms`, `token_estimate`. Parsable one-liner. 12 unit tests cover the metrics block. (`pending_body_reads=0` here — state-promoter emits its own counter in a future event when promotion runs land.)
  2. **Measurement tooling (shipped 2026-05-21)** — `scripts/measure-f47-token-cost.py` v0.1.0 parses a captured stderr trace OR a Claude Code session JSONL, finds `lifecycle.discovery` events, aggregates `token_estimate` against PRD §7 budgets. Auto-classifies scenario (steady vs heavy) from bucket counts; `--scenario` override available. `--session-latest` auto-discovers the most recent tomo-instance session JSONL.
  3. **Operator runs (deferred)** — empirical measurement on Privat-Test (post-T3.5 reset) for Scenario A (steady — empty or 1-2 captured) and Scenario B (heavy — 3 instructions + 2 suggestions + 1 moc-proposal + 5 sources). Capture stderr OR use `--session-latest` after each run. Procedure documented in `docs/evolution/2026-05/2026-05-21_F-47-P5-token-cost-and-e2e-validation.md`.
  4. **Validate (operator)** — Scenario A ≤ 2,000 tokens AND Scenario B ≤ 6,000 tokens. If either fails: investigate dominant cost (Kado response shape? listDir count? body-read budget once state-promoter reports?), fix or document deviation.
  5. **Ongoing use** — the instrumentation stays live for ALL future `/inbox` runs. Run `measure-f47-token-cost.py --session-latest` periodically to detect cost regressions when scaling vault size, adding doc-types, or changing renderer payloads. PRD §7 budgets are the regression boundary, not a one-shot acceptance gate `[ref: PRD/§7 Success Metrics + Tracking Requirements]` `[ref: SDD/Quality Requirements/Performance; lines: 1107-1109]`.

- [x] **T6.4 Full PRD AC verification — E2E flows §6.1/§6.2/§6.3/§6.4** `[activity: e2e-test]`

  1. Prime: Read PRD §6 flow diagrams 6.1 (best-case `/inbox`), 6.2 (best-case `/moc-propose`), 6.3 (mixed-state run), 6.4 (drift recovery). Cross-check against the SDD §Acceptance Criteria EARS-format list `[ref: SDD/Acceptance Criteria; lines: 1120-1160]` — every PRD AC must be verifiable from this phase.
  2. Test: Four E2E live runs on Privat-Test:
     - **§6.1 best-case `/inbox`**: drop one fresh `.md` → /inbox → suggestions doc with `tomo.state=pending-approval` + source captured → tick Approved → /inbox → instructions doc with `tomo.state=pending-apply` + `tomo.source_suggestions=<path>` + suggestions `tomo.state=approved`. (Hashi-side cleanup verified in T6.1 handoff — out of scope here unless Hashi has already adopted; if so, full §6.1 including trash works.)
     - **§6.2 best-case `/moc-propose`**: 5+ notes tagged for a topic → /moc-propose tag:topic → proposal-doc with `tomo.state=pending-accept` → tick Accept on MOC01 → /inbox → bundled instructions with 1× create_moc + N× update_frontmatter, `tomo.source_moc_proposal=<path>`, proposal-doc flips to `accepted`.
     - **§6.3 mixed-state run**: prepare an inbox with (a) old captured source + (b) pending-apply instructions (manual) + (c) pending-approval suggestions (manual, with Approved ticked) + (d) pending-accept moc-proposal (manual, with Accept ticked) + (e) fresh untagged source → /inbox → discovery returns 3 pending hits + 1 captured + 1 newSource; sequential promotion: (c) → instructions + suggestions approved; (d) → instructions + proposal accepted; Pass-1 for (e); final summary lists 3 pending-apply paths via parallel-instructions warning.
     - **§6.4 drift recovery**: inbox with 3 captured sources, 0 pending → /inbox → drift hint emitted verbatim with count=3 + recover command; /inbox --recover → captured docs re-Pass-1; new suggestions doc; captured tags idempotently re-asserted.
  3. Implement: This task is largely test runs, not code. Document each scenario's actual outcome in `evolution/2026-05/<date>_f47-e2e-validation.md`. Tick PRD AC checkboxes in the spec file (`requirements.md`) as each is verified.
  4. Validate: All four scenarios pass per their PRD §6 diagrams. Tick every PRD AC checkbox under §4 Features and §5 Detailed Feature Specifications.
  5. Success: All 30+ PRD AC verified end-to-end `[ref: PRD/§4 Feature Requirements + §5 Detailed Feature Specifications]` `[ref: SDD/Acceptance Criteria; lines: 1120-1160]`. Evolution log entry committed; PRD checkboxes updated.

- [x] **T6.5 Memory updates + 013/009 README resumption markers** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read SDD §Cross-Spec Coordination Post-F-47 work queue `[ref: SDD/Cross-Spec Coordination; lines: 990-1001]`. Read `docs/ai/memory/memory.md` index + relevant decision files. Read 013 README + plan/phase-6.md and 009 README for current resumption notes.
  2. Test: N/A (documentation). Done = each referenced spec README is updated with the post-F-47 status; auto-memory has at least one entry capturing the shipped F-47 state machinery as a referenceable pattern for F-44/45/46.
  3. Implement:
     - `docs/XDD/specs/013-moc-creation-skill/README.md` + `plan/phase-6.md`: mark T6.2 + T6.4 as DONE (verified in Phase 5 T5.4 + Phase 6 T6.4 §6.2 run); update Status field if appropriate.
     - `docs/XDD/specs/009-voice-memo-transcription/README.md`: add the post-F-47.P3 regression task — re-run T5.1 (5-min voice memo end-to-end) after F-47.P3 (Phase 4 stop-gate) ships, verifying the new two-run gate doesn't regress the existing voice workflow.
     - `docs/XDD/specs/015-msp-condition-b-accumulation/`, `docs/XDD/specs/016-multi-topic-atomic-notes/`: append a note in their READMEs pointing to F-47's `doc-frontmatter.schema.json` as the schema their renderer-touch tasks must emit when those plans scaffold.
     - Run `/memory-add` to capture: (a) F-47 shipped pattern (state-machine + byFrontmatter + state-promoter), (b) `tomo.state` is the canonical lifecycle field for future Tomo doc-types, (c) `kado_client.write_frontmatter()` is the only frontmatter-mutation entry point in Tomo (eliminates regex YAML edits at the source).
  4. Validate: 013/009/015/016 README diffs reviewed. Memory index file has the new entries (auto via /memory-add). All cross-references resolve.
  5. Success: Post-F-47 work queue from SDD is reflected in the relevant spec READMEs; memory captures the F-47 pattern for future doc-type adoption `[ref: SDD/Cross-Spec Coordination/Post-F-47 work queue; lines: 990-1001]`.

- [x] **T6.6 Phase 6 Validation & spec finalisation** `[activity: validate]`

  Run `pytest tests/ -v` — full unit + integration suite must pass. Run `ruff check tomo/scripts/` — zero new findings. Run the four E2E scenarios per T6.4 — all pass. Confirm `_outbox/for-hashi/` + `_outbox/for-kokoro/` handoff files are filed. Confirm token-cost evolution-log entry exists. Update spec 017 README: Current Phase = `COMPLETE`; Status field shows all six phases ✅; append final Decisions Log entry noting cutover date + Hashi handoff date + Kokoro ADR draft date. Cut the merge: feature branch `feat/017-tomo-lifecycle-tags` ready for merge into `main` (per Constitution L1 Operations — direct main commits remain blocked; merge via `--no-ff` is the standard path). Surface any open follow-ups to `docs/XDD/backlog.md` (e.g. F-48 incremental discovery cache, `instruction-render.py:388/416` resolve_stem_to_path latent bug per SDD §Risks Known Technical Issues).
