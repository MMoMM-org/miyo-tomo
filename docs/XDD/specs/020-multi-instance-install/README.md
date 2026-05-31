# Specification: 020-multi-instance-install

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-05-31 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-05-31 |

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
