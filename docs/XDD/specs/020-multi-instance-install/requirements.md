---
title: "Multi-instance first-class install + lifecycle tag-prefix cleanup"
status: draft
version: "1.0"
---

# Product Requirements Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain (remaining items live in Open Questions, deferred to SDD)
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria (Gherkin format)
- [x] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [x] Problem is validated by evidence (real install attempt + code citations)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Metrics map to verifiable outcomes (no telemetry — Constitution forbids it)
- [x] No feature redundancy
- [x] No technical implementation details included (layout/migration mechanics deferred to SDD)
- [x] A new team member could understand this PRD

---

## Product Overview

### Vision
One Tomo installation that cleanly hosts **many** self-contained instances — one per vault or context — each with its own files, its own name, and its own update lifecycle.

### Problem Statement
Tomo's installer assumes a **single** instance. Every install writes to the same three repo-root locations: `$REPO_ROOT/tomo-install.json` (config), `$REPO_ROOT/tomo-home` (Docker home), and `$REPO_ROOT/begin-tomo.sh` (launcher) (`install-tomo.sh:13,1222,1270`). Standing up a second instance with the default flow **overwrites the first**: its config record, its auth/home state, and its launcher. The isolation flags that would prevent this (`--instance-name`, `--instance-location`, `--home-dir`, `--config-file`, `install-tomo.sh:44-47`) exist only for test isolation and must all be supplied manually and consistently — there is no guidance, no discovery of existing instances, and the wizard's only re-run affordance is a single "Use existing config? [Y/n]" (`install-tomo.sh:755`). The practical consequence: a user who wants Tomo for two vaults (e.g. *Privat* and *Work*) cannot do it through the supported path without risking clobbering.

Separately, the install wizard still prompts for a **lifecycle tag prefix** (and exposes a `--prefix` flag) whose purpose was removed by F-47: lifecycle state now lives in `tomo.state` frontmatter (written by `mark-captured.py` via `write_frontmatter`), and Tomo no longer writes `#<prefix>/captured` tags at all. The prompt, the `lifecycle.tag_prefix` config field, the dead `state-scanner.py` (tag-based discovery, unreferenced outside retired specs 003/004), and a statusline "tag access" probe that searches for a tag that is never written are all residual scaffolding that confuses users and maintainers.

### Value Proposition
- **For the user:** install and run Tomo against multiple vaults without manual flag juggling or fear of clobbering; each instance is a portable, self-contained directory; the launcher tells you when an instance is behind the repo and offers to update it.
- **For the maintainer:** the install wizard stops asking for a setting that does nothing, and dead code is removed — the wizard reflects the real (frontmatter-based) lifecycle model.

## User Personas

### Primary Persona: Multi-vault PKM power user (Marcus)
- **Demographics:** Technical Obsidian user; runs Tomo in Docker; maintains more than one vault (e.g. a personal vault and a work/client vault) with different content-sensitivity and config.
- **Goals:** Run an isolated Tomo instance per vault; create a new instance in minutes; keep each instance updated against the Tomo source repo; see at a glance which instance a session belongs to.
- **Pain Points:** Today a second install silently overwrites the first; instance files are scattered at the repo root; no way to list what instances exist; no signal when an instance is behind the repo.

### Secondary Persona: First-time single-instance user
- **Demographics:** New Tomo user setting up exactly one vault.
- **Goals:** Get one instance running with minimal ceremony.
- **Pain Points:** Should not be burdened by multi-instance complexity — the single-instance path must stay simple. (This persona constrains the design: multi-instance must not make the common case harder.)

## User Journey Maps

### Primary User Journey: Add a second instance for a different vault
1. **Awareness:** User already runs one Tomo instance; wants a separate one for another vault.
2. **Consideration:** Re-runs `install-tomo.sh`. Instead of a single "use existing config?" prompt, the wizard lists known instances and offers **create new** or **update an existing one**.
3. **Adoption:** Chooses "create new", names it, picks (or accepts the default) parent dir; a self-contained instance directory is created and registered.
4. **Usage:** Runs that instance's own `begin-tomo.sh`. The container, the in-container statusline, and Hashi all show the instance's name. The first instance is untouched.
5. **Retention:** On a later launch, `begin-tomo.sh` notices the Tomo repo is newer than this instance and offers to update it — the user stays current without tracking versions manually.

### Secondary User Journey: Keep an instance up to date
1. User launches an instance via its `begin-tomo.sh`.
2. The launcher compares the instance's installed version against the Tomo repo it was built from (repo path from the registry).
3. If the repo is newer, the launcher warns and offers to run the update for this instance (or proceed without updating).

## Feature Requirements

### Must Have Features

#### Feature 1: Self-contained per-instance directory
- **User Story:** As a multi-vault user, I want each instance to live in its own directory containing everything it needs, so that instances never share state and can be moved or deleted independently.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a new install, When the user names an instance, Then a single directory `<parent>/<instance-name>/` is created containing the instance's launcher, its config record, its Claude Code workspace, and its Docker home mount — nothing instance-specific is written outside that directory.
  - [ ] Given two instances created with different names, When both exist, Then neither instance's launcher, config, workspace, or home directory is shared with or overwritten by the other.
  - [ ] Given an instance directory, When the user deletes that directory, Then no other instance is affected (self-containment).

#### Feature 2: Instance registry + discovery
- **User Story:** As a user with multiple instances, I want install to know what instances already exist, so that re-running it lets me update a specific one instead of clobbering.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given an instance is created, When install completes, Then the instance is recorded in a registry at `~/.tomo/instances.json` with at least its name, instance-directory path, the Tomo source-repo path it was built from, and its installed version.
  - [ ] Given one or more registered instances, When `install-tomo.sh` is re-run, Then it lists the known instances and offers "create new" vs "update `<name>`" (replacing the single "Use existing config? [Y/n]" prompt).
  - [ ] Given the registry references an instance directory that no longer exists, When install reads the registry, Then it reports the stale entry and does not crash (graceful handling — failure case).
  - [ ] Given no registry exists yet, When install runs, Then it creates one and proceeds as a first-instance install (happy path on a clean machine).

#### Feature 3: Configurable instance name surfaced in container + Hashi
- **User Story:** As a user juggling instances, I want each instance's name visible inside its container and in Hashi, so that I always know which instance a session belongs to.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given an instance named `<name>`, When its container starts, Then the instance name is visible inside the container (e.g. the in-container statusline shows `<name>`, not a generic "tomo-instance").
  - [ ] Given an instance named `<name>`, When its container starts, Then Hashi can identify it by the `miyo.tomo.instance-name=<name>` Docker label (already emitted at `begin-tomo.sh.template:487`).
  - [ ] Given two running instances, When the user inspects either container, Then each reports its own distinct name (no collision; container name remains `tomo-<name>`).

#### Feature 4: Per-instance update
- **User Story:** As a maintainer of several instances, I want to update one instance at a time, so that updating "Work" never touches "Privat".
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given multiple registered instances, When the user runs the update flow for a chosen instance, Then only that instance's files are updated and only that instance's config/version record changes.
  - [ ] Given an instance selected for update, When the update runs, Then it reads that instance's own config record (not a single shared repo-root file).

#### Feature 5: Launcher update-availability check
- **User Story:** As a user, I want my instance's launcher to tell me when it's behind the Tomo repo, so that I can stay current without manually comparing versions.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given an instance whose installed version is older than the Tomo repo it was built from, When the user runs that instance's `begin-tomo.sh`, Then the launcher warns that an update is available (showing installed vs available version).
  - [ ] Given an update is available, When the launcher warns, Then it offers to run the update for this instance immediately, and the user may decline and launch anyway.
  - [ ] Given the instance is at or ahead of the repo version, When `begin-tomo.sh` runs, Then no update prompt appears and launch proceeds normally.
  - [ ] Given the recorded Tomo-repo path no longer exists or its version cannot be read, When `begin-tomo.sh` runs, Then it skips the check with a non-fatal note and launches normally (failure case — never block launch on the check).

#### Feature 6: Remove vestigial lifecycle tag prefix
- **User Story:** As a user, I don't want to be asked for a setting that has no effect, and as a maintainer I don't want dead code, so that the wizard reflects the real (frontmatter-based) lifecycle model.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given the install wizard runs, When the user reaches the lifecycle section, Then there is no "Lifecycle tag prefix" prompt and no `--prefix` flag, and no `lifecycle.tag_prefix` value is written to vault-config.
  - [ ] Given the codebase after this change, When searching for `state-scanner.py`, Then the dead tag-based discovery script no longer exists and nothing references it.
  - [ ] Given the in-container statusline runs, When it performs its Kado read-access check, Then it uses a `byFrontmatter tomo.state` read (the real model) rather than a `byTag #<prefix>` search for a tag Tomo never writes.
  - [ ] Given an inbox run after this change, When `/inbox` processes items, Then lifecycle behaviour (capture → active, discovery, cleanup) is unchanged — it already depends only on `tomo.state` frontmatter, not on the removed prefix (regression guard).

### Should Have Features
- **Documentation sweep:** user-facing docs and the example config are updated to match — remove `#MiYo-Tomo/captured` lifecycle-tag references and the tag-prefix prompt from `configuration.md`, `setup.md` (step 4), `usage.md` (lifecycle namespace), `troubleshooting.md`, and `vault-example.yaml`; document the multi-instance install flow, the registry, and the launcher update check.

### Could Have Features
- **Top-level instance picker:** an optional top-level launcher/command that lists registered instances and lets the user pick one to start, instead of running each instance's `begin-tomo.sh` directly.
- **Auto-trigger update from the launcher prompt:** beyond offering to update, run the update script inline and relaunch in one step (a polish on Feature 5's "offer to run").

### Won't Have (This Phase)
- **Legacy-layout migration.** There is no real legacy to migrate: the repo's `$REPO_ROOT/tomo-instance` + `tomo-home` is a **manually-maintained development/test instance**, which the maintainer will reconcile by hand. The new layout is the only supported layout; no automatic migration of a flat repo-root install is built.
- **Running/orchestrating multiple instances simultaneously** through a single control surface (each instance is still launched on its own).
- **Remote or networked instances.** Instances remain local Docker containers (Constitution: local-first).

## Detailed Feature Specifications

### Feature: Instance registry + discovery (most complex)
**Description:** A registry file at `~/.tomo/instances.json` is the index of all Tomo instances on the machine. Each instance's full configuration continues to live in that instance's own `tomo-install.json`; the registry is a lightweight index (name → location + source-repo path + installed version) so that install can discover, list, and target instances regardless of where their directories live.

**User Flow:**
1. User runs `install-tomo.sh`.
2. System reads `~/.tomo/instances.json` (creating it empty if absent).
3. System lists registered instances and offers: create new / update `<name>`.
4. On "create new": user provides a name and (optionally) a parent dir (default `~/MiYo/Tomo/`); system creates `<parent>/<name>/`, installs into it, and adds/refreshes the registry entry.
5. On "update `<name>`": system loads that instance's `tomo-install.json` and runs the update against that instance only.

**Business Rules:**
- The instance directory's own `tomo-install.json` is the source of truth for that instance's configuration; the registry is an index and must be reconcilable from the instance directories (it must not hold config that exists nowhere else).
- The registry stores, per instance: name, instance-directory path, Tomo source-repo path, installed version, and an install/update timestamp.
- Instance names must be unique within the registry.

**Edge Cases:**
- Registry entry points to a missing directory → report stale entry, offer to drop it, do not crash.
- Two instances requested with the same name → reject the duplicate name and re-prompt.
- Registry file missing or unreadable → treat as "no instances yet"; recreate on next successful install (registry is rebuildable, not authoritative for config).
- `~/.tomo/` not writable → fail with a clear error before creating any instance files.

## Success Metrics

> Tomo collects **no telemetry** (Constitution L1). "Metrics" here are verifiable outcomes checked via tests and manual validation, not analytics events.

### Key Performance Indicators
- **Isolation correctness:** creating a second instance leaves the first instance's launcher, config, workspace, and home byte-unchanged (verified by test).
- **Discovery correctness:** a freshly created instance appears in `~/.tomo/instances.json` and is offered on the next install re-run (verified by test).
- **Identity correctness:** each running container reports its own instance name in the statusline and via the Docker label (verified by test/inspection).
- **No regression:** the full existing test suite passes; `/inbox` lifecycle behaviour is unchanged after the tag-prefix removal.
- **Wizard honesty:** no removed/dead setting is prompted for (verified by test asserting the prompt/flag is gone).

### Tracking Requirements
Not applicable — no telemetry. Validation is via the test suite and a manual two-instance smoke test on the maintainer's machine.

---

## Constraints and Assumptions

### Constraints
- **bash 3.2** (macOS default) — no associative arrays; portable constructs only.
- **MiYo Constitution L1 (Testing):** filesystem/path code must have happy-path AND failure/denial tests — this feature is almost entirely path and config code.
- **Local-first (Constitution L1):** registry and all instance files stay on the user's machine; registry holds paths/metadata only, never vault content.
- **Additive-where-possible on hot paths:** the in-container runtime (agents, inbox pipeline) should be unaffected; changes concentrate in install/update/launcher/statusline.

### Assumptions
- The maintainer will reconcile the repo's existing `tomo-instance`/`tomo-home` test setup by hand (no migration tooling needed).
- Each instance is built from a known Tomo source repo whose path can be recorded and later read for the version check.
- The Tomo repo version is readable from a single canonical source (as install already does — `# version:` in `tomo/dot_claude/rules/project-context.md`).
- A user runs one instance's container at a time per launcher invocation (no built-in concurrent orchestration required).

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Registry drifts from reality (entries for deleted/moved instances) | Medium | Medium | Treat instance dirs as source of truth; registry is a rebuildable index; handle stale entries gracefully; consider a reconcile/scan fallback in SDD |
| Removing `lifecycle.tag_prefix` breaks a hidden consumer | High | Low | Audit completed this session — only the statusline probe + dead `state-scanner.py` touch it; add a regression test that `/inbox` lifecycle still works via `tomo.state` |
| Launcher version check blocks or slows launch | Medium | Low | Check must be non-fatal and skip cleanly on any error; never block the container start |
| Instance name unsafe as container hostname (invalid chars) | Low | Medium | Sanitize the name for hostname use while preserving the display name (design in SDD — OQ5) |
| Per-instance launcher duplicates the install/update sed-render logic (backlog D-09) | Low | Medium | Reuse / extract the shared render-launcher helper as part of this work |

## Open Questions

Deferred to SDD (technical/cosmetic, do not block requirements):
- [ ] **OQ2 — Inner directory names:** keep `tomo-instance/` + `tomo-home/` inside each instance dir, or rename to `instance/` + `home/`? Affects the `TOMO_INSTANCE_DIR` basename that the statusline reads.
- [ ] **OQ5 — Instance name vs container hostname:** sanitize the name for `--hostname` (which rejects some characters) while showing the raw name in the statusline; decide whether the statusline reads a new `TOMO_INSTANCE_NAME` env or keeps deriving from the dir basename.
- [ ] **OQ7 — Registry schema + version field:** exact JSON shape of `~/.tomo/instances.json`, and which version string the launcher compares (installed `tomoVersion` vs repo `# version:` source).
- [ ] **OQ8 — Default parent creation:** if `~/MiYo/Tomo/` doesn't exist, create it silently or confirm with the user first.

---

## Supporting Research

### Competitive Analysis
Not a market-facing feature. Prior art within the project: the existing isolation flags (`--instance-name`, `--instance-location`, `--home-dir`, `--config-file`) already prove the runtime can host distinct instances (distinct container names via `tomo-<name>`); this spec promotes that capability from a test-only mechanism to a first-class, registry-backed install flow.

### User Research
Direct stakeholder (Marcus) input, this session: (a) install should support multiple instances; (b) each instance is its own directory holding all its files (begin-tomo, home, workspace); (c) the instance name must be configurable and visible inside the container and in Hashi. Migration: not needed — the repo `tomo-instance` is a hand-maintained test instance. Discovery: registry file. Launcher: per-instance, with an added repo-version update check driven by the registry's recorded repo path.

### Market Data
N/A — internal developer tooling.
