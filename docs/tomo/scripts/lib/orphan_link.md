# WHY: lib/orphan_link.py

> Rationale for decisions in `tomo/scripts/lib/orphan_link.py`.
> The module is the case-(a) orphan pass: for every cache entry whose `up_state`
> is "absent", it proposes either linking to an existing MOC or creating a new one.

## Case-(a) Orphan Pass Is a New Pass — Not a Phase-6 Edit (H2)

WHY: moc-discovery.py Phase 6 runs a `duplicates_skipped` deduplication step
that filters clusters against existing MOCs. H2 explicitly prohibits modifying
that step. The orphan pass is logically separate: Phase 6 asks "are these
clusters already covered by a MOC?"; the orphan pass asks "does this individual
note/MOC have a parent at all?". Conflating them would break the Phase-6
contract and would mix two different units of work in one code path. The orphan
pass runs AFTER the cache is loaded and Phases 1–6 have produced their cluster
results; it reads `cache.entries` directly.

## Orphan MOCs Are Eligible — No Relaxation of `restrict_to_atomic_note_paths` (H3)

WHY: An orphan MOC (a MOC with `up_state == "absent"`) is an entry in the
cache, and the cache is already scoped to configured paths. Treating MOCs as
eligible orphans requires no change to `restrict_to_atomic_note_paths` in
moc-discovery.py — that guard applies to Phase-1's atomic-note pre-filter on
the clustering path, which this module does not touch. H3 documents this
explicitly to prevent future reviewers from assuming MOC-eligibility implies
a permission relaxation.

## Local Scorer to Avoid Circular Import

WHY: The same keyword-overlap approach used in Phase 5/6
(`|overlap| / |orphan topics|`) is reimplemented locally here rather than
imported from moc-discovery.py. moc-discovery.py is this module's CALLER;
importing it would create a circular import (orphan_link ← moc-discovery ←
orphan_link). The local `_overlap_ratio` function uses the same denominator
(orphan topic count) and the same threshold (0.5) as the production scorer, so
results are consistent across the two paths. Keeping the scorer here also makes
unit-testing the orphan pass independent of moc-discovery's full module state.

## Top-3 Candidates, DESC by Score (OQ-4)

WHY: When multiple existing MOCs score above the link threshold, the user sees
at most three link candidates, sorted by overlap ratio descending. OQ-4
established the cap to keep the proposal-doc readable — more than three
candidates is noise. The self-exclude guard (`moc.get("path") == orphan_path`)
prevents an orphan MOC from being offered as its own link target, which would
be a trivial circular reference.

## `create_new` Reason String — Distinguishes No-Overlap from Below-Threshold

WHY: When no MOC clears the link threshold, the reason string distinguishes two
cases: "no existing MOC shares any topics" vs "topics matched but no MOC was
above the threshold." The distinction is actionable for the user: the first
case suggests the topic is genuinely novel (a new MOC is likely warranted); the
second suggests an existing MOC is close but not close enough (the user may
want to check the candidates manually). Both cases still emit `mode="create_new"`,
so the proposal-doc renderer treats them identically for instruction generation.
