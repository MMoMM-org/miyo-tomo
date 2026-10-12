# basename_census.py — WHY

Runtime file: `tomo/scripts/lib/basename_census.py`. Spec 039 K3, ADR-3, PRD F3-AC7.

- **Why a census at all.** A bare embed is ambiguous when two vault files share a
  basename. K1 (attachment plan) needs a vault-wide count per name before it
  decides between a bare and a path-qualified embed.
- **Why `byName` plus a filter.** Kado `byName` is a case-insensitive substring
  match over every file type (Kado `search-adapter.ts`), so `photo.png` also
  returns `old-photo.png`. The census keeps only hits whose final path segment
  equals the name.
- **Why raw counts.** The run adjustment (subtract this run's inbox copies, add
  its targets) belongs to K1; keeping the census raw keeps it testable alone.
- **Why `_call_tool` and a 2-page budget.** `KadoClient.search_by_name` follows
  every cursor, so it cannot honour a page budget. A third page means the name is
  too common to count cheaply: result None.
- **Why None is cached.** An unanswered census already makes K1 path-qualify the
  embed (fail-safe). Re-querying after a rate-limit error would multiply calls
  against F3-AC7's bound. Cached value is None, never 0.
- **Normalisation.** NFC + casefold on both sides, matching
  `typed_name_check._comparable` (inside_inbox). Names with `*`/`?` are never sent:
  Kado would read them as a glob; Obsidian forbids them in names anyway.
- **Known limit.** The query is sent NFC-casefolded; Kado lowercases but does not
  normalise, so an NFD-stored filename may not match the NFC query (undercount).
