---
title: "Phase 5: Docs sweep + finalize"
status: pending
version: "1.0"
phase: 5
---

# Phase 5: Docs sweep + finalize

## Phase Context

**GATE**: Read before starting.
- `[ref: requirements.md/Should Have Features]` — documentation sweep
- `[ref: solution.md/Component → directory mapping]` — docs + vault-example.yaml
- Docs touched by this spec: `docs/installation.md`, `docs/setup.md` (step 4 + add multi-instance + registry + update-check), `docs/usage.md` (lifecycle namespace), `docs/configuration.md` (tomo-install.json schema: drop `lifecyclePrefix`, add `repoPath`; registry), `docs/troubleshooting.md` (`#MiYo-Tomo/captured` refs), `docs/README.md` (nav)
- `tomo/config/vault-example.yaml` (`tag_prefix`)

**Key Decisions:** all ADRs (this phase makes the docs match the shipped behaviour).

**Dependencies:** Phases 1–4 (behaviour final before documenting).

---

## Tasks

Aligns user-facing docs + the example config with the shipped multi-instance + frontmatter-lifecycle reality, then closes the spec.

- [ ] **T5.1 Document multi-instance install + registry + update-check** `[activity: documentation]`
  1. Prime: final install/update/launcher behaviour `[ref: solution.md/Key Flows]`.
  2. Implement: update `installation.md` + `setup.md` for the per-instance layout (`<parent>/<name>/{begin-tomo.sh, tomo-install.json, instance/, home/}`), default parent `~/MiYo/Tomo/`, the create-new vs update-`<name>` flow, the `~/.tomo/instances.json` registry, and the launcher update-availability prompt; `configuration.md` for the `tomo-install.json` delta (`repoPath` in, `lifecyclePrefix` out) + registry; `README.md` nav.
  3. Validate: cross-links resolve; `bash`/code fences correct.
  4. Success: a reader can stand up a second instance from the docs `[ref: PRD/Should]`.

- [ ] **T5.2 Remove lifecycle-tag references from docs + example config** `[activity: documentation]` `[parallel: true]`
  1. Prime: ADR-6 `[ref: solution.md/ADR-6]`.
  2. Implement: drop the tag-prefix step from `setup.md` step 4; remove `#MiYo-Tomo/captured` lifecycle-tag references from `troubleshooting.md` + `usage.md` (lifecycle namespace) and reframe around `tomo.state` frontmatter; remove `tag_prefix` from `vault-example.yaml`.
  3. Validate: `rg '#MiYo-Tomo/|tag_prefix|lifecyclePrefix'` over `docs/` + `tomo/config/` returns only intentional/historical mentions.
  4. Success: docs reflect the frontmatter lifecycle model `[ref: PRD/F6, Should]`.

- [ ] **T5.3 Final validation + version-bump audit** `[activity: validate]`
  1. Verify every edited managed file got a `# version:` bump (install-tomo.sh, update-tomo.sh, begin-tomo.sh.template, tomo-statusline.sh, vault-example.yaml, + any configure-*.sh touched).
  2. Run full `python3 -m pytest tests/ -q`; `bash -n` on all edited shell; `ruff check` on changed/new python.
  3. Success: full suite green; bash 3.2 clean; ruff clean `[ref: PRD/Success Metrics]`.

- [ ] **T5.4 Two-instance live smoke (operator)** `[activity: validate]`
  1. Operator-run: create instance "A" at `~/MiYo/Tomo/A`, then "B"; confirm both launch, each shows its own name in-container + Hashi, registry lists both, A's files unchanged after creating B; trigger the update-check by bumping repo version.
  2. Success: real two-instance flow works end-to-end `[ref: PRD/Success Metrics]`. (Manual — operator-gated, like prior live tests.)

- [ ] **T5.5 Spec close-out** `[activity: validate]`
  - Update spec README to Implemented; log shipping notes (PR, version bumps); update backlog (close D-09; note D-10 docs-refresh adjacency). Finalize via xdd-meta.
