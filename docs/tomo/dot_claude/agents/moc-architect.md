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

## /moc-propose Writes No Vault Note — Orphan Reasons Are Stamped at Apply Time (CON-3, OQ-6)

WHY: For a `create_new` orphan, the proposal-doc renders the orphan's `reason`
plus an instruction that, on accept, `/inbox` renders into the instruction set —
applied later (by hand or via Hashi) to stamp the reason into the note(s) and
create the new MOC. `/moc-propose` itself writes ONLY the proposal-doc to the
inbox — it never mutates vault notes (the 2-pass model, CON-3). The actual
`up:`/note write happens later at apply time through
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

## around Mode Is Single Pass (spec 042, F2/F3)

WHY: `moc-discovery.py --around` resolves the seed from the discovery cache,
makes one `kado-graph neighbors` lookup and builds the proposal (or the
extension) in one invocation. There is no topic extraction to hand to the LLM —
members come from links, not from topics — so the `--emit-phase1` /
`--phase1-input` round-trip has nothing to do. The script exits 2 (FATAL usage)
if `--around` is combined with `--emit-phase1`, `--phase1-input` or
`--check-moc-uplinks`, so the agent routes `around` through its own single-pass
branch, like `check-moc-uplinks`, and then straight to the reducer. The
`trigger_arg` is quoted in the call because seed names often contain spaces
(`around:Health MOC`).

The around aborts (`around-not-found`, `around-ambiguous`, `around-periodic`,
`around-ineligible`, `seed-lookup-failed`, `fewer-than-3-notes`,
`no-missing-members`) carry an `abort_message` the script fills with the seed
name, the candidate paths or the remedy. The agent relays it verbatim through
the existing Step 4 rule; it never classifies or rewords an around abort itself,
so a new abort reason in the script needs no prose change.

## Link Counts Ride the `Discovery:` Line (spec 042, F7)

WHY: The six-field STRICT output block is a fixed contract (rules/authoring
"fixed output format"); adding a seventh field would break every reader of the
block and the earlier examples. Link evidence is therefore appended to the
existing `Discovery:` line as `; links: K members, L lookups`, read from the
DiscoveryReport's `link_stats` (`members_total`, `lookups`). It is printed on
every run, including `K = 0`, because "no link members" is itself the signal the
owner needs to judge whether link discovery ran (F7-AC2) — an omitted suffix
would be indistinguishable from a run where the feature never fired. The
` (S skipped: budget)` suffix appears only when `clusters_skipped_budget > 0`:
the 120-attempt graph budget (ADR-4) degrades silently per cluster, and this
suffix and ` (P sampled: budget)` are the one place the user learns proposals
were written without, or with only partial, link evidence.
Failed lookups (`link_stats.failed`) go to `Aborts/notes` as
`lookups failed: F`, matching the SDD error table, because a failure is a
warning about the run rather than a count of what it produced. When the payload
has no `link_stats` (a Pass-1 abort from the `--emit-phase1` file), the counts
are 0 rather than omitted, so the line shape never varies.

## Reducer Gets `--config` (spec 042)

WHY: `suggestions-reducer.py --moc-proposal-mode` reads
`tomo.moc_proposal.max_results` from `--config` (default
`config/vault-config.yaml`, cwd-relative). Passing it explicitly makes the
reducer call match every discovery call and keeps the rendered slice and the
slice `moc-discovery.py` augments with link members reading the same file —
discovery augments exactly `clusters[:max_results]`, so a reducer reading a
different config would render clusters that were never looked up.

## Pass 2 Exit 1 Is a Partial Result, Not a Failure (spec 042)

WHY: `moc-discovery.py` exits 0 (clean), 1 (partial) or 2 (fatal). Exit 1 means
the scan finished and printed the full DiscoveryReport but dropped some clusters
(D3 duplicates, squelched clusters). A live run on 2026-10-29 stopped on exit 1
after D3 dropped 104 duplicate clusters, so a perfectly usable report never
reached the reducer. The agent therefore stops only on exit 2 and parses stdout
on exit 0 or 1. The same wording is used in the `around` single-pass branch even
though `--around` returns only 0 or 2: one uniform rule for every
`moc-discovery.py` call that returns a report is simpler than a per-mode table.
`--emit-phase1` (Step 3a) and `--check-moc-uplinks` keep their rules, because
exit 1 cannot occur there. The reducer and transport rules are unchanged:
non-zero there is a real failure.

## Sampled Clusters Are Shown on the `Discovery:` Line (spec 042, F7)

WHY: A cluster whose members were looked up only in part (graph budget ran out
mid-cluster) is rendered with fewer link members than exist. The
` (P sampled: budget)` suffix, read from `link_stats.clusters_sampled`, tells
the user which share of proposals rests on partial link evidence. It sits before
the ` (S skipped: budget)` suffix because sampled clusters are rendered and
skipped ones are not; like the skipped suffix it appears only when its count is
above 0.

## Version 0.8.0

WHY: Bumped from 0.7.0 for the `around` mode (routing, single-pass branch), the
link counts on the `Discovery:` line and the reducer `--config` argument.
`update-tomo.sh` skips unchanged versions.

## Version 0.8.1

WHY: Bumped from 0.8.0 for the exit-code rule (exit 2 fatal, exit 0 or 1 parse
stdout) in the `around` and Pass 2 steps and the `sampled` suffix on the
`Discovery:` line. `update-tomo.sh` skips unchanged versions.

## Version 0.8.2 — `around` Discovery line (spec 042, #216)

WHY: Live runs printed `OK — 1 candidates → 1 clusters` for `around:<note>` and
`OK — 0 candidates → 1 clusters` for `around:<MOC>`. In `around` mode
`candidates_total` and `topic_clusters` describe the engine's internals, not what
the owner got: one new MOC, or an extension of an existing one. The line now names
the outcome. The agent tells the two apart by `around.kind` (set from the resolved
seed in `moc-discovery.py`; `moc` means the extension path, which also fills
`extension`) and takes the name from `around.stem`. The `; links: …` part is
unchanged. `update-tomo.sh` skips unchanged versions.
