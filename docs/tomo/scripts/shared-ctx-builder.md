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

## `build_asset_folder` — threading `concepts.asset` to a process that can't read config (spec 031)

WHY `concepts.asset` is read HERE and written into `shared-ctx.json` as
`asset_folder`, rather than `suggestions-reducer.py` reading `vault-config.yaml`
directly: the reducer has never had a `--config`/`--vault-config` argument — only
`instruction-render.py` does, at instruction-render (Pass-2 apply) time. But the
suggestions document (Pass 1, which the reducer produces) needs to tell the user
where attachments will be filed BEFORE they approve — see
`suggestions-reducer.md`'s "destination is a run-level preamble" note for the full
reasoning. `shared-ctx-builder.py` already reads `vault-config.yaml` once per run
and already writes an envelope the reducer already loads (previously only for the
tracker field→section map); adding one more resolved value to that existing
envelope avoids building a second, parallel config reader for one string.

WHY the default is imported (`from lib.render_actions import
DEFAULT_ASSET_FOLDER`) rather than restated as a literal: `render_actions.py` is
where the destination is ACTUALLY used to build a `move_asset` action's real
destination path (`_asset_dest_join`). A second hardcoded copy of
`"Atlas/290 Assets/295 Attachments/"` here would be a duplicate literal that could
drift from the canonical one — exactly the DRY/SSoT violation this repo has
explicitly rejected elsewhere in this same spec (the `KNOWN_FILE_EXTENSIONS`
relocation, see the spec's decision log). Importing the dotted `lib.render_actions`
module requires the script's own directory on `sys.path` (`sys.path.insert(0,
str(SCRIPT_DIR))`) — distinct from the existing `sys.path.insert(0, str(SCRIPT_DIR
/ "lib"))` used for the BARE-name `kado_client`/`profile_conventions` imports;
both insertions coexist without conflict.

WHY `build_asset_folder` normalises with `folder.rstrip("/") + "/"` (matching
`_asset_dest_join`'s own normalisation exactly), not just `.strip()`: a configured
`concepts.asset` value without a trailing slash (or with a doubled one) would
otherwise make the shared-ctx envelope — and therefore the rendered preamble line —
name a DIFFERENT string than the one `_asset_dest_join` actually builds the real
destination from at apply time. The document would tell the user one folder while
the file lands in another, with nothing erroring — the same "document says one
thing, vault does another" failure class this spec exists to close, just moved one
layer up into the destination string itself instead of into a missing action.
Every existing vault-config value happens to carry a single trailing slash by
convention, which is exactly why this was easy to miss and worth normalising
defensively rather than trusting the convention to hold.

## Why the budget only sheds derived data (changed 2026-09-13)

`enforce_budget` used to run seven passes. The first four trimmed tracker
descriptions to 200 characters and then emptied `negative_keywords`,
`positive_keywords` and `keywords` — **before touching a single MOC**. Only
then did it start on `editable_callouts`, headings and topics.

That ordering was backwards on every axis:

- **What it shed.** Keyword lists are entered by a person through
  `tomo-trackers-wizard` and are the entire basis of tracker matching. MOC
  inventory is derived from the vault and rebuilt on the next
  `/explore-vault`. Shedding the irreplaceable to protect the regenerable.
- **Where the weight is.** Measured on the live instance 2026-09-13: `mocs`
  held **77%** of a 38.6 KB context (29.7 KB across 64 entries) while every
  tracker field together held 9.6%. The keyword lists inside that are a
  rounding error — emptying all fifteen bought about 1.1 KB.
- **How it failed.** Silently. Nothing logged, nothing validated, and the
  analyst's fallback degrades without complaint. The observable effect was
  that trackers stopped matching, which reads as a classification problem
  rather than a configuration one.

It was firing constantly, not at some rare extreme: untrimmed the same context
was **42104 bytes** against a 40960 budget, so it emptied the keyword lists on
every single run. The user's account — "the trackers worked and then the
keywords were gone" — is exactly this crossing the threshold as the vault grew.

The passes are now: `editable_callouts`, then headings greedily per MOC, then
topics. All three are derived, so shedding them costs a re-derivation and
nothing else. On the same live data the budget is met at 38935 bytes with all
fifteen tracker fields keeping their keywords.

**If the budget cannot be met** after shedding everything derived, the builder
now says so on stderr instead of silently emitting an oversized file. That is
the honest failure: `shared-ctx.json` is read by *every* subagent, so its bytes
are multiplied by the fan-out — twelve times in a normal run — and the fix is
either less MOC inventory or a deliberate `--max-bytes`, not quietly deleting
someone's configuration.

## Why `warn_unusable_trackers` keys on positive_keywords alone

`_seed_keywords` derives `keywords` from the field name, so that list is never
empty. But the analyst's matching rule reads `positive_keywords` and nothing
else — `keywords` reaches the context and is read by no one. Counting it in the
warning would silence the check on precisely the configuration it exists to
report: fifteen fields with seeded keywords, no positive keywords, and no way
to match anything.

The warning stays quiet when `trackers_enabled` is false or a field's `active`
is false. "I do not use trackers" is a configuration, not a gap, and a warning
that fires on a deliberate choice is one people learn to ignore.
