# Domain — Tomo
<!-- Business rules, data models, entities, domain language. Updated: 2026-06-09 -->
<!-- What goes here: what X means in this codebase, business rules that drive code decisions -->
<!-- Entries that appear frequently may be promotable → run /memory-promote -->

## MOC naming convention (owner's vault)
A wikilink names a **MOC** when its target ends with `(MOC)` (parenthetical) OR a
trailing ` MOC` word — e.g. `[[AI MOC]]`, `[[Efforts (MOC)]]`. A bare topic name
(`[[Boardgames]]`) is a regular note, NOT a MOC. Encoded in
`shared-ctx-builder._MOC_NAME_RE` (`\bMOC` word-boundary, case-insensitive,
end-anchored). Drives the Condition C placeholder feed (021 T4.3, 2026-06-09).

## "placeholder link" vs "missing MOC" (terminology)
A **placeholder link** = any dead `[[wikilink]]` in a MOC body (detected by
`lib/placeholder_detect`, stored complete in the cache). It MIGHT point to a
missing MOC OR a missing regular note. Only the subset matching the MOC naming
convention above are **missing MOCs**. Condition C (offer MOC creation) consumes
only that subset — filtered at `shared-ctx-builder.build_placeholder_links`, not
in the cache. Do not call the whole dead-link list "missing MOCs".

## Periodic notes are never placeholder MOCs
Date-shaped targets (`YYYY-MM-DD` daily, `YYYY-Www` weekly, `YYYY-MM` monthly)
resolve to real daily notes that live outside the MOC `scope_paths`, so they
leak as dead links unless excluded. `lib/placeholder_detect._is_periodic_note_target`
drops them at detection (021 T4.3). Year-themed MOCs with a suffix (`2024 Goals`)
are unaffected (regex is hyphen-anchored).
