# Specification: 020-multi-instance-install

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-05-31 |
| **Current Phase** | Implemented |
| **Last Updated** | 2026-06-01 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 6 Must-Have, 1 Should (doc sweep), 2 Could (top-level picker, inline auto-update), 3 Won't. Gherkin ACs incl. failure cases. 4 OQs carried to SDD. |
| solution.md | completed | 7 ADRs all confirmed 2026-05-31. Per-instance layout (instance/+home/), registry index, TOMO_INSTANCE_NAME identity, non-fatal launcher update-check, no migration, tag-prefix removal, shared render-launcher (D-09). |
| plan/ | completed | 5 phases, ~20 tasks, TDD. P1 foundation libs (registry + render-launcher); P2 install multi-instance flow; P3 update per-instance + launcher identity/update-check; P4 tag-prefix cleanup (Part B); P5 docs + finalize. Every task traced to F1–F6 + ADRs. |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-31 | Spec created | User wants multi-instance install made first-class (today the wizard assumes one instance; a 2nd install clobbers the single repo-root config, home dir, and launcher). Surfaced while installing an instance outside the repo. |
| 2026-05-31 | Fold lifecycle tag-prefix cleanup into this spec (Part B) | Both changes reshape the install wizard. Post-F-47 the `lifecycle.tag_prefix` is vestigial (state moved to `tomo.state` frontmatter); the wizard prompt, `--prefix` flag, and dead `state-scanner.py` are residual scaffolding. Cleaning them up alongside the wizard restructure avoids touching install-tomo.sh twice. |
| 2026-05-31 | XDD spec before implementation (user choice) | Architecture change to install layout + a migration concern (existing single-instance install) → trace to an approved spec per MiYo Constitution L1 before coding. |
| 2026-05-31 | Default instance parent = `~/MiYo/Tomo/` (prompted) | User choice. Instances live in user space, not the repo checkout; the trigger was installing an instance outside the repo. |
| 2026-05-31 | No legacy migration | User: the repo's `tomo-instance`/`tomo-home` is a hand-maintained test instance, not real legacy. New per-instance layout is the only supported layout; no auto-migration built. |
| 2026-05-31 | Discovery via registry file `~/.tomo/instances.json` | User choice over dir-scan. Instances can live anywhere; registry indexes name → path + source-repo path + version. Instance dirs remain source of truth for config (registry is a rebuildable index). |
| 2026-05-31 | Launcher gains an update-availability check | User addition. `begin-tomo.sh` compares the instance's installed version vs the recorded Tomo-repo version and offers to update. Non-fatal — must never block launch. |
| 2026-05-31 | PRD completed → SDD | All critical gates pass; 4 technical OQs (OQ2/OQ5/OQ7/OQ8) carried into SDD. |
| 2026-05-31 | SDD completed — 7 ADRs confirmed → PLAN | ADR-1 layout (inner dirs instance/+home/); ADR-2 registry index; ADR-3 TOMO_INSTANCE_NAME + sanitized hostname; ADR-4 non-fatal launcher update-check; ADR-5 no migration; ADR-6 tag-prefix removal + statusline byFrontmatter; ADR-7 shared render-launcher (closes D-09). |
| 2026-05-31 | PLAN completed → Ready | 5 phases, ~20 TDD tasks. Foundation-first (registry + render-launcher libs as pure testable units), then install, then update+launcher identity/check, then Part B cleanup, then docs+finalize. All tasks traced to PRD ACs + ADRs. Spec ready for /implement. |
| 2026-05-31 | Phases 1–4 implemented | P1 foundation libs (`instance-registry.sh`, `render-launcher.sh` + tests); P2 multi-instance install flow; P3 per-instance update + launcher identity (`TOMO_INSTANCE_NAME`/hostname) + non-fatal update-check; P4 Part B tag-prefix cleanup (wizard prompt + `--prefix` flag + `lifecyclePrefix` removed; `state-scanner.py` deleted; statusline repointed to `byFrontmatter tomo.state`; `/inbox` lifecycle regression guard added). |
| 2026-06-01 | Phase 5 implemented — docs sweep + finalize | **T5.1** (`96a3b4b`, `82b29e7`) documented per-instance layout, registry, update-check in installation/setup/configuration/README; **T5.2** (`4c4afe3`, `6d1dfcf`) scrubbed lifecycle tag-prefix from user docs + `vault-example.yaml` (v1.1→1.2) and reframed on `tomo.state` frontmatter; **T5.3** (`4ec8672`) final validation: all 5 changed managed files version-bumped, `bash -n` clean on bash 3.2.57, `ruff` clean, made the lifecycle regression guard hermetic. Spec-020 owns 105 passing tests; full suite 469 pass / 87 fail / 2 collection-error — **all 87+2 failures pre-existing** (`jsonschema` incompatible with Python 3.14, + `ide_bridge` bash-snippet tests), **0 spec-020 failures**. |
| 2026-06-01 | Findings logged to backlog | **D-09 closed** by ADR-7 (`render-launcher.sh`). **D-10 raised** — `cleanup-tomo.sh` (v0.1.0) is not multi-instance-aware (operates on `$REPO_ROOT/tomo-instance/`, refuses external paths); its docs left unchanged. **D-06 reinforced** — tier-2/tier-3 architecture-reference docs still describe the old `#MiYo-Tomo/<state>` tag model; deliberately left out of this spec's *user-facing* sweep. |
| 2026-06-01 | T5.4 two-instance live smoke — OPERATOR-PENDING | Operator-gated (Docker, real two-instance creation), consistent with prior MiYo live-validation handling. Implementation + automated tests complete; final real-world two-instance smoke is the one remaining manual step before the work is exercised end-to-end. |
| 2026-06-01 | Implementation complete | Phases 1-5 shipped on feat/020-multi-instance-install. Multi-instance first-class install (self-contained `<parent>/<name>/{begin-tomo.sh,tomo-install.json,instance/,home/}`, `~/.tomo/instances.json` registry, `TOMO_INSTANCE_NAME` identity, non-fatal launcher update-check) + Part B lifecycle tag-prefix removal (frontmatter `tomo.state`). Version bumps: install-tomo.sh 0.3.1→0.5.0, update-tomo.sh 0.4.2→0.6.0, begin-tomo.sh.template 0.11→0.14, tomo-statusline.sh 0.4→0.7, vault-example.yaml 1.1→1.2. 105 spec-020 tests pass; full suite 469 pass / 87 fail (all pre-existing jsonschema-on-Python-3.14 + ide_bridge bash-snippet; 0 spec-020). D-09 closed (render-launcher.sh), D-10 raised (cleanup-tomo.sh not multi-instance-aware). T5.4 two-instance live smoke operator-pending. Not yet merged/pushed. |

## Context

Add Docker-side support for managing **multiple** Tomo instances, each self-contained in its own directory, with a configurable, surfaced instance name. Fold in the removal of the now-vestigial lifecycle tag prefix (superseded by F-47 frontmatter state).

**Part A — Multi-instance first-class install:**
1. Install can create AND manage multiple instances (discover existing, create-new vs update-`<name>`).
2. Each instance is self-contained: `<parent>/<instance-name>/{begin-tomo.sh, tomo-install.json, instance/, home/}` — no more single `$REPO_ROOT/tomo-install.json` / shared `tomo-home` / shared launcher.
3. Instance name configurable and surfaced inside the container (`--hostname`, statusline) and to Hashi (`miyo.tomo.instance-name` label — already present).
4. `update-tomo.sh` operates per-instance.
5. **Migration** of the existing single-instance install is the key risk — design explicitly.

**Part B — Lifecycle tag-prefix cleanup:**
- Remove the wizard prompt + `--prefix` flag; stop writing `lifecycle.tag_prefix` to vault-config.
- Delete dead `tomo/scripts/state-scanner.py` (tag-based discovery, unreferenced post-F-47).
- Repoint `tomo-statusline.sh` Test 2 from `byTag #<prefix>` to a `byFrontmatter tomo.state` read.
- Sweep docs + `vault-example.yaml` for `#MiYo-Tomo/captured` references.

**Constraints:** bash 3.2 (macOS); Constitution L1 (tests on filesystem paths + happy/failure cases); additive-where-possible; migration designed before coding.

**Branch:** `feat/020-multi-instance-install`.

Related: builds on spec 019 (IDE Bridge — per-instance `tomo-home/.claude/ide/<port>.lock`), F-47 (frontmatter lifecycle state), backlog D-09 (shared render-launcher helper — relevant to per-instance launcher rendering).

---
*This file is managed by the xdd-meta skill.*
