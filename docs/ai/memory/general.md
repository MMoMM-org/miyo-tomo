# General — Tomo
<!-- Conventions, naming rules, code style, git workflow. Updated: 2026-05-07 -->
<!-- What goes here: how files are named, folder structure, style choices, branch conventions -->
<!-- What does NOT go here: tool-specific quirks (→ tools.md), domain rules (→ domain.md) -->

<!-- 2026-05-06 -->
- Before brainstorming a new feature in Tomo, grep `docs/XDD/reference/tier-3/` and `tomo/schemas/` for prior art. F-43 (MOC-creation skill) had ~70% of the spec already in place — `tier-3/lyt-moc/new-moc-proposal.md`, `moc-matching.md`, `t_moc_tomo` template, and the `create_moc` / `add_relationship` actions in `instructions.schema.json` — that a greenfield brainstorm would have duplicated. The pattern: tier-3 = "what should happen", schema = "how the action is shaped"; both often pre-date the user-facing skill that wires them up. Saves ~30% of brainstorm time and avoids accidental contradictions with existing spec.

<!-- 2026-05-07 -->
- Orchestrator slash commands have two valid model interpretations: **impersonation** (parent reads the orchestrator's body and acts on it) vs **dispatch** (parent spawns the orchestrator as a Task subagent). Impersonation costs ~60% more tokens than dispatch on /inbox-shape workflows because the parent re-reads context that a fresh subagent would receive cleanly. Lock the reading explicitly with STRICT/NEVER wording in the orchestrator's frontmatter — and pick dispatch unless the orchestrator must fan out further subagents (nested Agent dispatches fail). Touch point: any new orchestrator agent in `tomo/dot_claude/agents/`. Confirmed 2026-05-01 /inbox token analysis.
- Haiku is **not** strong enough for STRICT-orchestration agents — twice in /inbox runs a haiku-pinned orchestrator silently skipped Pass-2 dispatch and rendered the artefact itself instead of running the deterministic scripts (Step 2.5 fan-resolve and instruction-render were both bypassed). Pin sonnet or opus for orchestration roles; haiku is fine for terminal/leaf subagents that only follow a literal script. Touch point: `model:` field in orchestrator agent frontmatter. Confirmed 2026-05-01 (twice in same session).
