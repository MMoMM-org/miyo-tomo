# WHY: lib/review_state.py

> Rationale for decisions in `tomo/scripts/lib/review_state.py`.
> The module is the only owner of the open-review states of `/review`
> (spec 045, SDD Complex Logic `review_state`, ADR-2, ADR-6): the canonical
> state list, the one function that classifies a review document, the
> content-free `meta.json` reader and the listing `start` prints.

## WHY One Function Owns the States

WHY: SDD Internal API Changes names six canonical states (`open`,
`failed-delivery`, `delivered`, `applied`, `move-refused`, `target-missing`)
and three readers of them: `review-session.py start` (the listing),
`review-instructions.py status` (one stem) and the skill's offers. A state
computed in two places drifts: `start` would call a review "open" while
`status` calls the same stem "failed-delivery". `review_state` is the single
function; `STATES` is the single list; every caller imports both and never
spells a state itself.

## WHY Only `open` and `failed-delivery` Are Classified Now (T2.3)

WHY: the plan splits the algorithm: T2.3 ships steps 1 and 2 (a failed step
in `meta.json`, or an approved document without a set, is `failed-delivery`;
no set JSON is `open`); T4.3 adds steps 3–7, which need the set JSON's
`applied` flags and probes of the target and the inbox copy (ADR-6). The
function already takes `set_json`, `target_exists` and `inbox_copy_exists`
so T4.3 extends the body without touching a caller. A set JSON handed in
today raises `StateNotClassified`: returning a guessed `delivered` would
claim a delivery nobody verified, and a state outside the canonical list
would break the one-owner rule. The T2.3 lister never hands a set JSON in
(it has no probe yet), so the exception cannot reach a user; the raise is a
tripwire for T4.3, not a runtime path.

## WHY the Document Is the Source and `meta.json` Only Adds

WHY: ADR-2: the open state lives in the vault. The review document finds
itself by `tomo.doc_type=review` even when renamed, and its top-level
`review_period`, `review_kind` and `review_stem` keys say which review it
is. `meta.json` under `tomo-tmp/review/<stem>/` is content-free and may be
gone (a cleaned `tomo-tmp`, a new container home); it adds `failed_step`,
nothing more. A missing or unparsable `meta.json` therefore counts as
absent, never as an error: an approved document with no meta is
`failed-delivery`, which offers resume or drop — the honest answer when the
delivery's record is lost. A document whose frontmatter Kado cannot read or
that carries no `review_period` is listed under `skipped_review_docs` with
its reason rather than dropped: the vault is the source of truth and a
corrupted record must stay visible (design-for-corruption rule).

## WHY the Stem Falls Back to `<period>_review`

WHY: SDD Data Storage Changes fixes the stem as `<period-name>_review`.
A document written before `review_stem` existed, or one whose key the user
removed, still names its period; deriving the stem from it keeps `meta.json`
and the set JSON reachable instead of listing a review no later step can
act on.

## WHY the Listing Is Ordered by Period Start

WHY: SDD `OUTPUT: list ordered by period`. Weeks and months interleave
(`2026-W09`, `2026-03`, `2026-W13`), so the order is the period's first day
under the configured week rule, name as the tie-breaker; a period name the
rule cannot parse sorts last so the listing never hides it. The sort is
stable across runs, which lets the skill number the offers.
