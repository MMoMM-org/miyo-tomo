# WHY: moc-architect

> Rationale for decisions in `tomo/dot_claude/agents/moc-architect.md`. The
> agent is the `/moc-propose` orchestrator: it routes args to `moc-discovery.py`
> and renders the proposal-doc via `suggestions-reducer.py --moc-proposal-mode`.

## Case-(a) Orphan Link-or-Create Lives in the Renderer, Not the Agent (spec 021 T2.4)

WHY: The proposal-doc may now carry a `## Orphan Notes & MOCs` section after the
MOC cluster sections. That section is produced entirely by
`suggestions-reducer.py` (`render_moc_proposal_doc` → `_render_orphan_section`)
from the `orphan_suggestions` array on the DiscoveryReport, which `moc-discovery.py`
fills via `lib/orphan_link.emit_orphan_suggestions`. The agent is a pure
orchestrator (same identity as instruction-builder): it never composes markdown,
so the orphan section required NO agent logic — only a one-line note that the
body may include it and must still be passed through byte-identical. Splitting
the orphan rendering between a script and the LLM would create two parallel
format definitions that drift; keeping it 100% in the renderer keeps a single
source of truth.

## /moc-propose Writes No Vault Note — Orphan Reasons Are Stamped by /execute (CON-3, OQ-6)

WHY: For a `create_new` orphan, the proposal-doc renders the orphan's `reason`
plus an instruction that, on accept, `/execute` stamps the reason into the
note(s) and creates the new MOC. `/moc-propose` itself writes ONLY the
proposal-doc to the inbox — it never mutates vault notes (the 2-pass model,
CON-3). The actual `up:`/note write happens later via `/execute` (Hashi) through
`kado_client.write_frontmatter(mode='merge')`. Rendering the reason + the
deferred-write instruction in the doc (rather than writing immediately) is what
keeps `/moc-propose` proposal-only.

## Transport via kado-write-file.py, Not Inline kado-write (spec 021, 2026-06-06)

WHY: Step 7.5 transports the proposal-doc to the vault inbox by running
`scripts/kado-write-file.py` (Bash), NOT by reading the doc and inlining its body
into an `mcp__kado__kado-write` tool call. Observed live (2026-06-06): a
whole-vault `scan` produced a 136 KB proposal-doc (~250 orphan entries); the
inline-kado-write path tried to emit the full body as tool-call args and blew the
output-token budget — the doc was correct on disk but never reached the vault.
The script reads the file from disk and pushes it through its own Kado client
(`operation=note` for `.md`), so the content never routes through the agent's
token budget. This is the established "large/many writes → script with embedded
Kado client" pattern (`decisions.md`). Consequence: the `mcp__kado__kado-write`
tool was dropped from the agent's `tools` list (no longer used).

## Version 0.6.0

WHY: Bumped from 0.5.0 for the Step 7.5 transport change above (inline kado-write
→ `kado-write-file.py` script) + the `tools` minimisation. `update-tomo.sh` skips
unchanged versions, so the change only ships if the version header advances.
