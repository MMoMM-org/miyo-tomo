---
title: "Phase 1: Preconditions, no behaviour change"
status: in_progress
version: "1.0"
phase: 1
---

# Phase 1: Preconditions, no behaviour change

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Constraints; CON-1, CON-2]` — release order, Kokoro first
- `[ref: SDD/ADR-2]` — the shared folder lookup
- `[ref: SDD/ADR-6]` — the renderer stops defaulting to "blank"
- `[ref: SDD/Implementation Gotchas]` — vendored copy 2 → 3 first
- `[ref: research.md/R1 §1, R2 §1, R4 §2 and §6]`

**Key Decisions**:
- Every task here leaves Pass 1 and Pass 2 output byte-identical. The full suite must be green after each task with **no** test expectation changed except the vendored-copy delta in T1.3.
- The two handoffs are written now because both are owed before code that depends on them: Kokoro before any C1 change (CON-2), Hashi because three of its asks are already decided (accept, release vehicle, §4 rule) and its #141 is waiting.

**Dependencies**: none.

---

## Tasks

Clears the ground: the owed handoffs go out, the stale vendored schema is corrected, the shared folder lookup exists, and two latent defects that the new reasons would trigger are closed first.

- [ ] **T1.1 Kokoro design-time handoff for #186** `[activity: technical-writing]` `[parallel: true]`

  1. Prime: Kokoro `ADR-029-…:77-81, 136-152`; `_outbox/for-kokoro/2026-10-11_…adrs-read-two-push-backs…:138-172` (what we promised); PRD Problem 4; SDD ADR-10 `[ref: SDD/ADR-10]`
  2. Test: n/a (document). Checklist instead: names C1 (values + description), C3, C4, C10; states option 1 and the owner ruling; states how the owner is now told about the note (F6-AC8 wording); carries both near-miss runs (`I05 depends_on [I01]`); says Hashi needs no change and why; documents the suggestions wire's v3 → v4 migration path (L2 Architecture); states the gate — no merge before Kokoro answers, a rejection reverts T5.2
  3. Implement: `_outbox/for-kokoro/2026-10-12_tomo-to-kokoro_<slug>.md` via `/miyo-outbox`
  4. Validate: owner reads it before it is marked sent
  5. Success: handoff sent in Phase 1; T5.2 does not start before; merge waits for Kokoro's answer `[ref: PRD/CON-2]` `[ref: SDD/Constraints; CON-2]`

- [ ] **T1.2 Interim reply to Hashi's `proposed_dir` handoff** `[activity: technical-writing]` `[parallel: true]`

  1. Prime: `_inbox/from-hashi/2026-10-11_hashi-to-tomo_attachment-conflicts-need-an-editable-target-folder.md`; PRD CON-3; SDD External Interfaces
  2. Test: n/a. Checklist: §1 accepted as `string | null`, required, released as `schema_version` 4 (coordinated); §2 our measurement — the risk exists **today** (three code paths, R1 §3) and our ruling (path only when ambiguous); states that Obsidian's resolution of an ambiguous bare basename stays unmeasured (PRD A1 — neither side can probe Obsidian); §4 confirmed with file:line (`render_actions.py:849/886`, `embed_rewrite.py:136`) and `proposed_dir` follows the same rule; #185 ruling (one reason, refused not trimmed on the markdown route) and the `unsafe_sequence` ruling; F1-AC11 ruling; folder refusal classes (incl. `# ^ [ ]`) so their picker can pre-empt them; that a missing folder is allowed because their executor creates it, asking whether several missing levels are created at once if their code or the Obsidian API docs settle it (A3)
  3. Implement: `_outbox/for-hashi/2026-10-12_tomo-to-hashi_<slug>.md`; set the inbound handoff `status: done`
  4. Validate: owner reads it before it is marked sent
  5. Success: Hashi's three asks answered `[ref: PRD/CON-3]`

- [ ] **T1.3 Refresh the vendored consumer suggestions schema to v3** `[activity: integration]` `[parallel: true]`

  1. Prime: `tomo/schemas/hashi-suggestions-wire.schema.json` (const "2"); Hashi's `src/schema/suggestions-wire.schema.json` (const "3"); `tests/test_wire_snapshot_parity.py:689-760` `[ref: SDD/CON-1; research.md/R2 §1]`
  2. Test: the parity test's pinned delta between vendored and live is **empty** for v3 (it pins 6 entries today)
  3. Implement: copy Hashi's v3 file byte-identically (`cmp` against their tree); re-pin the parity test's expectation and rewrite its docstring's narrative
  4. Validate: `cmp` clean; full suite green
  5. Success: vendored copy = consumer's actual v3 `[ref: SDD/Implementation Gotchas]`

- [ ] **T1.4 Shared folder lookup `lib/vault_folder_lookup.py`** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: `suggestions-reducer.py:311-421` (`_VaultFolderLookup`) and its WHY in `docs/tomo/scripts/suggestions-reducer.md:1000-1040`; `render_actions.py:542-576` (the join helpers), `:991-1033` (`make_folder_listing`); `kado_client.py:54, 253-272, 686, 861-863` `[ref: SDD/ADR-2; SDD/Components K2, K15]`
  2. Test: `state()` returns `listed` / `absent` (KadoNotFoundError carrying Kado's `Path not found`) / `unanswered` (an endpoint 404 and any other KadoError); `assets()` keys by `_asset_dest_join`, includes non-`.md` only; one `list_dir` per folder however many views are read (counting fake); `make_folder_listing` built on it returns exactly today's map for a fixture; reducer behaviour unchanged (existing 037 tests)
  3. Implement: first move the WHY to `docs/tomo/scripts/lib/vault_folder_lookup.md` (WHY first, strip second); move `_dest_join`/`_asset_dest_join` to `lib/vault_paths.py` (K15) with re-exports from `render_actions` so K2 imports no cycle; move the class to lib (public name) with a `# version:` header and why-docstring, add `state()`, keep the `folder_listing_calls` counter name the reducer and `cost_history` read; reducer imports it; `make_folder_listing(client_or_lookup)` becomes a `.md` view over the same raw cache
  4. Validate: full suite green with no expectation changed; ruff clean
  5. Success: one raw listing per folder shared by every reader `[ref: PRD/F3-AC7]`

- [ ] **T1.5 `_typed_name_refusal_reason` no longer defaults to "blank"** `[activity: backend]` `[parallel: true]`

  1. Prime: `render_actions.py:692-720`; `backlog.md:1757` `[ref: SDD/ADR-6]`
  2. Test: an unrecognised reason code raises (`ValueError`) rather than returning the blank sentence — RED against today's fall-through; the three known codes keep their exact sentences (038 mutation table `test_038_t3_2_*:434-442`)
  3. Implement: explicit `blank` branch; raise on anything else
  4. Validate: suite green; docstring at `:706-708` corrected
  5. Success: no unknown reason can be reported as blank `[ref: PRD/F5-AC5]`

- [ ] **T1.6 Join test: every computed name passes the typed-name rules** `[activity: testing]` `[parallel: true]`

  1. Prime: `suggestions-reducer.py:521-579` (`_propose_asset_name`), `typed_name_check.py`; `backlog.md:2457` `[ref: SDD/Components K14]`
  2. Test: for a table of source basenames drawn from the PRD's input set — discoverable as attachments (no `# ^ [ ]`, no edge whitespace) and vault-legal (no `FORBIDDEN_CHARS`): spaces, umlauts, dots, `(n)` already present, no extension, multi-suffix — every non-None `_propose_asset_name` result is accepted by `check_typed_name`; the excluded classes are named in the test docstring with the existing pinned divergence `test_038_t4_4_the_two_paths_converge.py:556`; the test must survive T2.1 unchanged
  3. Implement: `tests/test_039_t1_6_computed_names_pass_typed_rules.py`
  4. Validate: prove it can fail — feed it a deliberately bad stub proposer
  5. Success: Tomo never proposes, for a discoverable vault-legal source, a name it would refuse `[ref: PRD/F5-AC6]`

- [ ] **T1.7 Phase 1 validation** `[activity: validate]`

  - Full suite green in one invocation; ruff clean; Pass 1 and Pass 2 output byte-identical on the 038 baseline fixture; both handoffs read by the owner. Backlog `:1757` and `:2457` marked resolved with commit SHAs.
