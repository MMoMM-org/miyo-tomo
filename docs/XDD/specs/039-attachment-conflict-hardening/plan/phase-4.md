---
title: "Phase 4: The attachment plan"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: The attachment plan

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-1]` — one plan, before the render loop
- `[ref: SDD/ADR-3]` — the census and its run adjustment
- `[ref: SDD/ADR-7, ADR-8, ADR-9]`
- `[ref: SDD/Runtime View; Decision table (K1)]` — rows 1–11, first match wins
- `[ref: SDD/Implementation Examples; the plan for one source]`
- `[ref: PRD/Detailed Feature Specifications; F3 + F4, Rules 1–7, Edge Cases]`
- `[ref: research.md/R1 §1–§3, R3 §1–§5]`

**Key Decisions**:
- K1 is the **only** place an attachment's fate is decided. After T4.3/T4.4, `_build_move_asset_actions` and the embed rewrite contain no decision logic of their own (grep for `check_typed_name`, `remedy ==`, `claimed` in them → only K1).
- Owners are collected in full, not first-only (`render_actions.py:820-829` today) — T5.2 depends on it.
- The census subtracts every inbox source this run moves; forgetting it makes every attachment ambiguous.
- `ignore` skips the occupancy row only — a run collision still withholds it (PRD Rule 4).
- K1 is built in two passes: outcomes for every source first, embeds second (SDD Decision table).
- Every existing harness keeps its assertions. The ~43 old-signature call sites in ~25 test files migrate through a `plan_from_remedies(...)` test helper; "no expectation changed" means no **assertion** changed.
- Every new module starts with a `# version:` header and a why-docstring, and its `docs/tomo/scripts/lib/*.md` WHY file is written in the same task.

**Dependencies**: Phases 1–3.

---

## Tasks

Delivers the single decision site and rewires both of today's decision sites to read it.

- [ ] **T4.1 Basename census `lib/basename_census.py`** `[activity: integration]` `[parallel: true]`

  1. Prime: `kado_client.py:283-311, 601-637`; `render_resolve.py:599-614` (the pattern to copy); Kado `search-adapter.ts:408-415` (substring, all file types) `[ref: SDD/ADR-3; SDD/Interface Specifications K3]`
  2. Test: `count("photo.png")` ignores `old-photo.png` (substring hit); case-folded equality (`Karte.PNG` counts for `karte.png`); one search per distinct case-folded basename however often asked; a Kado error → `None`, and not cached as 0; a third page requested → stop, `None` (page budget); `searches` and `pages` counters
  3. Implement: `make_basename_census(client)` closure or small class
  4. Validate: counting fake; ruff clean
  5. Success: `[ref: PRD/F3-AC7]` (name-search bound and page budget); input to F4

- [ ] **T4.2 The plan `lib/attachment_plan.py`** `[activity: domain-modeling]`

  1. Prime: everything in Phase Context; `_build_move_asset_actions` `render_actions.py:723-970` in full — every branch there becomes a row here `[ref: SDD/ADR-1; SDD/Decision table]`
  2. Test: table-driven against fake K2/K3, one test per decision-table row with an accepting and a rejecting variant; plus: two Ignores onto one target → the second `collision` (Rule 4); a default folder with a trailing `/` refused `trailing_separator` on both paths; a folder equal to `concepts.asset` but owner-supplied → treated as default; a source withheld late in Pass A is not counted in Pass B; null folder and folder == `dirname(destination)` → `concepts.asset` from Pass 2 config (F1-AC5); folder under Keep/Ignore ignored (F1-AC6); original name in a new folder accepted (F1-AC10); empty name + typed folder → `blank` (F1-AC11); typed folder refused → no fallback target (F2-AC6); a bad folder in one source leaves the others planned (F2-AC7); K2 `absent` → move + `folder_created` (F2-AC8); non-conflict attachment onto a now-occupied target → `vault_occupied` (F3-AC2); Ignore onto occupied → move (F3-AC4); K2 `unanswered` → move + `unchecked` (F3-AC6); census: unique → bare when renamed / untouched when not (F4-AC1), others ≥ 1 incl. occupier or another in-run target → full path (F4-AC2), unrenamed default-folder ambiguous → full path (F4-AC3), inbox copy and other moved inbox sources not counted (F4-AC4), `None` → full path (F4-AC6); two sources → same target: second `collision`; case-only occupier → occupied; owners complete for a shared attachment
  3. Implement: `AttachmentDecision`, `AttachmentPlan`, `build_attachment_plan(...)` per SDD K1 (two passes); `plan_from_remedies(...)` test helper. Carried from Phase 3: call `check_typed_folder` with the vault-relative inbox path (`concepts.inbox`, e.g. `100 Inbox/`) or `inside_inbox` never matches; the parser hands over `""` owner-supplied for an empty, malformed (no or broken backticks) or self-contradicting duplicate folder line — K1 must refuse it (`blank`), never fall back to the default folder
  4. Validate: every row has both polarities; mutation check — delete the census subtraction and watch F4-AC4's test fail; ruff clean
  5. Success: `[ref: PRD/F1-AC3, AC5, AC6, AC10, AC11]` `[ref: PRD/F2-AC4, AC6, AC7, AC8]` `[ref: PRD/F3-AC1, AC2, AC4, AC6]` `[ref: PRD/F4-AC1, AC2, AC4, AC6]`

- [ ] **T4.3 The move builder becomes a projection of the plan** `[activity: backend]`

  1. Prime: `render_actions.py:723-970, 1494-1531, 1534-1637, 2786-2877`; `instruction-render.py:643-651` `[ref: SDD/ADR-1, ADR-7; SDD/Interface Specifications K5]`
  2. Test: `_build_move_asset_actions(manifest, plan)` emits one `move_asset` per planned move whose owners include a rendered manifest item, in today's order and id sequence; returns `skipped_assets` for withheld decisions with the new kinds and `owner_source_items`; returns `move_ids_by_origin` with **every** owner; `suppress_moves_for_unfiled_attachments` holds the notes for `typed_folder_refused` and `vault_occupied` and still not for `vault_collision_held`; `_attachment_suppression_reason` gives each new kind its own sentence (no "correct that inbox path" for them); the full 036/037/038 suite green with **no assertion changed** (F1-AC7, F3-AC3)
  3. Implement: projection; `build_actions(..., attachment_plan=plan)`; remove the decision branches from the builder; `instruction-render.py` builds the plan (with K2 and a census) at the `build_actions` call so the suite stays green — T4.5 moves the build before the loop; migrate harnesses via `plan_from_remedies`
  4. Validate: grep — no `check_typed_name` / `remedy ==` / `claimed` left in the builder; golden comparison on the 038 baseline byte-identical
  5. Success: `[ref: PRD/F3-AC1]` (emission side) `[ref: PRD/F3-AC3]` `[ref: PRD/F1-AC7]` `[ref: PRD/F2-AC4]`

- [ ] **T4.4 Embed rewrite reads the plan** `[activity: backend]`

  1. Prime: `embed_rewrite.py` (0.4.2) in full; `attachment_index.py:13, 148-171` `[ref: SDD/ADR-9]`
  2. Test: renamed + unique → bare new name (today's output, F4-AC1); unrenamed + unique → body untouched; ambiguous → `![[<full path>]]` in **every** owning note (F4-AC2, F4-AC3); suffixes `|300`, `|alias`, `#heading` kept and extension kept, no alias added (F4-AC5); a written `![[Other/name.png]]` pointing elsewhere is **not** rewritten (R1 §3 measured defect); a withheld source rewrites nothing — run-level `collision` included (F4-AC8, closes backlog `:1956`); fenced code and non-`!` links untouched (existing tests); original name into a new folder rewrites to the qualified path when ambiguous (F1-AC10)
  3. Implement: `rewrite_attachment_embeds(body, attachments, plan)`; drop the duplicated `check_typed_name` call (closes backlog `:1917` for this site); the render-loop call site switches to the plan in this task (T4.5 only relocates the build)
  4. Validate: 037/038 embed tests green or deliberately retargeted with a stated reason; ruff clean
  5. Success: `[ref: PRD/F4-AC1, AC2, AC3, AC5, AC8]` `[ref: PRD/F1-AC10]`

- [ ] **T4.5 Wire the plan into Pass 2** `[activity: backend]`

  1. Prime: `instruction-render.py:380-760, 850-924` `[ref: SDD/Runtime View; SDD/Cost]`
  2. Test: integration through `main()` (call it the way production does — all optional args as production passes them): plan built once after remedies load and before the first render; goldens use a census fake that answers "unique" so byte-identity holds; `validate_destinations` receives a view of the **same** K2 instance (one `list_dir` per folder across asset and note guards, counting fake); a run with no attachment makes zero census and zero extra listing calls (F3-AC7); a bad typed folder refuses one item and the run exits 0 with the rest produced (F2-AC7) — and never reaches `_check_path_shape`; a Pass 2 `cost_history` entry carries `folder_listing_calls`, `basename_searches` and `basename_pages` when `--cost-history` is given, mirroring the reducer (`suggestions-reducer.py:2869, 2907`) (C1-AC1); garden-audit and daily-only runs (`client` None) unaffected
  3. Implement: build K2/K3/K1 after `:457`; pass plan to the loop and `build_actions`; counters; pass the shared lookup's `notes` view to `validate_destinations` instead of a client (drops the `isinstance` path in `make_folder_listing`), and memoise the per-folder map inside `validate_destinations` — T1.4 review measured ~4.7 ms per rebuild for a 3000-note folder; switch `suggestions-reducer.py:2365` and the docstrings at `:526`, `:562` to the public `VaultFolderLookup` name, keeping `_VaultFolderLookup` only for the 037 tests
  4. Validate: full suite green; ruff clean
  5. Success: `[ref: PRD/F3-AC7]` `[ref: PRD/F2-AC7]` `[ref: PRD/C1-AC1]`

- [ ] **T4.6 Phase 4 validation** `[activity: validate]`

  - Full suite green in one invocation; ruff clean; golden byte-identity on the 038 baseline; grep proof that K1 is the only decision site; backlog `:1917` and `:1956` updated with SHAs.
  - Carried from Phase 3: `test_038_t4_4_the_two_paths_converge.py`'s `_strip_provenance` maps a non-owner-supplied `proposed_dir` to `None` (the markdown spells the untouched default as the rendered folder, the wire as `null`); back it with a destination-level assertion — both paths produce the same `move_asset` destination for: untouched default, typed folder, default + trailing `/` (refused on both), typed folder equal to `concepts.asset`. `test_039_t3_4_folder_not_consumed_yet.py` asserts the folder is ignored; retarget it to the real folder outcome here.
