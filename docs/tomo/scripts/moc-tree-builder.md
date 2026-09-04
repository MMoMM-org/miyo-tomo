# WHY: scripts/moc-tree-builder.py

> Rationale for decisions in `tomo/scripts/moc-tree-builder.py`.
> Rebuilt for spec 021 (T1.4): now the MOC-structure-cache builder that
> orchestrates `lib/moc_scan`, `lib/up_parse`, and `lib/placeholder_detect`.

## Rebuilt as MOC-Structure-Cache Builder, Not Just the Cache-Builder Feed (C2)

WHY: Before spec 021, moc-tree-builder.py produced only the
`cache-builder-shaped map_notes JSON feed` (stdout) consumed by `cache-builder.py
--mocs`. It had no separate output: the MOC-structure cache (`moc-structure-cache.yaml`)
did not exist. The rebuild adds a second, independent output: the
`MocStructureCache` YAML, a unified `entries` list with a `kind` discriminator
("moc" | "note"). This cache is what `moc_cache_loader` reads for `/moc-propose`.

The legacy stdout feed must continue to work (vault-explorer Step 9 calls
`moc-tree-builder.py > moc-output.json` then `cache-builder.py --mocs
moc-output.json`). C2 requires that `kind==moc` entries carry `classification`
and `linked_notes` as an int so `cache-builder.build_classifications` and
`build_scan_stats` keep working without modification. Both fields are always
present on moc-kind entries; `classification` stays `None` (faithful to the
legacy value and to the live cache — Dewey derivation is not in T1.4 scope).

## Dual-Output: stdout JSON Feed + `moc-structure-cache.yaml` — Same Run

WHY: Running the builder once to produce both outputs avoids a double scan of
the vault (one for the YAML, one for the JSON). The single `run_with_client()`
call produces `(cache, feed)` from the same `ScanResult`; `run()` then writes
the YAML atomically and dumps the feed to stdout. ALL progress/warnings go to
stderr — stdout carries the JSON feed only. This is the
`feedback_never_redirect_stderr_into_json` rule in concrete form: mixing
progress lines into stdout would corrupt the `json.load` in the
vault-explorer Step 9 pipeline.

## `placeholder_links` Persisted in BOTH Outputs (W1)

WHY: The placeholder list from `placeholder_detect.detect_placeholders` is
returned from `build_entries` as a first-class value and placed in both the
`moc-structure-cache.yaml` (top-level `placeholder_links` field) and the
stdout JSON feed (as `feed["placeholder_links"]`). cache-builder.py's
`build_placeholder_links` lift reads it from the feed; the moc-structure-cache's
copy feeds Condition C in the inbox-analyst (via shared-ctx). Both consumers
see the same list from the same run, eliminating the divergence that occurred
when the two files had different data.

## Reuses `cache-builder.py` TTL/Timestamp and Atomic-Write Primitives

WHY: Reuse, not reinvention. `utc_now_iso` is imported from cache-builder.py
via `importlib` (the hyphen in the filename prevents a direct import). The
atomic-write mechanism in `write_cache_atomic` replicates the tmp-rename
pattern from cache-builder.py's `write_cache_atomic` because the file header
differs (`moc-structure-cache.yaml` vs `discovery-cache.yaml`), but the
underlying contract is identical: a torn/partial write never reaches the
`_load_yaml` staleness check in `moc_cache_loader`, because the file is
either fully written or not replaced at all.

## `tags` Populated from Frontmatter in the Same Read Round-Trip (T7.1 / ADR-13)

WHY: Each cache entry carries its note's real `tags` list (extracted from the
frontmatter that is already read during `read_note_raw()`). No extra per-note
round-trip is needed: `parse_frontmatter(content)` yields the tags from the
same content string that supplies title, wikilinks, and the raw text for
`up_parse`. The `extract_tags(fm, body)` helper normalises both list-form and
scalar-form frontmatter tags AND merges inline `#tags` from the body (#50); a
note with no tags produces `[]`, never `None`.

The concrete reason tags are stored here and not computed on demand:
**ADR-13 introduces two exclude-tag filters** (`MiYo/Tomo/exclude/moc` and
`MiYo/Tomo/exclude/note`) that must read each entry's `tags` at filter time
in `lib/orphan_link.emit_orphan_suggestions` and `moc-discovery._handle_scan`.
Computing tags on demand at filter time would require an additional Kado read
per entry, breaking the single-read-per-note contract the builder was designed
around (C1) and risking rate-limit pressure on large vaults. Caching them in
the MOC-structure-cache (metadata-only — Constitution L1 satisfied) lets both
filters operate directly on the pre-loaded entry without any vault I/O.

Spec: 021 Phase 7 T7.1, PRD Feature 8 AC7.

WHY frontmatter AND inline (#50): `extract_tags(fm, body)` merges the YAML
frontmatter `tags:` list with inline `#tags` parsed from the note body (code
blocks/spans skipped, leading `#` stripped, first-seen order). So the ADR-13
exclude tags (`MiYo/Tomo/exclude/moc` / `.../exclude/note`) now take effect in
EITHER form — matching MOC *discovery*, which uses Kado
`search_by_tag(#type/others/moc)` and matches inline + frontmatter both. This
resolves the earlier frontmatter-only asymmetry (surprising for users who tag
inline, the Obsidian default). Both tag sources are still read from the SAME
single content round-trip (`read_note_raw`), so the single-read-per-note
contract (C1) is preserved — no extra Kado I/O. The exclude filters
(`lib/orphan_link.emit_orphan_suggestions`, `moc-discovery._handle_scan`) do an
exact-membership check, so surfacing inline tags in the entry `tags` list is
safe. Inline-tag parsing lives in `moc-tree-builder.parse_inline_tags`.

## `up_state` Resolved by Caller, Not by `up_parse` (M1)

WHY: `up_parse.parse_up_from_content` returns `{target, source}` only.
`_resolve_up_state` in this builder maps the target against the MOC stem set
(`moc_stem_set`) to produce "absent" / "valid" / "broken". The stem set is
built once in `build_entries` and reused for all notes. This keeps up_parse
independent of vault state (testable in isolation) while keeping the resolution
logic co-located with the data that makes it possible.

## `up_broken_reason` Distinguishes WHY `up_state` Is Broken (spec 033 T1.1/T1.2 / ADR-2, ADR-3)

WHY: `_resolve_up_state` now returns `(up_state, up_broken_reason)` instead of
`up_state` alone. `up_state`'s three values (`absent` / `valid` / `broken`)
are deliberately UNCHANGED (ADR-2) — three existing consumers key on
`up_state == "absent"` (`_check_unparented`) or `== "broken"`
(`_check_broken_up`, and `_check_orphan`'s `setdefault`). Extending the enum
itself with new values like `not-a-moc` / `unresolved` would make each of
those `==` comparisons silently wrong for the new values — code that still
compiles, still passes any test that only checks the old values, and quietly
stops flagging findings it used to catch. An additive field leaves every
existing comparison true and every consumer correct; this is the same choice
spec 032 made twice already, for `up_source` and `up_value` (see T7.1 above).

`up_broken_reason` distinguishes the two ways a resolution can be `broken`:
- `not-a-moc` — the `up::` target IS a real, in-scope note (it resolves
  against `note_stem_set`, derived from `scan_result.in_scope_note_paths`).
  The link itself works; the note it points to just doesn't carry the MOC
  tag. This is an advisory situation, not data corruption — nothing here is
  actually broken in the vault.
- `unresolved` — the target is not in `moc_stem_set` OR `note_stem_set`: it
  is not part of the audited area at all. `unresolved` deliberately means
  "not found in the scope this cache scanned", NOT "does not exist anywhere
  in the vault" — the cache only knows its own scope, and answering the
  stronger question would require a vault existence check this builder must
  not acquire (ADR-6; C1's single-read-per-note contract governs reads that
  DO happen, but a broken-link classifier must not reach for an extra one
  just to firm up its answer).

A stem present in both `moc_stem_set` and `note_stem_set` (a MOC also listed
as a note) resolves `valid` — the MOC set is checked first and wins the tie,
matching `up_state`'s pre-existing MOC-first precedence.

**The load-bearing part is absence (ADR-3):** `up_broken_reason` is written
on EVERY entry the builder assembles, `None` where it does not apply (the
`absent`/`valid` cases). Its PRESENCE, not its value, is the cache-freshness
signal a downstream reader relies on. `None` is a legitimate, meaningful
value here — so a reader that does `entry.get("up_broken_reason")` and
treats a `None` result as "no reason" cannot tell that case apart from "this
cache predates spec 033 and never wrote the key at all". Consumers MUST test
for the key with a module-level `_MISSING` sentinel and a membership check
(`entry.get("up_broken_reason", _MISSING) is not _MISSING`), never `.get()`
with a default — mirroring the sentinel pattern spec 032 already established
for `up_value` (T7.1 above).

The failure this absence rule exists to prevent: without it, a pre-033 cache
read by 033-aware code would silently read as `unresolved` for every single
finding (because a missing key and an explicit `None` are indistinguishable
under a bare `.get()`). That would keep offering the destructive "repoint or
remove" fix on exactly the findings this spec exists to protect from
that fix — while the report claims it already checked.

## `placeholder.build` / `moc-cache.build` Telemetry Goes to stderr (M2/M4/M7)

WHY: The PRD §Observability table promises these two events to validate the
placeholder false-positive drop (M2/M4) and the no-excluded-leak guarantee (M7),
but there is no event bus in Tomo — `lib/tomo_lifecycle` is a pure state machine,
not a sink. The T4.3 live validation (2026-06-09) found the events were never
actually emitted, so the metrics could only be eyeballed off the cache file.
`_emit_build_telemetry` writes two greppable `[moc-tree] <event> {json}` lines to
**stderr**, never stdout — stdout is the cache-builder JSON feed and any non-JSON
byte there corrupts the downstream `json.load`
(`feedback_never_redirect_stderr_into_json`). Parsers split on the event name.
This is the minimal sink that makes the PRD metrics observable without inventing
event-bus infrastructure the rest of the pipeline does not have.

WHY emit from `run_with_client` (the testable seam) rather than `run()`: the seam
is where `scan_result`, the placeholder stats, and the assembled cache all
co-exist in memory. Emitting here lets the FakeKadoClient tests assert on the
event payloads via `capsys` with no live Kado or disk write, and `run()` (the
real-IO wrapper) inherits the emission for free. The `(cache, feed)` return tuple
is deliberately UNCHANGED — stats ride out on stderr, not in the return value, so
no consumer of the seam had to change (only the internal `build_entries` grew a
third tuple element).

## `excluded_leak_count` Is a Defense-in-Depth Guard, Expected 0 (M7)

WHY: `moc_scan` already honours `exclude_paths` and drops excluded notes before
assembly, so `_count_excluded_leaks` over the assembled entries is normally 0.
It is not redundant: it is the M7 assertion that the scan's exclusion actually
held — a non-zero value is the only signal that an excluded path (e.g. the `X/`
template vault) leaked into the cache through a scan bug. Because the scan never
lets a leak through end-to-end, the counter is unit-tested against hand-built
entries rather than through the seam. Prefix matching normalises a trailing `/`
so `X` and `X/` both mean "the X folder" while `Xenon/` is not a false match.

## WHY resolve `Conventions` from `--config` and thread `parent_marker` into `up_parse` (spec 028 T4.2)

WHY: `up_parse.parse_up_from_content` used to hardcode the `up::` inline marker.
The builder already carries the parsed vault-config dict down to `build_entries`,
so it resolves the active profile's `Conventions` there
(`resolve_conventions(profiles_dir=DEFAULT_PROFILES_DIR, profile_override=config.get("profile"))`)
and passes `conventions.parent_marker` into every `parse_up_from_content` call.
`parent_marker` defaults to `up::` in the lib, so `miyo` parses exactly as before
(CON-2). `DEFAULT_PROFILES_DIR` is `SCRIPT_DIR.parent / "profiles"` — caller-
supplied from this script's own dir so the flattened instance layout resolves
(ADR-2 / CON-4). `FOOTER_CALLOUTS` is deliberately NOT touched — it is a separate
concern explicitly out of scope for spec 028. See
`docs/tomo/scripts/lib/profile_conventions.md` for the resolver rationale.
