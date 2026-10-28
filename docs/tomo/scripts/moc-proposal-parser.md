# WHY: tomo/scripts/moc-proposal-parser.py

> Rationale for decisions in `tomo/scripts/moc-proposal-parser.py`.
> The script turns an accepted MOC proposal doc (rendered by
> `suggestions-reducer.py --moc-proposal-mode`) into the
> `parsed-suggestions.json` that `instruction-render.py` reads. The
> synthesis conductor calls it for every `doc_type: moc-proposal` entry.

## One Section Kind Per `### MOCxx` Block, Two Item Kinds Out (spec 042, SDD ADR-5)

An `around:<MOC>` run proposes the missing members of an existing MOC. The
reducer renders that as an extension section in the same doc type:

```
### MOC01 — Extend [[Health MOC]]
- [ ] Accept
**Extends:** [[Health MOC]]
**Trigger:** around:Health MOC
#### Missing members (2)
- [ ] [[Cold Showers]] (no up:: yet) — linked with [[Health MOC]]
- [ ] [[Sleep Debt]] (existing up:: [[Psychology MOC]] → becomes `related::`) — linked with [[Health MOC]]
#### up::-Handling Override
- [ ] **Keep existing up::, add [[Health MOC]] as `related::`** (applies to all ticked members)
```

WHY the heading stays `### MOCxx`: `_split_moc_blocks` starts a block only at
a `### MOCxx` heading. Any other heading (`### EXT01`, `### Extend …`) is not a
block boundary, so its lines would be appended to the previous MOC block and
its members would become that new MOC's children. Keeping `MOCxx` also leaves
the doc type, the state promoter's Accept regex, inbox-triage and the
eval-gated conductor untouched. The cost is that `MOCxx` no longer implies
"create".

WHY the parser branches on the `**Extends:**` line, not on the title text or
the frontmatter: the line belongs to the section, so a doc that mixes an
extension with new-MOC sections still parses each block on its own. The
heading title is user-visible text, and the frontmatter's
`proposal_kind: moc-extension` describes the whole doc, not one block.

WHY an extension emits `action: "extend_moc"` with no `template` and no
`destination`: there is no note to create. `instruction-render` renders a file
only for items with a template; a template-less item skips the render loop and
the manifest. `extend_moc` is expanded into `add_relationship` + `link_to_moc`
from `confirmed` later (render_actions), never written to the wire as its own
action. A template or destination key would make the renderer try to create
a note named after the MOC.

WHY `#### Missing members` is read like `#### Children`: the member lines have
the same contract (ADR-7) — the member wikilink is first and the
` — linked with [[A]]` suffix comes after it, so the first wikilink on a ticked
line is the member. Only ticked lines become `supporting_items`.

WHY the Override section is read unchanged: the extension's toggle text
("Keep existing up::, add [[X]] as `related::`") carries `keep`, the same
keyword the new-MOC toggle is matched on. Members are then handled by the
same up-preservation rules as a new MOC's children (PRD F1-AC5).

## An Accepted Extension With No Ticked Member Is Skipped and Reported

WHY: Accept with zero ticked members asks for nothing — there is no note to
give `up::` and no line to add to the MOC. Passing it on as `extend_moc` with
an empty list would yield an item that produces no action, and the
instructions-diff gate cannot tell "nothing asked" from "something lost". The
section goes to `skipped` with `disposition: "no_ticked_members"` and a
`reason`, and the CLI prints one stderr line naming the section and the MOC,
so the user learns why their Accept had no effect. The disposition is
deliberately neither `skip` nor `delete_source`: those two drive `skip` and
`delete_source` actions on an inbox source, and an extension has no source.

A rejected extension (Accept unticked) goes to `skipped` with
`disposition: "rejected"`, like a rejected new-MOC section. It is never
squelched — see `docs/tomo/scripts/suggestion-parser.md`.
