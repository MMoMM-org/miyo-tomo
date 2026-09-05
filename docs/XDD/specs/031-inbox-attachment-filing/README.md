# Specification: 031-inbox-attachment-filing

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-01 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-09-05 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 6 Must features, 27 Gherkin criteria, 10 business rules, 9 edge cases, 4 open questions |
| solution.md | completed | 6 ADRs (4 user-confirmed, 2 corollaries), traced resolution walkthrough, directory map, 6 gotchas |
| plan/ | completed | 6 phases, 31 tasks, 141 spec refs, 8 parallel |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-01 | Spec scaffolded | Surfaced by a real cross-vault import: `tomo-instance/tomo-tmp/rendered-hashi/instructions.json`, a session-composed set with 13 `move_note` + 8 `move_asset` moving `100 Inbox/Images/*.jpg\|png` → `Atlas/290 Assets/295 Attachments/`. The deterministic `/inbox` pipeline cannot produce that today. |
| 2026-09-01 | Cross-repo dependency already satisfied — no blocker | Hashi shipped `move_asset` in **0.20.1** (PR #120): `{id, action, source, destination, applied?}`, `additionalProperties:false`, `fileManager.renameFile` so embeds/links follow, never calls `vault.process`. Tomo's producer AND mirror schemas carry it (PR #154). `schema_version` stays `"2"`. This spec plans against a live, executable action — not a pending dependency. |
| 2026-09-01 | Config layer already satisfied — no new config | `concepts.asset` = `Atlas/290 Assets/295 Attachments/` already exists in `tomo/profiles/miyo.yaml:57` and the instance `vault-config.yaml:33`. The destination is resolvable today via `read-config-field.py --field concepts.asset`; no wizard change, no new config key. |
| 2026-09-01 | **Scope: Case A only** (embedded attachments) | An attachment embedded in an inbox note rides **its note's** lifecycle and needs no `tomo.state` frontmatter of its own. This is what the observed import needed. |
| 2026-09-01 | **Case B explicitly OUT of scope** (standalone inbox attachments) | `inbox-triage.py:163-173` deliberately ignores every non-`.md`/non-audio inbox file — a documented won't-do-yet (#93, 2026-07-18): such files carry no `tomo.state` frontmatter and cannot enter the 2-pass state machine. Case A does not conflict with that rationale, so this spec does **not** reopen #93. Revisiting Case B is a separate decision. |
| 2026-09-01 | Open Question 1 is the spec's centre of gravity | Embed → vault-path resolution. The body says `![[foto.jpg]]`; the observed file lived at `100 Inbox/Images/foto.jpg`, i.e. a subfolder, not a sibling. Candidate strategies: inbox-subtree scan, Kado search, sibling-only assumption. This is expensive to revise after the fact and must be an ADR, not an implementation detail. |
| 2026-09-01 | Research: **no regex in the repo distinguishes `![[…]]` from `[[…]]`** | All nine wikilink patterns (`moc-tree-builder.py:95`, `suggestion-parser.py:59`, `topic-extract.py:207`, `placeholder_detect.py:61`, `render_actions.py:119`, `up_parse.py:69`, `moc-proposal-parser.py:26`, …) match the inner `[[…]]` of an embed and treat it as a plain link. Writing a tenth regex is avoidable: Kado's `listNotes fields=["links"]` returns `{target, kind}` with `kind=='embed'` (`Kado/src/obsidian/search-adapter.ts:299-305`) — one call for the whole subtree, no body reads. `topic-extract.py:373-379` already has the inverse filter (`if kind != "link": continue  # ADR-4: embeds excluded`). |
| 2026-09-01 | Research correction: Kado's `.md`-only limit applies to **`read`, not to `listDir`/`byName`** | `listDir` and `byName` use `app.vault.getFiles()` (`search-adapter.ts:408-414`, `:242-252`) and therefore see images; `byContent`/`byFrontmatter`/`listNotes` use `getMarkdownFiles()`. Extension-strictness is scoped to `kado-read` (`Kado/src/mcp/tools.ts:113`). Live proof inside Tomo: `garden-audit-detect-suggest.py:63` does `search_by_name("*_garden-audit.json")`. This widens the viable resolution strategies — an earlier assumption that Kado could not see attachments was too broad. |
| 2026-09-01 | Research: resolution strategy comparison (input to the SDD ADR, not yet decided) | (i) **inbox-subtree listDir + basename match** — correct for the observed layout, **+1 call, O(1)** in notes and embeds, benign and *detectable* failure. (ii) **`byName` per embed** — correct vault-wide but O(unique embeds), and `byName` is **substring** matching (`kado_client.py:277-279`) so a wrong file can be selected silently. (iii) **sibling assumption** — 0 calls, but **wrong for the observed case** (`100 Inbox/Places/note` → `100 Inbox/Images/karte.jpg`) and fails by fabricating a path. Research recommends (i). Note (ii) was already evaluated and rejected for the audio peer in **027 ADR-2** (*"extra Kado reads (429 risk)"*) — same question, same answer. Correct-by-construction alternative for the record: `kado-graph operation=outgoing` returns Obsidian's own `resolvedLinks` (`graph-adapter.ts:54-56`), but costs +1 call per note and needs a new `KadoClient` wrapper. |
| 2026-09-01 | Research: `inbox-triage.py` lists the inbox at **`depth=1`** | `client.list_dir(inbox_path, depth=1)` (`:155`) — `100 Inbox/Images/` appears only as a folder item; the files inside are **never seen** today. Any resolution strategy needs its own subtree view. |
| 2026-09-01 | Research: the per-run Kado call counter **under-reports by 3** | `inbox-triage.py:1521-1533` `_count_kado_calls` docstring says *"1 listDir + 7 byFrontmatter + N body reads"* but returns `5 + body_reads`, and ignores the per-item reads at `:242`, `:315`, `:583`. It feeds the cost log, so this spec's cost metric is untrustworthy until corrected — raised as Open Question 4. |
| 2026-09-01 | Research: **`instructions-diff` would silently ignore a new action kind** | `ACTION_ORDER` (`instructions-diff.py:429-433`) is the reconciliation whitelist; `run_diff` iterates it (`:645`) to build `total_actual` (`:649`). An unlisted kind is counted by `summarize_actual` (`:365-366`) but never reconciled — the audit passes **green** while N actions go unaudited. Not an under-count failure, a blind spot. Only symptom: header `action_count` (`:629`) exceeds printed `TOTAL` (`:659`). Promoted to a Must-have acceptance criterion (PRD Feature 5). |
| 2026-09-01 | Research: `attachments` must NOT ride the `move_note` action | `audio_peer` only rides `move_note` because `_build_delete_source_actions` receives `move_notes` as input (`render_actions.py:1320-1325`). `move_asset` has no such coupling, so a separate `_build_move_asset_actions(manifest, …)` reads the manifest directly. This removes the strip-before-wire step entirely (`render_resolve.py:452-459`) and structurally prevents a moved asset from ever landing in a `delete_source`. |
| 2026-09-01 | Research: four change sites have **no `audio_peer` precedent** | `_REQUIRED_PATH_FIELDS` (`render_actions.py:204-219`) — else `_validate_action_paths` silently skips the kind; `render_md.py:31-46` + `:239` — else `instructions.md` prints *"(unknown action: move_asset)"*; `instructions-dryrun.py:25-33` — else unknown-type exit 1; `instructions-diff` (above). Plus a `KeyError` risk: `concepts.asset` is absent from the defaults at `instruction-render.py:106`. |
| 2026-09-01 | Research: two path helpers are traps for non-`.md` files | `_ensure_md_extension("foto.jpg")` appends `.md` — `.jpg` is not in `_KNOWN_FILE_EXTENSIONS` (`render_actions.py:59-68`, audio + md only). `_dest_join` (`:488`) hardcodes `.md` at `:498`. `_disambiguate_filename` (`:448`) asserts `.md` at `:467-469` and cannot be reused for destination collisions as-is. |
| 2026-09-01 | PLAN completed → spec **Ready** | `plan/`: 6 phases, 31 tasks, 141 `[ref:]` links, 8 parallel. P1 pure detection+resolution core (no Kado import) · P2 emission (`_asset_dest_join`, global dedup, planner slot 3, collision guard) · P3 field threading through BOTH review channels + 4 parser sites · P4 the audit blind spot + dry run · P5 pipeline wiring + the ADR-4 counter fix · P6 integration/regression/cost/live. P2–P4 are mutually independent and may run concurrently after P1 fixes the field shape. TDD throughout; every task carries Prime/Test/Implement/Validate/Success. Ready for /implement. |
| 2026-09-01 | Alignment verified against source at plan time | `ACTION_ORDER` (`instructions-diff.py:429-433`) lists 8 kinds with no `move_asset` — the blind spot is real, not theoretical. `REQUIRED` (`instructions-dryrun.py:25-33`) lists 9 kinds with no `move_asset` — a dry run would exit 1 today. Both confirmed by reading the source, not inherited from research. |
| 2026-09-01 | SDD completed — 4 ADRs confirmed by the user | **ADR-1** resolve via a per-run recursive `list_dir` of the inbox + basename index (+1 call, O(1); ambiguity reported not guessed). **ADR-2** detect embeds deterministically, not in the analyst (keeps structured extraction out of the LLM; testable without an agent per Constitution L1). **ADR-3** destination collision → skip + report (`_disambiguate_filename` asserts `.md` at `render_actions.py:467-469` and cannot be reused; renaming stays a Should-have). **ADR-4** fix `_count_kado_calls` here, since this spec's cost metric depends on it. Corollaries: **ADR-5** `attachments` never rides the `move_note` action — a separate `_build_move_asset_actions` reads the manifest, which removes the strip-before-wire step and makes a `delete_source` on an attachment structurally impossible; **ADR-6** an attachment move never implies a deletion (the intent inversion vs `audio_peer`). |
| 2026-09-01 | Design correction during SDD: the extension classifier is a **two-step** test | `_KNOWN_FILE_EXTENSIONS` (`render_actions.py:59-66`) contains `md` alongside the image set, so a naive membership check would classify `![[Note.md]]` as an attachment and emit a `move_asset` for a note — which Hashi rejects (CON-3). Correct test: in the frozenset AND not in `{md, canvas, base}`. Verified against source. |
| 2026-09-01 | Verified: `concepts.asset` is absent from `CONFIG_DEFAULTS` | `instruction-render.py:105-111` lists `concepts.inbox`, the daily-note path, log heading/level and profile — no asset entry. `cfg["concepts.asset"]` would raise `KeyError` on a profile omitting it. Adding a default is a named task. |
| 2026-09-01 | PRD completed | `requirements.md`: 6 Must features, 27 Gherkin criteria, 10 business rules, 9 edge cases, MoSCoW with 5 explicit Won't-Haves, 6 tracked metrics, 7 risks. Ready for SDD. |
| 2026-09-05 | **Sanctioned deviation from the SDD: the extension allowlist moved out of `render_actions.py`** | Importing `_KNOWN_FILE_EXTENSIONS` from `render_actions.py` made the pure `attachment_index.py` library transitively import ~175 modules, including `kado_client`, and execute `tag-handler-group.py` at module scope (`render_actions.py:32-44`, `exec_module` at `:43`) — incompatible with ADR-2's pure-library boundary. Relocated to `lib/file_extensions.py` as public `KNOWN_FILE_EXTENSIONS`; `render_actions.py` keeps `_KNOWN_FILE_EXTENSIONS = KNOWN_FILE_EXTENSIONS` as a back-compat alias, guarded by a subprocess regression test in `tests/test_attachment_index.py`. Transitive imports 175 → 4. Duplicating the frozenset was considered and rejected as a DRY/SSoT violation — the single source of truth moved, it was not copied. |
| 2026-09-05 | **Correction: path-qualified resolution narrows candidates, it does not test path-set membership** | `solution.md`'s "Resolution — traced walkthrough" row 3 said a path-qualified target is "used verbatim after verifying membership in the index's path set" — impossible to satisfy. Kado's `listDir` always returns the full vault-relative path (`Kado/src/obsidian/search-adapter.ts:34,245` — `path: file.path`), so `build_inbox_index` only ever holds keys like `100 Inbox/Images/karte.jpg`, never a bare `Images/karte.jpg`; a literal membership test against a partial path always misses, making every path-qualified embed permanently `unresolved` and contradicting PRD AC-F2.2. What shipped instead: look up the target's own basename, then narrow that basename's candidate paths to whichever ends with the given target at a `/` boundary. `resolved_path` is always retrieved from the index, never string-built; narrowing to more than one candidate is `ambiguous`, not first-hit-wins. `solution.md` and `plan/phase-1.md` corrected to match. |
| 2026-09-05 | **Three spec defects found by building against reality, not prose — same failure mode spec 032 already logged four times** | (1) the path-set-membership claim above. (2) `solution.md`'s "Destination join" example gave the wrong reason `_ensure_md_extension` is unsafe for attachment paths — it claimed `.jpg` is absent from the allowlist, when `jpg` IS present and the call is actually a silent no-op; the real hazard is any extension NOT in the allowlist (`.heic`, `.tiff`, `.docx`, `.arw`) silently getting a `.md` suffix appended. (3) `plan/phase-1.md` T1.2 described `list_dir_result`'s fail-open cases as only "empty or missing", without stating the real shape — Kado's `list_dir` returns a flat `list[dict]`, no wrapper object, no `entries` key (`kado_client.py` `list_dir` → `_search_all`; `garden-audit.py:371`). T1.2 avoided shipping against the wrong shape only because the implementer was explicitly instructed to read `kado_client.py` and an existing consumer before writing the fixture, rather than trusting the plan's description — the same "the plan names one site; the code has two" pattern spec 032's log already records four times. |
| 2026-09-05 | **All three Phase 1 code-quality FAILs were tests passing for the wrong reason, not broken production code** | A `{}` parametrize case that early-returned and never reached the guard it named; a missing mixed-case test leaving a `.lower()` call unprotected; an untested `path == target` branch that could be deleted with all 30 tests still green. Zero defects in production logic — what caught all three was mutation-testing the specific line each test claimed to guard, not re-reading the code. Standing test-quality bar for Phases 2-6: a test earns its place only if deleting or mutating the line it claims to guard turns it red. |

## Context

**Problem.** When an inbox note embeds an attachment, `/inbox` emits `move_note` for the note and
nothing for the attachment. The note lands in `Atlas/202 Notes/`; the image stays in the inbox.
The embed does **not** break — Obsidian resolves `![[foto.jpg]]` by name across the vault — which
is exactly why this is invisible: nothing is reported as wrong, the asset is simply never filed and
the inbox never empties. Nothing in the pipeline detects embeds at all; `topic-extract.py:380`
excludes them by design (ADR-4, for topic extraction).

**Why now.** The capability gap became concrete in a real cross-vault import, and both blockers that
would normally defer it are already gone: Hashi executes `move_asset`, and `concepts.asset` already
names the destination. What is missing is purely Tomo-side production.

**The chain that must carry an attachment list:**

```
inbox-analyst → suggestions doc → suggestion-parser → manifest
              → render_actions (_build_move_asset_actions) → render_md
              → instructions-diff coverage audit
```

**Prior art to mirror:** `move_note.audio_peer` already threads a non-`.md` companion path
through this exact chain (`instruction-render.py:317,430` → `render_actions.py:584` →
stripped before the wire at `render_resolve.py:438-459`). Note the contrast in intent: the audio
peer is **deleted** via a paired `delete_source` (`render_actions.py:927-928`); an embedded
attachment must be **moved** and must NOT get a `delete_source`.

**Known constraints for the SDD:**
- `move_asset` carries only `{id, action, source, destination, applied?}` — `title`,
  `parent_mocs`, `tags`, `source_inbox_item` are rejected (`additionalProperties:false`).
- Hashi's `move_note` now hard-rejects non-note endpoints, so routing by extension is mandatory,
  not optional.
- `instructions-diff` is a paired consumer: a new emitted kind needs a matching `derive_expected`
  source or the coverage audit under-counts.
- Two notes may embed the same attachment — the emitter must de-duplicate, and must decide what
  happens when only one of the two notes is approved.

---
*This file is managed by the xdd-meta skill.*
