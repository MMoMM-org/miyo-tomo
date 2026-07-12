# WHY: scripts/suggestions-render.py

> Rationale for decisions in `tomo/scripts/suggestions-render.py`.
> This renderer is a pure consumer: it turns `suggestions-doc.json` (produced by
> `suggestions-reducer.py`) into the human-facing review markdown the user reads.

## MOC-suffix in the Proposed-MOCs fallback comes from the doc's `conventions` block (spec 028, F-55)

WHY: `render_proposed_mocs` prints a MOC's display name as `pm["name"]` when the
reducer set one, and falls back to constructing a name from the topic when it
didn't. That fallback used to hardcode `f"{topic} (MOC)"` — the miyo suffix —
which would print `" (MOC)"` even for a profile (e.g. lyt) whose convention is a
plain title. This was a seam the original spec-028 seam-map missed; caught by the
Phase-4 seam grep.

Fix: the fallback now reads `moc_suffix` from the top-level `conventions` block
that `suggestions-reducer.py` writes into `suggestions-doc.json` (spec 028 Phase 2),
and applies it via `lib.profile_conventions.ensure_suffix(topic, moc_suffix)`.

WHY read the suffix from the input doc, not re-resolve the profile here: this
script is a pure renderer with no `--config`/`--profile` channel. The reducer
already resolved the active profile's conventions upstream and stamped them into
the doc; the renderer must consume that same resolved value, not independently
re-derive it (single source of truth — the doc is the contract).

WHY the default is `""` when the `conventions` block is absent (older artifact):
an empty suffix is the safe no-op — it never invents a `" (MOC)"` a vault does not
use. `ensure_suffix` additionally guards apply-once, so a topic that already ends
in the suffix is not double-suffixed. Under miyo (`moc_suffix == " (MOC)"`) the
output is byte-identical to the previous hardcoded literal.

## WHY `build_wire_payload` remaps `member_ids` from section-space to flat-space (ADR-026)

WHY: the reducer runs TWO independent S-id counters. `section_id = S{source_idx}`
(`suggestions-reducer.py:1576`) counts every SOURCE — including daily-only ones,
which consume an index but emit no atomic. `suggestion_id_flat = S{counter}`
(`:1702`) counts only ATOMIC notes. proposed_mocs `items` are built in the
section-space (`:1735/1745`, via `_atomic_id`), while each wire suggestion is
keyed by its flat `suggestion_id` (`_wire_note`, `sid = action["suggestion_id"]`).
When a daily-only source sits between atomics the two spaces diverge, so copying
`items` verbatim into `member_ids` made a member point at the WRONG suggestion
(the Cooking-MOC off-by-one: item `S14` = *Japanische Gerichte* in section-space,
but `S14` = *Knowledge Management* in the wire's flat space; the note's real flat
id was `S13`). The tag `topic/japan` — computed from the true member — contradicted
the member id, which is the tell.

Fix: build an `atomic_key → suggestion_id` map that mirrors the reducer's
`_atomic_id` keying (bare `section_id` for the 0th atomic, `section_id#idx` for
F-41 multi-atomic sources) and remap `member_ids` through it. The wire is then
self-consistent — every `member_id` references one of its own `suggestions[].id`.
The fan-resolve doc never drifted (its sources are all atomics, so
section-space == flat-space), which is why only the primary wire showed the bug.
Scope: this fixes the ADR-026 JSON wire (Hashi's active flow); the markdown Pass-2
path resolves proposed-MOC members by note title, not by these raw ids.
