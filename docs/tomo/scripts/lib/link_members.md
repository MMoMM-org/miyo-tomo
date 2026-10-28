# WHY: lib/link_members.py

> Rationale for decisions in `tomo/scripts/lib/link_members.py` (spec 042,
> `/moc-propose` finds MOC members through the link graph).
> The module decides which `kado-graph` neighbours may become "link members" of a
> proposed MOC. This page covers `NodeEligibility`.

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

Two sibling readers resolve atomic-note paths too: `moc-discovery.py`
`_atomic_note_paths` and `lib/moc_scan.read_scope_paths`. A change to how
atomic-note paths are resolved must check all three.

## Reasons Are Returned, Never Logged

WHY: Out-of-scope paths can belong to sensitive folders (Constitution: vault
content is sensitive; audit metadata only). The module neither prints nor logs;
callers aggregate reason counts and never emit the path of an out-of-scope node.
