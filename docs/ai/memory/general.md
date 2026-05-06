# General — Tomo
<!-- Conventions, naming rules, code style, git workflow. Updated: 2026-05-06 -->
<!-- What goes here: how files are named, folder structure, style choices, branch conventions -->
<!-- What does NOT go here: tool-specific quirks (→ tools.md), domain rules (→ domain.md) -->

<!-- 2026-05-06 -->
- Before brainstorming a new feature in Tomo, grep `docs/XDD/reference/tier-3/` and `tomo/schemas/` for prior art. F-43 (MOC-creation skill) had ~70% of the spec already in place — `tier-3/lyt-moc/new-moc-proposal.md`, `moc-matching.md`, `t_moc_tomo` template, and the `create_moc` / `add_relationship` actions in `instructions.schema.json` — that a greenfield brainstorm would have duplicated. The pattern: tier-3 = "what should happen", schema = "how the action is shaped"; both often pre-date the user-facing skill that wires them up. Saves ~30% of brainstorm time and avoids accidental contradictions with existing spec.
