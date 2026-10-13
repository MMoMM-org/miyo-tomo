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
- **Kado's matching contract.** `search-adapter.ts` byName: `query.toLowerCase()`
  is a substring of `f.name.toLowerCase()`. No Unicode normalisation, JS
  lowercase rather than casefold. A query only finds files whose stored name
  contains those exact code points once lowercased.
- **Why two query forms, and why `.lower()`.** macOS stores names decomposed
  (NFD) while typed names arrive NFC, so a single-form query undercounts, and an
  undercount reads as "unique" and yields an unsafe bare embed (PRD Rule 5: an
  unverified question is never favourable). The census sends NFC-lower and,
  when different, NFD-lower. Python `.lower()` mirrors JS `toLowerCase`;
  casefold would turn "Straße" into "strasse", which Kado cannot match.
- **Why casefold locally.** After the union by path, hits are narrowed to final
  segment equality under NFC + casefold (as `typed_name_check._comparable`).
  That is looser than Kado's own rule and can only over-count; over-counting
  makes K1 path-qualify, the safe direction. Cache key is the same local key, so
  repeated asks in any casing or form cost nothing. Names with `*`/`?` are never
  sent: Kado would read them as a glob; Obsidian forbids them in names anyway.
- **F3-AC7 interaction.** "One name search per distinct basename" becomes at
  most two: the second search is sent only for names whose NFC and NFD forms
  differ (accented or otherwise decomposable names); ASCII names cost one.
  `searches` counts each variant search sent, `pages` each page fetched.
- **Budget across variants.** PAGE_BUDGET (2) applies per variant search. If any
  variant errors or exhausts its budget the whole count is None (cached), never
  a partial number.
- **Glob metacharacters.** Kado `search-adapter.ts` `isGlobQuery` treats only
  `*` and `?` as glob syntax; `globQueryToRegExp` escapes `. + ^ $ { } ( ) | [ ] \`
  first, so `[` and `{` are literal there and are sent like any other character
  (pinned by a test). Guarding more than `*`/`?` would return None for legal
  names for no safety gain.
- **Malformed responses.** Response parsing sits inside the same `try` as the
  call, so a non-dict result or non-dict item is "unanswered" (None), never a
  count taken from a half-read answer.

## The local key is `path_key` (spec 039 W7)

The narrowing key (NFC + casefold) is `lib.vault_paths.path_key`, not a private
copy, so the census counts under the same key K1 and K2 compare targets with.
The Kado query forms (NFC and NFD through `.lower()`) are unchanged.
