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
`review-instructions.py status` (one stem; planned, Phase 4 T4.3) and the
skill's offers. A state
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
tripwire for T4.3, not a runtime path. `open_reviews` carries a one-line
code comment saying so, because a well-meant "read the set JSON too" edit
before T4.3 would turn the tripwire into an abort of the whole listing
(`StateNotClassified` escapes `start` as exit 1) — the comment names the
task that lifts the restriction.

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
under the configured week rule **and the configured name formats**, name as
the tie-breaker; a period name no format parses sorts last so the listing
never hides it. The sort is stable across runs, which lets the skill number
the offers.

`open_reviews` takes `formats` (merged over `period.DEFAULT_FORMATS`, the
same merge `period.parse_args` does) because the first version ordered with
the defaults alone, and the default week format `GGGG-[W]WW` carries ISO
tokens: `period.parse_name` applies the ISO rule to upper-case week tokens
whatever `rule` says (`iso-tokens-need-iso-rule`), so the configured rule
was silently ignored. Under a confirmed Sunday/1 setup with `gggg-[W]ww`,
`2027-W01` starts 2026-12-27 and belongs before the month `2027-01`; ordered
with `GGGG-[W]WW` it starts 2027-01-04 and lands after it. The T2.3 code
review caught this; `start` now passes `review_config.configured_formats`
together with the rule, so the listing counts weeks the way the request does.

## WHY the Kind Is Inferred by Parsing, Not by a Letter

WHY: a document without `review_kind` (written before the key existed, or
the key removed by the user) still needs a kind for the listing and for the
format its period is parsed with. The first version guessed `week` when the
name contained a `W`; that letter is an artefact of the default format, not
of the kind — a week named under `gggg.ww` (`2027.01`) carries no `W` and
was listed as a month, parsed under `YYYY-MM` and sorted last. The kind is
now the first kind, in `KINDS` order (week before month), whose configured
format parses the name; a name no format parses falls back to the letter
guess so the listing still shows a kind for it. Week first because a name
that parses under both (a week format `gggg-ww` and the month format
`YYYY-MM` both accept `2027-01`) is an ambiguity the frontmatter normally
settles; the fallback only has to be deterministic, and the SDD's listing
puts weeks first.
