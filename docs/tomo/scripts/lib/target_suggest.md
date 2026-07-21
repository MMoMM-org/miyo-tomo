# WHY: lib/target_suggest.py

> Rationale for decisions in `tomo/scripts/lib/target_suggest.py`.
> On-demand target candidates for the two typeable fixable garden-audit checks
> (spec 030 Phase 7, D3). Computed ONLY on a `/garden-audit --suggest`
> re-invocation for Suggest-ticked findings — never during the Pass-1 scan.

## Two functions, two candidate sources (D3)

WHY `dead_link` and `broken_up` use different scorers rather than one shared one:
they suggest fundamentally different things. `suggest_dead_link_targets` fuzzy-matches
the dead wikilink *stem* against all cache note stems — a dead link is almost always a
typo or a rename of a real note, so string similarity is the right signal.
`suggest_repoint_mocs` targets *MOCs*, so it merges two MOC-shaped signals: the note's
topic overlap with each MOC (a note that thematically belongs under a MOC) AND
stem-similarity of the broken up-target against MOC stems (a mistyped MOC name). A single
generic scorer would miss one of these halves.

## difflib, not a new dependency (D3)

WHY `difflib.SequenceMatcher` (stdlib) instead of a fuzzy-match library (rapidfuzz,
thefuzz): the constitution bounds dependencies, and a stem-similarity ratio is exactly what
`difflib` gives for free. `difflib.get_close_matches` was considered but `SequenceMatcher`
directly gives us the score we surface in the pick list (`(0.92)`), so we compute the ratio
ourselves and gate on the cutoff. Case-folded (`.lower()`) so a case-only typo scores 1.0.

## Reuse orphan_link._score_against_mocs (D3)

WHY the broken_up topic half imports `orphan_link._score_against_mocs` rather than
re-implementing topic overlap: it is the SAME "does this note belong under this MOC" scoring
that the unparented/orphan filing path already uses (topic-set overlap ratio, threshold-gated,
top-N). Reusing it keeps the two "suggest a MOC" surfaces consistent and avoids a second,
drifting copy of the overlap math. The note is passed as a pseudo-orphan (stem/path/topics),
exactly the shape that function expects.

## Merge by MOC stem, keep the higher score

WHY `suggest_repoint_mocs` dedupes by MOC stem taking `max(score)`: a MOC can match BOTH by
topic overlap AND by stem similarity (e.g. "Writing MOC" when the note is about writing and the
broken target was "Writng MOC"). Emitting it twice would waste a pick slot and confuse the user.
Taking the higher of the two signals surfaces the MOC once at its best score.

## Both signals are cutoff-gated (`stem_cutoff`, parallels the dead_link cutoff)

WHY signal 2 (stem similarity) has its own `stem_cutoff=0.6` and is NOT ungated: difflib's ratio
is inflated by the shared `` MOC`` suffix every MOC stem carries — `Writing MOC` vs `Cooking MOC`
≈ 0.64, `Writing MOC` vs `Running MOC` ≈ 0.73 — so an ungated stem signal made every unrelated MOC
a "candidate". The failure mode is worst when the note has NO topics: signal 1
(`_score_against_mocs`) returns `[]`, so the ungated stem signal alone fills all top-N slots with
confident-looking-but-wrong MOCs. Gating signal 2 at 0.6 (the same cutoff `suggest_dead_link_targets`
already uses) drops the suffix-only matches; a genuine mistyped MOC (`Writng MOC` vs `Writing MOC`
≈ 0.9) still clears it. The topic signal stays gated by orphan_link's own `LINK_THRESHOLD`.

## Deterministic tie-break (score DESC, then target ASC)

WHY both functions sort by `(-score, target)`: a suggestion pick list that reorders between two
`--suggest` runs on the same inputs would be a confusing, non-reproducible surface (and would
break byte-for-byte enrichment idempotency). Sorting ties alphabetically by target makes the
output byte-stable.

## Exact self-reference excluded (dead_link)

WHY `suggest_dead_link_targets` skips a stem that exactly equals the dead target: a dead link is
by definition unresolved. If a note stem exactly matched the link, the link would already resolve
— it would not be a dead-link finding. Suggesting the exact string would be a no-op fix. A case
variant (differs only by case) is still a distinct, high-scoring candidate and is kept.

## Version 0.2.0

WHY: 0.2.0 (code-quality review W1) — added `stem_cutoff=0.6` to `suggest_repoint_mocs`, gating the
stem-similarity signal so unrelated MOCs sharing only the `` MOC`` suffix no longer fill the pick
list (worst with a no-topics note). 0.1.0 initial Phase 7 (T7.1). `update-tomo.sh` skips unchanged
versions.
