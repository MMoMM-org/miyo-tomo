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

## check-moc-uplinks Mode Skips the Two-Pass Topic Extraction (ADR-12, T6.5)

WHY: The `check:moc-uplinks` mode runs `moc-discovery.py --check-moc-uplinks` in
a SINGLE pass — no `--emit-phase1` / topic-extract / `--phase1-input` round-trip.
The two-pass dance exists only to let the agent LLM-extract topics for cache-miss
note candidates before clustering. check-mode does no clustering and operates on
cache MOC entries that already carry topics, so the agent invokes discovery once,
captures the DiscoveryReport from stdout, and proceeds straight to render +
transport. Forcing it through the two-pass path would burn an emit-phase1 file and
a topic-extract step for zero benefit.

## Contiguous Step Numbering (T6.5)

WHY: The Workflow steps were renumbered to be contiguous (1, 2, 3, …). An earlier
refactor left a Step 2→4 gap (no Step 3), which reads as a missing/forgotten step
and invites the model to hunt for it. Every step number now maps to a real step.

## Version 0.7.0

WHY: Bumped from 0.6.0 for the `check:moc-uplinks` mode (single-pass audit route),
the contiguous step renumbering, and the agent-author lean-pass. 0.6.0 added the
Step transport change (inline kado-write → `kado-write-file.py`) + `tools`
minimisation. `update-tomo.sh` skips unchanged versions, so the change only ships
if the version header advances.
