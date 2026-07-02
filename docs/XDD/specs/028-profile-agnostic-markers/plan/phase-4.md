---
title: "Phase 4: Wire-in, verify, single live-test"
status: completed
version: "1.0"
phase: 4
---

# Phase 4: Wire-in, verify, single live-test

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Integration Approach; two channels]`
- `[ref: SDD/Quality Requirements; Acceptance Criteria (EARS)]`
- `[ref: SDD/Deployment View]`

**Key Decisions**: instruction-render + moc-tree-builder resolve conventions from their existing `--config`. Exactly ONE live-test cycle (CON-3).

**Dependencies**: Phase 2 + Phase 3 complete.

---

## Tasks

Wires the two `--config` scripts into the resolver, runs full verification, and performs the single end-to-end live check.

- [x] **T4.1 instruction-render wire-in** `[activity: backend]`

  1. Prime: Read `instruction-render.py` `--config` handling (190-225) + its calls into `render_actions`.
  2. Test (RED): with `--config` pointing at a miyo test config, rendered actions match baseline; markers flow from the resolved profile.
  3. Implement (GREEN): at entry, `resolve_conventions(config_path=args.config, profiles_dir=<script SCRIPT_DIR/../profiles>)`; pass markers into the `render_actions` calls.
  4. Validate: pytest + ruff; miyo end-to-end render byte-identical.
  5. Success: [ ] render honors profile markers via `--config` `[ref: SDD/ADR-1]`

- [x] **T4.2 moc-tree-builder wire-in** `[activity: backend]` `[parallel: true]`

  1. Prime: Read `moc-tree-builder.py` `--config` handling (611-632) + `up_parse` usage.
  2. Test (RED): tree build parses relationship links using the profile's `parent_marker` via `--config`; miyo unchanged.
  3. Implement (GREEN): resolve conventions from `--config`; pass `parent_marker` into `up_parse`. Do NOT touch `FOOTER_CALLOUTS`.
  4. Validate: pytest + ruff.
  5. Success: [ ] tree build honors profile marker `[ref: SDD/ADR-1]`

- [x] **T4.3 Full offline suite + seam grep** `[activity: validate]`

  1. Run `./venv/bin/python -m pytest tests/` (whole suite, not just new tests) + `./venv/bin/ruff check tomo/scripts/`.
  2. Grep-verify **zero** hardcoded `up::` / `related::` / `" (MOC)"` literals remain in the 10 in-scope seams (defaults inside `profile_conventions.py` excepted).
  3. Success: [ ] full suite green; [ ] seam grep clean `[ref: SDD/Quality Requirements]`

- [x] **T4.4 WHY docs + version verification** `[activity: documentation]`

  1. Update `docs/tomo/scripts/*.md` WHY counterparts for changed runtime files (why the resolver, why per-script channel, ADR-2 path constraint) per repo docs rule.
  2. Confirm both profile `# version:` bumps landed (T1.2).
  3. Success: [ ] WHY docs updated; [ ] version bumps present `[ref: SDD/CON-5]`

- [x] **T4.5 SINGLE live-test cycle** `[activity: validate]`

  1. Sync instance (`update-tomo`) — verify script + profile versions landed in the instance (`[ref: reference_update_tomo_is_version_gated]`).
  2. Run ONE `/inbox` walk against Kado under the miyo profile; spot-check output matches expectations (no regressions).
  3. Spot-check lyt: MOC titles render plain (no `" (MOC)"`).
  4. Success:
     - [x] miyo live run shows no regression `[ref: PRD/Success Metrics]`
     - [x] lyt yields plain MOC titles `[ref: PRD/AC F-55]`
     - [x] This is the only live cycle consumed `[ref: SDD/CON-3]`
