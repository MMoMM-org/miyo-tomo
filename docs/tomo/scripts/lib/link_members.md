# WHY: lib/link_members.py

> Rationale for decisions in `tomo/scripts/lib/link_members.py` (spec 042,
> `/moc-propose` finds MOC members through the link graph).
> The module decides which `kado-graph` neighbours may become "link members" of a
> proposed MOC. This page covers `NodeEligibility`, `LinkLookup` and
> `augment_clusters`.

## Eligibility Rule (SDD ADR-3)

WHY: A linked note may become a link member only when ALL of these hold:
`.md` path; under the atomic-note paths; not in the inbox; not a periodic note;
not a MOC; not tagged `MiYo/Tomo/exclude/note`; present in the discovery cache.
`check(path)` returns `(eligible, reason)` where `reason` is a fixed token
(`ok`, `not-md`, `inbox`, `periodic`, `moc`, `out-of-scope`, `excluded-tag`,
`uncached`). Checks run in that order, so the most specific cause wins: a path
that is both periodic and uncached reports `periodic`, because "this can never
be a member" is more useful to the caller than "we have not seen it yet".

## Offline, From the Cache

WHY: The MOC-structure cache already holds every in-scope note with its tags and
up state, and the profile plus vault-config already name every excluded folder.
Deciding eligibility from those costs zero Kado calls, which matters because the
lookup budget (ADR-4) is spent on `kado-graph` calls and Kado rate-limits per IP.
Trade-off: a note created since the last cache build is skipped (`uncached`) until
the next build. Skipping is the safe side: a missing proposal costs the user
nothing, a wrong one costs a review decision.

## Uncached Nodes Are Skipped, Not Fetched

WHY: Reading an unknown note to classify it would add one call per unknown
neighbour and reintroduce the unbounded fan-out the budget exists to prevent.
Callers count the `uncached` reasons instead of reading the notes.

## Periodic Notes and MOCs Are Neither Members Nor Bridges

WHY: Daily, weekly and other periodic notes are hubs that link everything written
that day. Live probing showed every 2-hop result of a plain note arriving through
a daily or weekly note. If a daily counted as a bridge, any two notes written the
same day would look linked. MOCs link their members by design, so they would make
siblings look linked through the very structure being proposed. Both are
therefore excluded both as proposals and as bridge nodes; callers use
`is_periodic` / `is_moc` for the bridge side.

Periodic scope is the union of the profile `concept_defaults.calendar`
(`base_path` + every `granularities.*.path`), the vault-config
`concepts.calendar` of the same shape, and the vault-config
`tomo.moc_structure_cache.exclude_paths`. Disabled granularities stay in the set:
their folder may still hold old periodic notes.

## Path Normalisation

WHY: Vault-config values can carry a trailing space (`"Calendar/301 Daily/ "`,
see moc_scan OQ-5). `moc_scan` compares such prefixes verbatim to match the
cache builder; here a space-padded prefix would silently match nothing and let
dailies through, so every prefix is stripped and given a trailing `/` before
matching.

## Where Scope Comes From

WHY: Layer precedence is User Config > Profile. The atomic-note paths and the
inbox path are read from vault-config `concepts.atomic_note` / `concepts.inbox`
when set, else from the profile `concept_defaults.atomic_note` (base path plus
subdirectories) / `concept_defaults.inbox`. MOC detection ORs three signals
(cache `kind == "moc"`, the cache's `map_notes`, the profile's `map_note`
`name_suffix`, read through `profile_conventions.moc_suffix`) because each alone misses a real case: a
note tagged as a MOC outside the map folder, a suffix-named MOC the tag scan did
not see, a cache entry typed by the builder.

WHY the MOC suffix comes from the profile only: the vault-config schema has no
`map_note.name_suffix` key (`tomo/config/vault-example.yaml` `concepts.map_note`
carries only paths and tags), so there is nothing to layer over the profile value.

WHY a null vault-config concept falls back to the profile: `concepts.atomic_note`
or `concepts.inbox` set to null is treated as absent here and the profile default
applies. That is the safe side for scope (narrower than no scope at all).
Siblings differ: `moc-discovery.py` `_atomic_note_paths` reads the profile only and
never looks at vault-config; `lib/moc_scan.read_scope_paths` reads vault-config
only and treats null as absent with no profile fallback (an empty scope).

Two sibling readers resolve atomic-note paths too: `moc-discovery.py`
`_atomic_note_paths` and `lib/moc_scan.read_scope_paths`. A change to how
atomic-note paths are resolved must check all three.

## Reasons Are Returned, Never Logged

WHY: Out-of-scope paths can belong to sensitive folders (Constitution: vault
content is sensitive; audit metadata only). The module neither prints nor logs;
callers aggregate reason counts and never emit the path of an out-of-scope node.

## Link Lookups (SDD ADR-1, ADR-4)

WHY `neighbors`: a link member is found through `kado-graph` `neighbors`
(deduplicated outgoing and backlinks, source excluded). Direction does not matter
for "these notes are linked"; it matters only for "the MOC already links it",
which uses `outgoing` elsewhere.

WHY `limit` is never passed: Kado applies `limit` BEFORE its scope filter, so a
limited answer can silently drop in-scope nodes behind out-of-scope ones. The full
list is requested and filtered here.

WHY memoised by path: clusters share members. A second cluster containing A reuses
`neighbors(A)` without a call. A failed lookup is memoised too: asking again would
spend budget on a note that just failed, and every cluster containing it is marked
`failed` the same way.

WHY the budget counts HTTP attempts, not lookups: Kado rate-limits per IP and
counts every request, retries included (20 per 5 s, shared with the container).
`LinkLookup` reads `KadoClient.attempt_count` deltas, so a 429 retry costs budget
like any first send. The budget is 60 attempts per run; sends are paced at least
0.3 s apart. Both are module constants (`LOOKUP_BUDGET`, `LOOKUP_PACING_S`), not
config keys.

WHY the gate is installed on the client: the pre-check per cluster counts
lookups, which is a lower bound on attempts. Retries can still spend the rest of
the budget mid-cluster. `LinkLookup` therefore installs `client.attempt_gate`, so
the client refuses the send that would exceed the budget (`KadoBudgetExhausted`,
nothing sent) instead of the run overrunning it.

WHY gate and pacing install on enter, not on construction: a `LinkLookup` that is
built but never entered or closed would otherwise leave its gate on the client for
good. Installation happens on `__enter__` (or lazily on the first `neighbors`
call, so an unentered use is still budget-gated) and `close()` restores. Callers
that do not use the `with` block must call `close()` after `neighbors()`,
otherwise the gate stays installed on the client.

WHY the settings are restored on close: the client's gate applies to every Kado
tool, not only graph. Left installed, the 61st attempt of any later read, search
or write on the same client would raise `KadoBudgetExhausted` and be paced.
`LinkLookup` therefore installs gate and pacing for its lifetime and restores the
previous values on `close()` (idempotent). Callers use
`with LinkLookup(client) as lookup:`; the budget is per run, not per cluster, so
one lookup spans all clusters of the run.

## Augmenting Clusters (SDD Complex Logic)

WHY all-or-nothing per cluster: a cluster whose uncached lookups exceed the
remaining budget is skipped whole (`skipped_budget`) before any call. Half a
cluster's lookups would yield link members found through some members only,
which looks complete but is not. Skipping continues to the next cluster: a
smaller or already-cached cluster may still fit.

WHY an unmapped stem is `failed`: a cluster stem missing from `stem_to_path` is a
caller bug. Dropping it would score the cluster on a partial member set and still
report `done`, which looks complete but is not. The cluster gets no link members,
no `neighbors` call is made for it, and other clusters are unaffected. Raising
would abort the whole run over an optional enhancement.

WHY a mid-cluster budget stop is `skipped_budget`: when the gate refuses a send
inside a cluster (retries spent what the pre-check could not foresee), that
cluster's answer is incomplete, so it gets no link members. Its status is
`skipped_budget`, not `failed`, and it is counted in `clusters_skipped_budget`:
the cause is the budget, not a Kado fault, and the PRD requires the user to see
budget skips on the Discovery line ("(S skipped: budget)"). Only a `KadoError`
lookup failure is `failed`. The rest of the proposal is unchanged.

WHY `lookups` counts sends made: a lookup the gate refused before its first send
did not reach Kado, so it is not counted; a successful lookup and a `KadoError`
one are. `attempts` and `lookups` then agree on what "spent" means.

WHY two members (threshold 2): one link is common and weak; a note linked from
two or more members of the same topic is a member the topic missed. A node that
is already a topic member is never added again.

WHY the hub rule (no bridge): a neighbour is counted only when `NodeEligibility`
accepts it. A daily note linking A and B never becomes a member and never raises
anything's count, so two notes written on the same day do not look related.

WHY up state comes from the cache: each link member carries the cached `up_state`
and `up_target` so the renderer can show an existing `up::` without a read.

WHY the caller slices: `augment_clusters` receives only the rendered slice
(`clusters[:max_results]`). Marking the rest `not_rendered` is the caller's job,
so no lookup is ever spent on a cluster the user will not see.

WHY `LINK_MEMBER_MARKER` (` — linked with `) is a shared parse contract (ADR-7), not
display text: it is never localised. The reducer renders every link member line with
it, and `suggestion-parser` recognises the same constant to exclude marked lines from
the squelch signature, so link members never change a proposal's identity. Changing
the string breaks both consumers at once. See `suggestions-reducer.md` (link members
render after topic members) and `suggestion-parser.md`.
