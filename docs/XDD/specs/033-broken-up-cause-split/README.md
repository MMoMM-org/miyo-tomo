# Specification: 033-broken-up-cause-split

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-03 |
| **Current Phase** | PRD |
| **Last Updated** | 2026-09-03 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 6 Must features, 21 Gherkin criteria, 4 business rules, 4 edge cases |
| solution.md | pending | |
| plan/ | pending | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-03 | Spec scaffolded from issue [#157](https://github.com/MMoMM-org/miyo-tomo/issues/157) | Found while validating spec 032 on live data. `_resolve_up_state` (`moc-tree-builder.py:280`) returns `broken` for exactly one condition — *the `up::` target is not the stem of an in-scope MOC*. Three unrelated vault states collapse onto that one label, and `_check_broken_up` offers all three the same remedy: *"repoint it to a MOC you enter below, or leave empty to remove"*. |
| 2026-09-03 | The remedy is correct for **one** of the three causes | Target genuinely missing → remove/repoint is right. Target exists in scope but carries no MOC tag → **the link works**; removing it deletes a real parent. Target exists outside `scope_paths` → **the scanner is blind, not the vault**. A user working the list in good faith flattens deliberate hierarchy. |
| 2026-09-03 | Population measured on the live cache, not estimated | 2026-09-03 rebuild: 359 entries, 42 `broken_up`. **20** targets are present in the cache as `kind: note` (cause 2). **22** are absent from it (cause 1 or 3). Of those 22, seven name one target by bare stem while an eighth records the same target as a **full path under a folder outside `scope_paths`** — so cause 3 is confirmed, not hypothetical. At most a handful of the 42 are genuinely dangling. |
| 2026-09-03 | **The split costs nothing** — no new Kado calls, no new scan | `_resolve_up_state` is handed `moc_stem_set`, derived from `scan_result.moc_paths`. The same `ScanResult` already carries `in_scope_note_paths`, and the cache already stores every in-scope note with `kind: note` (measured: 64 MOCs + 295 notes). Distinguishing *valid* / *not-a-moc* / *unresolved* is a three-way test at the exact site of today's two-way test, over data already in hand. Contrast with spec 032, where the equivalent question also turned out to be free — same lesson twice. |
| 2026-09-03 | `unresolved` will **not** be split further into *missing* vs *out-of-scope* | The cache knows only its own scope; deciding whether an absent target exists elsewhere in the vault needs I/O this check does not have and must not acquire (`broken_up` is cache-only by construction — `_check_broken_up` takes no `graph_audit_fn`/`list_dir_fn`). The report will therefore say *"not found in the audited area"* rather than claim the note is gone. Honest under-claiming beats a wrong certainty. |
| 2026-09-03 | **`not-a-moc` becomes advisory with an inverted suggestion** (user decision) | Chosen over *"stop reporting it"* and *"report without a fix"*. The finding stops being an integrity defect and becomes an advisory naming the real gap: **the parent note carries no MOC tag**. The suggestion is the inverse of today's — *tag the target*, not *delete the link*. One tag often resolves several findings at once (measured: seven travel notes point at three parent notes). No Apply checkbox, so nothing destructive can be approved by accident. |
| 2026-09-03 | Scope boundary against spec 032, stated so it cannot drift | 032 decides **where** a broken-parent fix is written (`edit_frontmatter` vs a body edit) and is untouched by this spec. 033 decides **whether** a fix should be offered at all, and what it should say. The two meet only at the finding's `detail`, which gains one field. |
