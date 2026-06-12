# WHY: suggestions-reducer.py

> Rationale for decisions in `tomo/scripts/suggestions-reducer.py`.
> The script reduces per-item result JSONs into a suggestions-doc, and (in
> `--moc-proposal-mode`) renders a DiscoveryReport into a MOC proposal-doc.

## Orphan Overflow Footer + MOC-Uplink Heading (ADR-12, T6.4)

WHY: A whole-vault scan can legitimately surface hundreds of note orphans
(verified real on the live vault — empty `up::` placeholders + notes with no
`up`). moc-discovery caps the rendered set at `orphan_display_cap` and reports
`orphan_overflow`. `_render_orphan_section` renders a footer when `overflow > 0`
so the doc is honest about truncation and points the user at a scoped re-run —
silent truncation would read as "these are all the orphans" when they are not.

`check_mode` (report `mode == "check-moc-uplinks"`) relabels the H1 and the
orphan section as a "MOC Uplink Check" — the same renderer serves both the
notes-discovery proposal and the on-demand MOC-parentage audit, because a
check-mode report is just a DiscoveryReport with no clusters and MOC-kind orphan
suggestions. The cap/overflow live in moc-discovery (config-driven); the reducer
only renders what the report carries (`orphan_overflow`), staying a pure
`(report, config) -> (filename, body)` function with no Kado access (CON-3).

## Orphan Section is Check-Mode-Only (ADR-13 D1, T7.5)

WHY: After ADR-13 D1 the cluster path in moc-discovery no longer populates
`orphan_suggestions` — it always emits `[]`. The reducer gate
`if orphan_suggestions:` (at ~line 707) therefore never fires for cluster-mode
reports, so `## Orphan Notes & MOCs` and its `### Oxx` sub-sections never appear
in a cluster proposal-doc. No change was needed in the reducer itself — the
existing gate is the correct mechanism.

`_render_orphan_section` is check-mode-only as of T7.5. It is NOT removed because
`check-moc-uplinks` reports still carry MOC-orphan suggestions and rely on this
renderer. Any future use case that needs to surface note orphans in a proposal-doc
must explicitly populate `orphan_suggestions` in the DiscoveryReport — the renderer
will pick it up automatically. The renderer stays; only the cluster producer changed.

## N atomic notes per source — C1/C2 (F-41, XDD 016)

WHY: F-41 lets one inbox item emit N `create_atomic_note` actions (one per
conceptual thread — see `docs/tomo/dot_claude/agents/inbox-analyst.md` Step 7.5
and the wire-format ADR-2). The reducer is the first consumer that renders those
atomics for the user, and it had two N=1 traps that silently dropped threads
2..N.

WHY iterate ALL atomics in coexistence enforcement (C1): `_enforce_coexistence`
fetched the atomic action with `next(a for a in actions if kind ==
create_atomic_note)` — only the FIRST. The atomic-vs-`log_entry` coexistence
rules must be evaluated per atomic, so the single-fetch is replaced by iteration
over every `create_atomic_note`. With one atomic this is identical to before
(CON-2); with N it stops discarding the rest.

WHY key section titles per-atomic (C2): the title bookkeeping used
`section_titles[section_id] = title`, a scalar keyed by section. N atomics share
one source section, so the last title overwrote the earlier ones before
`_enrich_proposed_mocs` could use them — the per-atomic MOC enrichment then
operated on the wrong (or a single) title. Keying per-atomic (by index, or a
list) lets all N titles survive into enrichment.

WHY N independent Accept blocks under one source heading, not nested checkboxes
(OQ5): the reducer renders each atomic as its own per-item Accept block with its
own `**Source:** [[stem]]` line and its own `[ ] Approved` toggle, so the user
reviews and approves each thread independently. The per-source `### SNN — title`
heading is emitted by the orchestrator (not the reducer); the per-block
`source_stem` makes a single shared heading acceptable — the user can mentally
group the blocks without visual nesting. Renders stay scannable at the typical
N=2-3 and are designed for N=5 as the realistic upper bound.
