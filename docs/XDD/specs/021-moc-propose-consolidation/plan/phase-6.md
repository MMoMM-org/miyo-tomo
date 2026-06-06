---
title: "Phase 6: Scan output-quality cleanup (notes-only default, bounded link-first, MOC-uplink check, X/ exclude)"
status: pending
version: "1.0"
phase: 6
---

# Phase 6: Scan output-quality cleanup

## Phase Context

**GATE**: Read before starting.

**Specification References**:
- `[ref: SDD/ADR-12]` — notes-only default; bounded link-first output; `check:` MOC-uplink mode; X/ exclude via config; up_parse untouched
- `[ref: PRD/Feature 7]`
- `[ref: SDD/ADR-7]` — the case-(a) orphan pass this phase shapes; `[ref: SDD/ADR-11]` — scan candidate model (unchanged)

**Key Decisions** (ADR-12, user-confirmed 2026-06-06):
- Default scan orphan pass = `kind=="note"` only (drops the 45 noise MOCs); `emit_orphan_suggestions(entries, *, kinds=("note",))` stays pure.
- Output ordered `link_existing` before `create_new` (link_existing by top-candidate score DESC), then capped at `tomo.moc_proposal.orphan_display_cap` (default 50) in the pipeline; report carries `orphan_total` + `orphan_overflow`; reducer renders an overflow footer.
- `/moc-propose check:moc-uplinks` → `--check-moc-uplinks`: orphan pass over `kinds=("moc",)` only, clustering pipeline skipped.
- `X/` excluded via `tomo.moc_structure_cache.exclude_paths` (config, not script — `lib/moc_scan` already honors it).
- `lib/up_parse` / up_state resolution NOT modified (the 206 note-orphans verified real, not a defect).

**Why this phase** (post-live-validation, 2026-06-06): a plain scan emitted 251 orphan suggestions — 45 noise MOCs (17 `X/` template-vault, 17 Efforts, 6 root maps) + a 206-note flood. The pass at `moc-discovery.py:1682` iterates every `up_state=="absent"` entry (notes AND MOCs) uncapped. Shape the output; the underlying orphan detection is correct.

**Dependencies**: Phases 1–5 (cache carries `kind`-tagged entries with `up_state`/`topics`; `lib/orphan_link` + `emit_orphan_suggestions` exist; `tomo.moc_proposal` config block holds `candidate_cap`).

---

## Tasks

- [ ] **T6.1 Config: exclude `X/` template-vault** `[activity: config]` `[ref: SDD/ADR-12; PRD/F7 AC5; lib/moc_scan.py:59 scan, :142 _discover_moc_paths]`
  1. Prime: `lib/moc_scan.py` exclude application (`_is_excluded` `:133`, exclude wins over tag); current `tomo.moc_structure_cache.exclude_paths` in `tomo-instance/config/vault-config.yaml` (`X/900 Support/930 Templater/` + `Calendar/301 Daily/ `).
  2. Implement: in the instance config, replace the narrow `X/900 Support/930 Templater/` with `X/` (whole template-vault); keep `Calendar/301 Daily/ ` (trailing space). `X/` is Marcus-vault-specific → stays in the (gitignored) instance config.
  3. Config (committed): document the `exclude_paths` pattern with a comment in `tomo/config/vault-example.yaml` (the mechanism, not the `X/` value).
  4. Validate: rebuild the cache (host→Kado), `grep -c "path: X/" tomo-instance/config/moc-structure-cache.yaml` → 0.
  5. WHY → no runtime-script change; note in `docs/tomo/` config rationale that X/ exclusion is config-driven (exclude-wins-over-tag mechanism).
  6. Success: 0 `X/…` entries in the rebuilt cache `[ref: PRD/F7 AC5]`.

- [ ] **T6.2 `orphan_link`: kind-filter + link-first sort** `[activity: backend-api]` `[parallel: true]` `[ref: SDD/ADR-12; PRD/F7 AC1, AC3; lib/orphan_link.py:154 emit_orphan_suggestions]`
  1. Prime: `lib/orphan_link.py` — `emit_orphan_suggestions` (`:154`, iterates all `up_state=="absent"`), `_score_against_mocs` (`:105`), `OrphanLinkSuggestion` (`:51`), `LINK_THRESHOLD`/`TOP_N`. Tests: `tests/test_orphan_link.py` (`_entry`/`_moc` dict fixtures).
  2. Test (RED) — `tests/test_orphan_link.py`:
     - default `emit_orphan_suggestions(entries)` excludes `kind=="moc"` orphans (only notes returned).
     - `kinds=("moc",)` returns only MOC orphans; `kinds=("note","moc")` returns both.
     - ordering: a `create_new` note and a `link_existing` note → link_existing first; two link_existing → higher top-candidate score first.
     - update existing tests that assumed MOCs were included by default (they must pass `kinds=("note","moc")` or assert the new default).
  3. Implement: add `kinds=("note",)` keyword-only param; filter orphans by `entry.get("kind") in kinds`; after building suggestions, stable-sort: `link_existing` (key = -max(candidate score)) before `create_new`. Keep scoring/threshold untouched. Bump `# version:` 0.1.0 → 0.2.0.
  4. Validate: `./venv/bin/python -m pytest tests/test_orphan_link.py -v`; `ruff check`.
  5. WHY → update `docs/tomo/scripts/lib/orphan_link.md` (kind-filter default + ordering rationale; cap lives in caller, not here).
  6. Success: notes-only default + link-first order `[ref: PRD/F7 AC1, AC3]`.

- [ ] **T6.3 `moc-discovery`: cap + overflow + `--check-moc-uplinks`** `[activity: backend-api]` `[ref: SDD/ADR-12; PRD/F7 AC1-2, AC4; moc-discovery.py:200 argparse, :1682 orphan call, :1705 report]`
  1. Prime: argparse block (`:132`–`:243`, `--candidate-cap` pattern `:200`), orphan call site (`:1682`), report assembly (`:1705` `orphan_suggestions`), `tomo.moc_proposal` config read (where `candidate_cap` is resolved). Confirm how `check:` reaches the script (agent maps prefix → flag — see T6.5).
  2. Test (RED) — moc-discovery test suite:
     - default run: orphan call uses `kinds=("note",)`; report `orphan_suggestions` truncated to `orphan_display_cap`; `orphan_total`/`orphan_overflow` correct (e.g. 60 orphans, cap 50 → 50 shown, overflow 10).
     - `--check-moc-uplinks`: orphan pass over `kinds=("moc",)`; clustering pipeline (Phase 1–6) NOT run (spy asserts no `phase1_select_candidates`/cluster call); report contains MOC-uplink suggestions.
     - cap config: `orphan_display_cap` read from `tomo.moc_proposal` (default 50), overridable.
  3. Implement: pass `kinds` to `emit_orphan_suggestions` per mode; resolve `orphan_display_cap` (default 50) from `tomo.moc_proposal`; after the (already-sorted) pass, truncate + set `orphan_total`/`orphan_overflow` in the report. Add `--check-moc-uplinks` (`store_true`, modeled on `--candidate-cap`); when set, short-circuit to the MOC-kind orphan pass + report, skipping clustering. Bump `# version:`.
  4. Config: add `orphan_display_cap: 50` under `tomo.moc_proposal` in `tomo/config/vault-example.yaml` (+ instance); document.
  5. Validate: targeted pytest + full suite (only 8 pre-existing ide_bridge); `ruff check`.
  6. WHY → `docs/tomo/scripts/moc-discovery.md`: cap/overflow + check-mode (clustering-skip) rationale.
  7. Success: notes-only capped default `[ref: F7 AC1-2]`; check-mode over MOCs, no clustering `[ref: F7 AC4]`.

- [ ] **T6.4 `suggestions-reducer`: overflow footer + MOC-uplink section** `[activity: backend-api]` `[ref: SDD/ADR-12; PRD/F7 AC2, AC4; suggestions-reducer.py orphan renderer]`
  1. Prime: the `## Orphan Notes & MOCs` renderer in `suggestions-reducer.py` (consumes `report.orphan_suggestions`); how `--moc-proposal-mode` selects sections.
  2. Test (RED) — reducer test: with `orphan_overflow > 0`, rendered doc contains the overflow footer (count + "re-run with a scoped query"); with `orphan_overflow == 0`, footer absent. Check-mode report renders under a distinct MOC-uplink heading.
  3. Implement: read `orphan_overflow`/`orphan_total` from the report; emit the footer past the cap; render the MOC-uplink report under a clear heading when the report is check-mode. Bump `# version:`.
  4. Validate: reducer pytest; `ruff check`.
  5. WHY → `docs/tomo/scripts/suggestions-reducer.md`: overflow-footer + MOC-uplink section.
  6. Success: footer past cap, absent under cap `[ref: F7 AC2]`; MOC-uplink section in check-mode `[ref: F7 AC4]`.

- [ ] **T6.5 Agent + command cleanup** `[activity: docs]` `[ref: SDD/ADR-12; PRD/F7 AC4; CLAUDE.md lean-runtime rule]`
  1. Prime: `tomo/dot_claude/commands/moc-propose.md` (`0.2.4`, "Why impersonate" prose `:19`–`:26`), `tomo/dot_claude/agents/moc-architect.md` (`0.6.0`, Step 2→4 gap, mode whitelist `:45`, Step 4a table `:95`), `docs/tomo/dot_claude/{commands,agents}/` counterparts.
  2. WHY-first: capture every rationale being stripped (impersonate reasoning, refactor history) into the `docs/tomo/` counterparts BEFORE removing it from runtime (CLAUDE.md: strip-first destroys institutional knowledge).
  3. Command (`moc-propose.md` 0.2.4 → 0.3.0): replace the 7-line "Why impersonate" block with a one-line pointer to docs/tomo; add `check:moc-uplinks` to Usage + the Routing Rule (new whitelisted `check:` prefix). Manual lean-pass (imperatives only).
  4. Agent (`moc-architect.md` 0.6.0 → 0.7.0): renumber Steps to be contiguous (close the Step 2→4 gap); add `check:` to the Step 1 mode whitelist and a `check` row to the Step 4a invocation table (`--check-moc-uplinks`); route check-mode to skip Pass-1/topic-extraction. Then run the **agent-author audit** (`tcs-helper:agent-author`) and apply its lean findings.
  5. Validate: `update-tomo.sh --yolo` syncs both; spot-check the instance copies reflect the new versions.
  6. Success: lean runtime files, WHYs in docs/tomo, `check:` documented + routed `[ref: PRD/F7 AC4]`.

- [ ] **T6.6 Phase 6 validation + sync + finalize** `[activity: validate]`
  - Bump `# version:` on every edited managed file (orphan_link, moc-discovery, suggestions-reducer, moc-architect, moc-propose). `./scripts/update-tomo.sh --yolo` (also picks up checkpoint-pending moc-discovery 0.13.0 + kado-write-file 0.2.0). Full `./venv/bin/python -m pytest -q` (only 8 pre-existing ide_bridge failures allowed) + `ruff check`.
  - Live (host→Kado): rebuild cache → 0 `X/`; dump `emit_orphan_suggestions(entries)` ≤ 50, all `kind=="note"`, link_existing first; run `/moc-propose` (default) → bounded notes-only doc with overflow footer, no X/ or root MOCs; run `/moc-propose check:moc-uplinks` → focused MOC-uplink report.
  - Refresh `LIVE-VALIDATION-RUNBOOK.md` (M1–M9 + the F7 checks) → `Skill(tcs-workflow:xdd-meta)` `finalize 021-moc-propose-consolidation`.
