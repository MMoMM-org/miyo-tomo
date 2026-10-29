# WHY: lib/instructions_diff_garden.py

> Rationale for decisions in `tomo/scripts/lib/instructions_diff_garden.py`.
> The garden-audit mode of the coverage audit. Split out of
> `instructions-diff.py` (#216). See `docs/tomo/scripts/instructions-diff.md`
> for the module map.

## Why a Separate Module

WHY: garden-audit envelopes carry `garden_action` items. Their count math
(`_GARDEN_EXPECTED_KINDS`) and their path-anchored per-item check differ from
the suggestions mode. `run_diff` routes to `run_diff_garden` by shape
(`_is_garden_parsed`), so the two modes share only the report envelope and
`_unresolvable_link_notes`. A separate module keeps the garden count math from
mixing with the suggestions math.

`run_diff_garden` prints its own `RESULT:` lines. Their wording matches the
suggestions mode except for the observation suffix. The conductor relays either
one verbatim.

The rationale for garden mode itself (versions 0.7.0 and 0.8.0) is in
`docs/tomo/scripts/instructions-diff.md`.
