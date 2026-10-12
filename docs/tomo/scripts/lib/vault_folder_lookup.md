# WHY: lib/vault_folder_lookup.py

> Rationale for decisions in `tomo/scripts/lib/vault_folder_lookup.py`.
> One raw `list_dir` per vault folder, served to every reader: the Pass-1
> reducer's note, attachment and folder-occupancy views, the folder's
> `state()`, and Pass 2's `make_folder_listing` `.md` view. Only
> non-obvious decisions are recorded here.

## Moved to `lib/` and Shared With Pass 2 (spec 039 T1.4, ADR-2)

Until spec 039 the class lived in `suggestions-reducer.py` as
`_VaultFolderLookup`, and Pass 2 kept its own twin closure,
`render_actions.make_folder_listing`. The twin cached the `.md`-filtered map,
not the listing — exactly the trap the next section describes — so Pass 2
could not also answer an attachment question without listing every folder a
second time. Spec 039 needs Pass 2 to ask both questions of the same folder
(PRD F3-AC7: one raw listing per folder shared by every reader). Widening the
twin would have doubled the calls; the Pass-1 class already cached raw entries
and derived each view, so it moved to `lib/` and `make_folder_listing` became
a `.md` view over its cache (`make_folder_listing(client_or_lookup)` — hand it
the run's lookup to share the cache, or a client to get a private one).

The reducer keeps the name `_VaultFolderLookup` as an alias of
`VaultFolderLookup`; the spec 037 tests drive it by that name.

The path helpers it keys by (`_dest_join`, `_asset_dest_join`) moved with it
to `lib/vault_paths.py` (SDD K15): `render_actions` imports this module for
`make_folder_listing`, so the helpers had to live below both to avoid an
import cycle. `render_actions` re-exports them, so every existing import and
`render_actions._dest_join` lookup still resolves.

## `state()`: Absent Is Kado's `Path not found`, Nothing Else (spec 039 ADR-2)

A listing that fails used to read only as "empty" — fail-open, because an
error is not a collision, and that stays. Spec 039 also needs to know WHY a
folder lists nothing: a folder that does not exist yet is a known-free
destination (F2-AC8), while a folder Kado did not answer for is unknown and
must be reported "not checked" (F3-AC6). Treating the second as the first
would report a destination free that nobody looked at.

`absent` is only Kado's tool-level `NOT_FOUND` on `listDir`, whose message is
`Path not found: <path>` (Kado `search-adapter.ts:271`). `kado_client`
surfaces it as `KadoNotFoundError` — but it raises the SAME class for an HTTP
404 on the endpoint itself (a wrong `KADO_URL`, a misconfiguration that says
nothing about the folder). So the split reads the message, never the
exception type alone: classifying by type would turn a misconfigured server
into "every folder is absent, every destination is free". Every other error,
including a non-Kado one from a fake or a transport fault, is `unanswered`.
The message match is case-insensitive on `path not found`; the endpoint 404's
text (`Kado endpoint not found`) does not contain it.

`state()` reads the same cache the views do, so asking it costs no extra
round trip.

## The Counter Charges Pages, Including Failed Listings (spec 034 T6.1)

`folder_listing_calls` is read from the client's own round-trip counter
(`kado_client.observed_call_count`) rather than counted as one per cache
miss: `list_dir` pages internally, so a paged listing is several round trips.
The per-miss fallback applies only to a client that keeps no count. The
snapshot is taken after the `except`: a listing that raised still spent its
round trip. The name is kept because the reducer's output document and
`lib/cost_history.py` read it by that name.

## The Cache Holds the Raw Listing, Not the Derived Map (spec 037 T1.1)

Spec 037 needs the same per-folder `list_dir` cache T5.2 built to also answer
an attachment lookup — "is this destination already occupied" has to hold for
assets, not just notes. `_vault_folder_notes`'s body did two things in one
step: fetch-or-reuse the listing, and derive a `.md`-only `{destination:
path}` map from it. Generalising by parameterising that combined step (file
predicate + destination-join, still cached keyed on folder) would have cached
the *derived* map — so a folder the note caller primes first would hand the
attachment caller a `.md`-only dict for the rest of the run, and the
attachment lookup would find nothing. **Silently**: no exception, no second
`list_dir` call to notice, just an empty result exactly like "not occupied."
That is the failure mode this spec exists to remove, reintroduced by the
refactor meant to prevent it.

`_VaultFolderLookup` (module-level class, replacing the closure nested in
`main()`) splits the two steps instead: `_entries(folder)` is the only thing
that touches the cache, keyed on folder, storing the raw `list_dir` result
list. `notes()` and `assets()` both call it and then derive their own map —
`.md`-only via `_dest_join`, non-`.md` via `_asset_dest_join` — fresh, every
call, from whatever is in the cache. A second call for the same folder still
costs zero extra `list_dir` round trips (the entries are already cached); it
just costs a re-filter over an already-in-memory list, which is not a cost
`folder_listing_calls` was ever meant to count.

Hoisted to module level (it was a closure over `main()`'s locals — `kado_client`,
the cache dict, `folder_listing_calls`) so spec 037's test can drive it
directly, the same way `resolve_destination_clashes` already is, instead of
needing to run the whole reducer to exercise a lookup. `main()` now
instantiates one `_VaultFolderLookup(kado_client)` (or `None` when Kado is
absent/unreachable/`--fan-resolve`, unchanged from before) and reads
`folder_listing_calls` / `distinct_destination_folders` off it at the two
existing sites — behaviour unchanged, only where the state lives.

The note path is unchanged in output: `notes()` is the same filter
(`type == "file"` and lowercased name ends `.md`) and the same join
(`_dest_join(folder, name[:-3]).casefold()`) the pre-generalisation body used,
verified in `tests/test_037_t1_1_folder_cache_serves_attachments.py` against a
reproduction of that exact body, and against the spec 034 T5.2 suite passing
unmodified.

