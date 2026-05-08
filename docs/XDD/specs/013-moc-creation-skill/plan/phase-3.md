---
title: "Phase 3: Producer Surface — Reducer, Agent, Command"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Producer Surface — Reducer Extension, Agent, Slash Command

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Runtime View/Primary Flow]` — full producer sequence.
- `[ref: SDD/UI Visualization Guide]` — proposal-doc layout (single + multi-cluster).
- `[ref: SDD/Architecture Decisions/ADR-4]` — doc shape.
- `[ref: SDD/Architecture Decisions/ADR-9]` — template-rendered Why-narrative.
- `[ref: PRD/Feature 3]` — reviewable proposal-doc in inbox.

**Key Decisions**:
- **ADR-2**: Multi-MOC filename slug = top-confidence cluster.
- **ADR-4**: Section heading = `### MOCxx — <Title>`; top-level Accept = `- [ ] Accept` list-item.
- **ADR-9**: Why-narrative = template-rendered structured fields (no LLM).

**Dependencies**:
- Phase 2 (T2.1-T2.7) — `moc-discovery.py` produces `DiscoveryReport` JSON consumed by T3.1.
- T1.4 (`obsidian-markdown` skill) — referenced by T3.2 agent frontmatter.

---

## Tasks

This phase delivers the user-facing producer path: command → agent → discovery → reducer → proposal-doc on disk. After this phase, `/moc-propose tag:X` writes a real reviewable proposal-doc to the inbox.

- [x] **T3.1 `suggestions-reducer.py` `--moc-proposal-mode` branch + render** `[activity: backend-rendering]`

  1. Prime: Read `tomo/scripts/suggestions-reducer.py` lines 663-693 (existing render block entry) `[ref: SDD/Implementation Context/suggestions-reducer.py]`. Read SDD `UI Visualization Guide` for the target Markdown shape `[ref: SDD/UI Visualization Guide]`. Read SDD `Application Data Models` for `DiscoveryReport` input shape.
  2. Test: `tests/test_reducer_moc_proposal_mode.py::test_single_cluster_render` (1 cluster → 1 `### MOC01` section, exact heading format, `- [ ] Accept` list-item, editable text fields, Parent + Children + Override sections present); `test_multi_cluster_render` (3 clusters → 3 sections sorted by confidence DESC, MOC01-MOC03 IDs); `test_overflow_footer` (max_results=5 with 7 clusters → 5 sections + "Weitere 2 Cluster gefunden" footer); `test_filename_top_confidence_slug` (filename = `tomo-moc-proposal-<date>-<top-cluster-slug>.md` per ADR-2); `test_per_child_existing_up_annotation` (children rendered with parenthetical noting `valid|absent|broken`); `test_template_why_narrative` (Why-section uses template fields, deterministic across runs).
  3. Implement: Add `--moc-proposal-mode` flag + `--input <discovery-report.json>` to `suggestions-reducer.py`. New function `render_moc_proposal_doc(report: DiscoveryReport, config) -> (path, body)`. Markdown rendering via plain f-strings (no Jinja); Why-narrative template = `f"{n} Notes mit Topic-Overlap {topics_csv} haben keine dedizierte MOC. {k} davon haben up:: zur Klassifikation {parent}. Diese MOC würde die Lücke füllen."` with safe fallbacks if `parent` is null. Filename slug uses existing `slugify()` from `instruction-render.py:115-124`; multi-cluster filename uses top-confidence cluster's slug per ADR-2. Bump `# version:`.
  4. Validate: `pytest tests/test_reducer_moc_proposal_mode.py -v`. Visual check: render against a hand-built `DiscoveryReport` fixture; open in Obsidian; verify dataview fields parse and wikilinks resolve.
  5. Success: Proposal-doc shape matches ADR-4 + UI Visualization Guide `[ref: PRD/AC-3.1, AC-3.2, AC-3.3, AC-3.4]` `[ref: SDD/ADR-2]` `[ref: SDD/ADR-4]` `[ref: SDD/ADR-9]`.

- [x] **T3.2 `moc-architect` agent** `[parallel: true]` `[activity: agent-author]`

  1. Prime: Read existing agent `tomo/dot_claude/agents/inbox-analyst.md` for frontmatter + step structure `[ref: SDD/Implementation Context/inbox-analyst.md]`. Read sibling `vault-explorer.md`. Read `feedback_agent_format_enforcement.md` and `feedback_subagent_tool_availability.md`. Read `feedback_skill_format_distinction.md` for skill reference syntax.
  2. Test: N/A (agent-spec authoring). Done = file exists with correct YAML frontmatter, all referenced tools+skills resolvable in container, agent can be spawned via `/moc-propose` slash command without "Unknown skill" errors.
  3. Implement: Create `tomo/dot_claude/agents/moc-architect.md` with frontmatter: `name: moc-architect`, `description: "Discovers topic clusters in user vault, proposes new MOCs, emits proposal-doc to inbox. Triggers: topic density scan, tag-based discovery, folder browsing, title seeding via /moc-propose."`, `model: sonnet`, `effort: medium`, `color: <pick a free color>`, `tools: Bash, Read` (Bash for invoking python scripts; Read for diagnostics; Kado MCP tools NOT needed — discovery script handles Kado), `skills: [obsidian-markdown, lyt-patterns, obsidian-fields]`, `permissionMode: acceptEdits`. Body: STRICT/MUST rules + Steps 1-9 mirroring SDD `Runtime View/Primary Flow`. Use STRICT wording per `feedback_agent_format_enforcement.md`. Add `# version: 0.1.0`.
  4. Validate: Run `./scripts/update-tomo.sh`; restart Tomo container per `feedback_restart_after_agent_sync.md`. Inside container: invoke `/moc-propose --help` (or equivalent help-mode); verify agent activates and reports correct mode-routing without errors.
  5. Success: Agent activates from slash command, dispatches to `moc-discovery.py` and `suggestions-reducer.py` correctly `[ref: SDD/Runtime View/Primary Flow]` `[ref: SDD/Building Block View]`.

- [x] **T3.3 `/moc-propose` slash command** `[parallel: true]` `[activity: command-author]`

  1. Prime: Read existing command `tomo/dot_claude/commands/inbox.md` for frontmatter + body conventions `[ref: SDD/Implementation Context]`.
  2. Test: N/A (command-spec authoring). Done = file exists with correct frontmatter, the command is invocable inside the Tomo container.
  3. Implement: Create `tomo/dot_claude/commands/moc-propose.md` with frontmatter: `name: moc-propose`, `description: "Propose a new MOC for a topic, folder, classification, or whole-vault scan. Routes to moc-architect agent."`. Body: usage/help section listing all 6 input modes with examples (per PRD AC-1.x), STRICT routing rule (whitelist-only prefixes `tag:|folder:|class:|title:`, anything else = free-text), and explicit IMPERSONATE-vs-DISPATCH wording per `feedback_orchestrator_impersonate_vs_dispatch.md` (the command IMPERSONATES `moc-architect` which DISPATCHES to scripts; do NOT use Agent-tool nesting). Add `# version: 0.1.0`.
  4. Validate: Run `./scripts/update-tomo.sh`; restart container. Inside container, invoke `/moc-propose tag:topic/applied/zsh` against Privat-Test; verify the command resolves to `moc-architect`, which calls `moc-discovery.py`, which produces JSON, which is consumed by `suggestions-reducer.py`, which writes a proposal-doc to `<inbox_path>/`.
  5. Success: End-to-end producer path produces a proposal-doc on disk `[ref: PRD/AC-1.1 to AC-1.7]` `[ref: PRD/AC-3.1, AC-3.2, AC-3.3]`.

- [x] **T3.4 Phase 3 Validation** `[activity: validate]`

  Run `pytest tests/test_reducer_moc_proposal_mode.py -v` and any regression suite for the existing inbox flow. Run `ruff check`. **Live producer smoke**: invoke `/moc-propose tag:<real-tag>` inside the container against Privat-Test; verify the resulting proposal-doc parses as valid Obsidian Markdown, dataview fields render, wikilinks resolve. **Save the rendered proposal-doc to `tomo-tmp/` as the canonical fixture for Phase 4 parser tests** (per `feedback_fixture_from_live_render.md`).
