# WHY: lib/duplicate_proposals.py

> Rationale for decisions in `tomo/scripts/lib/duplicate_proposals.py`.
> The reducer's deterministic backstop against offering to create a MOC the
> vault already has (spec 040 ADR-6, PRD F4).

## Why a reducer backstop when the analyst is told not to

Spec 040 gives the analyst the names of all eligible MOCs and tells it not to
propose one that exists. That is an LLM instruction, and before spec 040
nothing checked a proposal against the vault at all (PRD, "No duplicate MOC
proposals"). The two baseline runs happened to produce no duplicate, so the
backstop answers a risk, not a measured rate: the analysis skipping the
existing-name check (PRD risk table). A deterministic check runs after the
analyst, in the one place every action passes once: the reducer's action loop.

It is equality-only by design. A near-duplicate ("Urlaub" against
"Vacation (MOC)") or an alias-only match passes it: merging on similarity
would make wrong merges silently, and the analyst instruction stays the
primary guard. The owner still decides on every Proposed MOC.

## Why one mutation per action, before render

The same action feeds three consumers: the markdown block (`render_create_atomic_note`),
the persisted candidates that become the C3 wire (`persist_candidate_anchors`),
and the Proposed-MOC cluster collection. Mutating the action once, before any
of them, makes all three agree by construction. The precedent is
`demote_structural_anchors` (#71), which sits next to it for the same reason.
Correcting each consumer separately would be three places to keep in step.

## Why the cluster key, on both sides

`build_topic_clusters` already decides which proposals are "the same MOC" with
`normalise_topic(strip_moc_marker(x, suffix))`. Using that exact key for the
duplicate check means "Vacations", "vacation" and "Vacation (MOC)" meet, and a
two-item cluster ("Project", "Projects") is converted all-or-nothing — never a
Proposed MOC fed by half its items while the other half links the existing
one. A second normaliser would let the two decisions disagree.

## Why every colliding path, unticked, appended

Two eligible MOCs can share a title ("Projects" in the MOC folder and in a
project area). The mutator cannot know which one the analyst meant, so it
offers all of them. They are unticked (`pre_check: false`, `score: 0.0`) and
carry no anchor: the analyst never placed the note in them, so ticking them
would claim a decision nobody made. They go after the analyst's own
candidates, so its first choice stays first, and a path already listed is not
added twice.

## Why only eligible thematic MOCs

Eligibility (the `MiYo/Tomo/exclude/moc` tag) is decided once, by the
shared-ctx builder; the mutator reads the context and never re-derives it, so
an excluded MOC cannot be re-offered through this back door. Classification
(Dewey) MOCs are skipped: a thematic proposal is not a duplicate of a
classification bucket, and the Classification Guard keeps those for
classification links.

## Why suppressed atomics are skipped

A sub-worthy atomic (#88) renders as "kept in inbox" with no MOC framing and
never seeds a Proposed MOC. Converting it would add candidates nobody sees and
count a conversion that changed nothing the owner reads.

## Why fail-open

Without a readable context the mutator returns `{}` and nothing converts —
exactly the reducer's behaviour before spec 040. A missing context is already
an aborted run upstream; the reducer should not add a second failure on top.

## Deviation from the SDD signature

The SDD lists `load_eligible_mocs(shared_ctx_path)`. The cluster key depends on
the profile's MOC suffix, so the function takes it as a second argument rather
than keying on an unstripped title and re-keying later.
