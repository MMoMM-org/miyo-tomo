# WHY: scripts/shared-ctx-builder.py

> Rationale for decisions in `tomo/scripts/shared-ctx-builder.py`.
> Builds the per-run `shared-ctx.json` envelope that every Phase-B
> `inbox-analyst` subagent reads. Only decisions with a non-obvious WHY are
> recorded here; the script docstring + `--help` cover usage.

## `build_placeholder_links` Filters to the MOC Naming Convention (Condition C)

WHY: `moc-tree-builder` detects **every** dead wikilink in MOC bodies — a
placeholder link in the general sense. A dead link may point to a missing MOC
**or** to a missing regular note. `inbox-analyst` Condition C uses this list to
offer MOC *creation* ("you linked `[[X]]`, want me to create that MOC and link
this item?"). Offering MOC creation for a dead link that was never meant to be a
MOC is the same over-detection bug as the date links — only larger.

T4.3 live validation (2026-06-09) measured it on the real vault: of 196 unique
placeholder targets, only **38** followed the vault's MOC naming convention
(`(MOC)` parenthetical or a trailing ` MOC` word). The other 158 were missing
regular notes — `$ Körperliche Fitness 2024`, `011 Index`, bare topic names —
which Condition C must not propose as MOCs.

The filter lives **here, at the Condition C feed**, not in the cache and not in
the detector:
- The cache (`moc-structure-cache.yaml`) stays a complete dead-link record —
  detection remains the general "all placeholder links" primitive (the user's
  terminology: they ARE placeholder links; only the `(MOC)`/` MOC` ones are
  missing MOCs).
- Filtering at the feed keeps the shared-ctx envelope lean (M6) — the 158
  non-MOC links never multiply across N analyst subagents.
- Condition C (the sole consumer) only ever sees genuine missing MOCs, so it
  cannot propose a MOC for a missing regular note.

`_MOC_NAME_RE` uses `\bMOC` so a mid-word "...MOC" (e.g. `COMMOC`) never matches;
the match is case-insensitive and anchored at end-of-string so `[[X (MOC)]]`,
`[[X MOC]]`, and `[[x moc]]` all qualify while `[[X MOC Notes]]` does not. The
convention is currently hardcoded (matches the date-filter precedent in
`lib/placeholder_detect`); promote to vault-config if a vault needs a different
MOC marker.
