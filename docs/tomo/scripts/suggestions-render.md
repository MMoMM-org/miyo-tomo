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
