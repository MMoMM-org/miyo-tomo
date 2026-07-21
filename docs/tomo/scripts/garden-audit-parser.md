# WHY: garden-audit-parser.py

> Rationale for decisions in `tomo/scripts/garden-audit-parser.py`.
> The script is the Pass-2 READER for the garden-audit skill (spec 030 Phase 4).
> It mirrors `suggestion-parser.py`'s CLI + wire contract (ADR-4 / ADR-026):
> `--file <md>` is byte-authoritative, `--wire <json>` is an optional edited-wire
> override, and the result is a `{"confirmed_items": [...]}` envelope printed to STDOUT.

## Parser Emits confirmed_items, Not Actions (spec 030 SDD)

WHY the parser is a pure reader that emits SEMANTIC items (`garden_check` /
`garden_action`) instead of pre-built Hashi actions: the SDD mandates "no new apply
path… mirror /moc-propose". The suggestions and moc-proposal flows both hand
`confirmed_items` to `instruction-render.py`, which assembles actions via
`render_actions`. Garden-audit does the same. The action assembler lives in
`render_actions.build_garden_audit_actions`, which reuses the shared
`_build_edit_note_text_actions` builder (previously dead code) — wiring the fix
primitive into the one live builder path. An earlier design where the parser emitted
`{"actions": [...]}` directly was end-to-end broken: `instruction-render` reads
`confirmed_items`, so the actions were silently dropped and nothing rendered.

## Markdown Authoritative, Wire Overrides (ADR-026)

WHY `main()` reads `--file` → `build_from_markdown` by default and only takes the wire
path when `load_changed_wire` returns a non-None (edited) wire: Tomo never assumes Hashi
is installed, so the human-reviewed markdown report is the byte-authoritative source of
what the user approved. The vault-published wire sibling is an OPTIONAL override that only
wins when the user actually edited it (its embedded `emit_digest` no longer matches a
recomputation over the editable payload). Unchanged / absent / unreadable / unknown-version
→ the markdown path is used. This mirrors `suggestion-parser.py` exactly.

## Structural HTML Comment Round-Trip

WHY `build_from_markdown` reads a `<!-- garden-audit ... -->` comment per `### Fxx` block
rather than re-parsing the visible prose: the visible report is written for a human reading
in Obsidian (wikilinks, plain-language fix summaries) and hides the machine data (exact
`match` string, `occurrence`, resolved `target_moc_path`). The renderer emits an invisible
structural comment (invisible in Obsidian reading view) carrying exactly that data, so the
parser reconstructs the `confirmed_item` deterministically without brittle prose parsing.
The visible affordances the parser DOES read — the `- [x] Apply` checkbox and the
`**Replace with:**` / `**Repoint to:**` fields — are the user's decision surface; everything
else comes from the comment. Advisory findings carry NO comment, so they never produce an item.

## Regexes Use re.MULTILINE

WHY `RE_APPLY_*` / `RE_REPLACE_FIELD` / `RE_REPOINT_FIELD` compile with `re.MULTILINE`:
they are `.search()`-ed against a whole multi-line finding block. Without `re.MULTILINE`
the `^` anchor only matches the start of the entire block string, so every field line
except the first would be missed (observed: repoint/replace values silently read as empty,
collapsing every fix to a removal).

## broken_up Discriminator: Repoint Value Present ⇒ add_relationship

WHY a `broken_up` block renders a `**Repoint to:**` field only for the repoint variant,
and the parser branches on whether the user typed a target: a non-empty Repoint value means
"repair the `up::` to this MOC" (`garden_action=add_relationship`, `up_line` built from it);
an empty / untouched `[[]]` placeholder means "remove the broken line"
(`garden_action=edit_note_text`, `replace=""`). This keeps the two legitimate resolutions
(repoint vs remove) behind one clean discriminator the user controls by typing or not typing.

## Dead-Link Match Uses `[[target]]` Wrapping (ADR-3)

WHY the `dead_link` structural comment stores `match="[[<dead_target>]]"` (wrapped) while
the scan stores the bare stem: `edit_note_text` does a literal string match against the note
body, where dead links appear as `[[Missing Note]]`. The renderer wraps once when emitting
the comment, so the parser reads the ready-to-match string. `occurrence="all"` because a dead
wikilink is typically repeated; broken-`up::` removal uses `first` (one `up::` line per note).

## Filing Warns and Skips on No Candidate MOC

WHY a filing item is skipped (with a stderr warning) when no `target_moc` is present: a
filing action with an empty MOC stem would fail at apply time (Hashi cannot resolve or create
a MOC with an empty stem). An empty candidate list is a genuine "no good MOC found" signal,
not a parser error — the user handles the note manually.

## Version 0.2.0

WHY: Bumped from 0.1.3 for the vertical fix (spec 030 Feature 3). The parser was rewritten
from a wire-only action-emitter into a markdown-authoritative reader that emits
`confirmed_items`; action assembly moved to `render_actions.build_garden_audit_actions`.
`update-tomo.sh` skips unchanged versions.
