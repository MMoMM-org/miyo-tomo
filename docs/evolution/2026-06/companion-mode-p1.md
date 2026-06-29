# 2026-06-28 — Spec 026: Companion Mode P1 — Framework Authoring Skills

**Context**: Spec 026 extends Tomo from inbox triage to active artifact authoring. The user can now
ask Tomo to compose Obsidian notes, Bases views, and Canvas files and write them to the inbox.
Five new or upgraded skills deliver format knowledge and write orchestration; two new deterministic
scripts gate parse validity; the existing write script gains a collision guard.

**Status**: Phases 1–4 shipped 2026-06-28. Phase 5 (docs, attribution, integration) in progress
2026-06-29.

**Spec**: `docs/XDD/specs/026-companion-p1-authoring-skills/`

---

## What changed

### Phase 1 — Deterministic safety scripts

**`tomo/scripts/validate-json.py`** (new, v0.1.0 — `ae0b720`)
Parse-gate for `.canvas` files. `json.loads` the file before any vault write; exit 0 valid /
exit 1 malformed (error to stderr); writes nothing. ADR-9: safety is deterministic + unit-tested,
not LLM-judged.

**`tomo/scripts/kado-write-file.py --no-overwrite`** (extended, v0.3.1 — `06a51f0`, `212fad5`)
New flag for collision detection. When the vault path already exists: print `EXISTS:<path>` to
stdout and exit 3 without writing. Absence → normal write (exit 0). Contract locked for T4.2
(inbox-author reads exit 3 + EXISTS signal to branch into warn+ask flow).

**`tomo/scripts/validate-yaml.py`** (new, v0.1.0 — `3cf6635`, `86521a3`)
ADR-4 correction: `.base` files are YAML, not JSON. Sibling gate for `.base` files using
`yaml.safe_load`; identical exit-code contract to validate-json.py. Extension routing:
`.canvas` → validate-json.py, `.base` → validate-yaml.py.

### Phase 2 — Format-knowledge skills

**`tomo/dot_claude/skills/obsidian-markdown/`** (upgraded, v0.2.0 — `e5fa6aa`)
Flipped to `user-invocable: true`. Description broadened and differentiated from obsidian-fields
(syntax verbs, not metadata classification). Content expanded: tables, task lists, fenced code with
language tags, footnotes, properties/frontmatter YAML, math, Mermaid, comments, highlights.

**`tomo/dot_claude/skills/obsidian-bases/`** (new, v0.1.1 — `ebad120`, `f148eff`, `9ef78b9`, `bd46431`)
YAML format reference for Obsidian Bases (`.base` extension). Sourced from kepano/obsidian-skills
(MIT). Covers: full YAML schema (filters/formulas/properties/summaries/views), filter expression
syntax with AND/OR/NOT operators, three property types (note/file/formula), Duration type handling,
four view types (table/cards/list/map), default summary formulas, YAML quoting rules,
troubleshooting. Full function reference in `references/FUNCTIONS_REFERENCE.md` (progressive
disclosure). Access-agnostic (no Kado mention). Trigger anchored to `.base` only.

**`tomo/dot_claude/skills/obsidian-canvas/`** (new, v0.1.0 — `385f4e3`)
JSON Canvas 1.0 reference for Obsidian Canvas (`.canvas` extension). Node/edge/group structure,
color system, ID rules, validation checklist. Sourced from kepano/obsidian-skills + jsoncanvas.org
spec. Access-agnostic. Trigger anchored to `.canvas` only.

### Phase 3 — Write-side helper skill

**`tomo/dot_claude/skills/kado-write-patterns/`** (new, v0.1.0 — `ce237d4`, `45e3565`, `b14f72d`, `cf3847a`)
Symmetric to kado-discovery-patterns on the write side. Covers the three write paths: (1) markdown
notes via `kado-write-file.py operation=note`, (2) `.base`/`.canvas` artefacts via
`tomo-tmp/staged-artifact.<ext>` → extension-routed parse-gate → `operation=file`, (3)
frontmatter merge via `write_frontmatter`. Includes `--no-overwrite` collision flow and error
handling. Pre-loaded by inbox-author via `skills: [kado-write-patterns]`.

### Phase 4 — inbox-author (rename + extend)

**`tomo/dot_claude/skills/inbox-author/`** (renamed + extended from `default-doc-writer` — `18e652c`, `009f197`, `8ca4049`, `c7ec133`)
ADR-3: `default-doc-writer` renamed to `inbox-author` (scope: free-form docs → all artifact
types including `.base`/`.canvas`). Five-step pipeline and three STRICT guards preserved verbatim.
Extended with: format dispatch (`.md` → token-render; `.base`/`.canvas` → direct-compose →
parse-gate routed by extension → `operation=file`), real template-key resolution with fallback
chain (`atomic_note`, `map_note`, `daily`, `weekly`, `monthly`, `yearly`, `project`, `source`,
`default`), and `--no-overwrite` warn+ask collision step (reads EXIT 3 + EXISTS signal from
kado-write-file.py). Format skills auto-load from description triggers; kado-write-patterns
pre-loaded via `skills:` frontmatter.

**Rename fan-out** (`764c847`):
- `scripts/update-tomo.sh` `RETIRED_SKILLS_DIRS` — added `default-doc-writer` so the old
  instance skill directory is pruned on next sync.
- `tomo/dot_claude/commands/tomo-setup.md` — single runtime reference to `default-doc-writer`
  replaced with `inbox-author`; version bumped 0.2.2 → 0.2.3.
- Old `tomo/dot_claude/skills/default-doc-writer/` and its WHY doc deleted in T4.1.

---

## ADR-4 correction

Original spec assumed both `.base` and `.canvas` were JSON. Fetching the kepano/obsidian-skills
source during T2.2 confirmed `.base` files are YAML (not JSON). ADR-4 was corrected; T1.4
added the YAML gate; all routing in inbox-author and kado-write-patterns uses extension-based
dispatch. `.canvas` remains JSON Canvas 1.0.

---

## References

- Spec 026 PRD: `docs/XDD/specs/026-companion-p1-authoring-skills/requirements.md`
- Spec 026 SDD: `docs/XDD/specs/026-companion-p1-authoring-skills/solution.md`
- kepano/obsidian-skills (MIT): attribution in `docs/tomo/dot_claude/skills/obsidian-bases.md`
  and `docs/tomo/dot_claude/skills/obsidian-canvas.md`
- Constitution L2 Operations: significant setup steps documented here per governance rule
