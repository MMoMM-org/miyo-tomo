# Decisions — Tomo
<!-- Architecture choices and rationale. Updated: 2026-05-06 -->
<!-- What goes here: why we chose X over Y, ADR links, significant tradeoff choices -->
<!-- Format: YYYY-MM-DD — Decision: [what] — Rationale: [why] -->

<!-- 2026-05-06 -->
- 2026-05-06 — Decision: External Obsidian skill/agent collections (e.g. `obsidian-ops-team` from davila7/claude-code-templates, `obsidian-bases`/`obsidian-markdown`/`json-canvas` from aitmpl.com) must pass a **Kado-MCP-compatibility check** before being absorbed into Tomo. — Rationale: Tomo's L1 invariant (CLAUDE.md root rule) is "NEVER modify vault files directly — all vault access goes through Kado MCP". Many community Obsidian skills hardcode direct filesystem access (`Read`, `Write`, `Bash` on vault paths, e.g. `/Users/cam/VAULT01/...` in obsidian-ops-team) which violates this contract. Outcome: direct-FS sources are **inspiration-only** (decomposition map, agent-shape patterns), not importable. Reference-style skills (markdown syntax, base spec, JSON canvas spec) without behavioural code can be absorbed as `tomo/skills/<name>/` (`user-invocable: false`, lazy-loaded), since they don't invoke filesystem at runtime. Documented during F-43 source evaluation 2026-05-06; see `docs/XDD/roadmap-obsidian-power.md` "Reference-skill absorption" table.
