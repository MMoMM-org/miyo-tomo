# WHY: lib/folder_homes.py

> Rationale for decisions in `tomo/scripts/lib/folder_homes.py`.
> The module finds folder-home MOCs and the notes they already hold. Phase 1 of
> `moc-discovery.py` drops those notes from its candidates, and
> `link_members.NodeEligibility` refuses them as link members (`folder-home`).

## Why Folder-Homes Exist

WHY: some vaults collect a folder's notes through a folder-home note, a MOC
named like its folder (`Atlas/202 Notes/2821 Quotes/2821 Quotes.md`) that lists
the folder with a Dataview table. Its notes carry no `up::`, so `/moc-propose`
saw them as orphans and proposed a new "Quote (MOC)" over all 63 of them
(2026-10-29). The Phase 6 duplicate checks could not catch it: the titles differ,
and the topic overlap with `2821 Quotes` scored 0.22 against the 0.80 threshold.
The folder-home's name cannot change to match, because it has to equal the
folder's name.

## Member Level, Not Cluster Level

WHY: the first fix (PR #220) skipped a whole cluster when at least 80 % of its
members sat in a folder-home folder. Live (2026-10-30) it removed every
pure-quote cluster, but single quotes still joined mixed clusters that stayed
under the threshold. "Have (MOC)" held 4 quotes and 2 code snippets, because
topics come from title words. A note the folder-home already lists needs no
second MOC, wherever it would cluster. So the decision moved to the note:
Phase 1 drops it before topic extraction and before the candidate cap, which
saves topic-extraction work and leaves room under the cap. The cluster-level
check in Phase 6 became dead code and was removed.

## Link Members Follow the Same Rule

WHY: spec 042 adds notes linked from at least two cluster members as link
members. A quote linked from two notes of a cluster would have come back
through that path. `NodeEligibility.check` therefore returns `folder-home` for
such notes, after `out-of-scope` and before `excluded-tag`. The same rule keeps
the notes out as bridges, and it applies to `--around` neighbours too.

## What Counts as a Folder-Home

- An existing MOC (cache `map_notes`) whose stem equals its folder's name,
  compared case-insensitively.
- A note belongs to it when its path lies in that folder or in a subfolder,
  matched on whole path segments: `2821 Quotes Archive/` is not inside
  `2821 Quotes/`. When homes nest, the deepest home is named.
- WHY the atomic-note root and its ancestors are excluded: they hold every
  atomic note. In the test vault, `202 Notes.md` and `Atlas.md` are named like
  their folders. Without the exclusion, every candidate would be dropped.
- WHY the roots come from `concepts.atomic_note` (scalar, `path`, `base_path`
  or `paths`) with the profile's `base_path` as fallback, and never from the
  profile's `subdirectories`: in the miyo profile those subdirectories
  (`2821 Quotes/`, `2611 Code Snippets/`, `2921 People/` …) are exactly the
  folder-home folders. Treating them as roots would disable the filter.
- Without any configured root, a vault-top home such as `Atlas/Atlas.md` would
  count. Every shipped profile defines `atomic_note.base_path`, so this case
  does not arise.

## Why a Drop and Not an Extension Proposal

WHY: the folder-home already lists these notes through its query. Proposing
`up::` links or list entries for them would duplicate what the vault already
shows.
