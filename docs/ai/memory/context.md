# Context — Tomo
<!-- Current sprint focus, active work, known blockers. Updated: 2026-05-07 -->
<!-- This file is short-lived — prune entries older than 2 weeks via /memory-cleanup -->

## Open tasks from session 2026-05-01

> **Migrated to GitHub 2026-06-03:** the operational/perf items below now live as GitHub issues — #9 → epic #18, #16 → epic #19, Pass-2/Pass-1 token work → epic #24, F-32 → #40. The verified mapping is in `docs/XDD/backlog.md`. Entries kept here for session-reset continuity; GitHub is the source of truth for status.

Persisted here so they survive session resets. Move to backlog.md when long-term, mark resolved when done.

### Operational follow-ups (do soon)

- ~~**#11 Origin/main pushen**~~ ✅ Done — `main` is in sync with `origin/main` as of 2026-05-07.
- ~~**#12 Hashi response handoffs archivieren**~~ ✅ Done — both 2026-04-30 hashi response items are in `_archive/outbox/2026-04/`.
- ~~**#13 Memory: pending learnings**~~ ✅ Done 2026-05-07 — (a)/(b) → `general.md`, (c)/(e)/(f) already in `troubleshooting.md`, (d) tracked below.

### In-flight cost / model investigations

- **F-32 parent-model sonnet pin verification** — `settings.json` `model:` field controls the parent /inbox session's model (parent-model inheritance). Last unpinned Pass-1 cost was ~$26 on opus main thread, ~79% of total Pass-1 cost despite only 30% of messages. Hypothesis: pinning sonnet at the parent drops main-thread cost to ~$7 with no quality regression on orchestration phases (A/A5/C are prompt-only). **Pending verification:** next /inbox live run with the sonnet pin active; record main-thread token count and cost. Touch points: `tomo/dot_claude/settings.json` `model:` field, F-32 in `backlog.md`.

### Technische Bug-Fixes & Verifikation

- **#9 Analyst: Audio-Klassifikation post-transcription** — **✅ Resolved 2026-06-03 → #33.** Die `asset`-Fehlklassifikation ist obsolet: Audios werden vor dem Dispatch herauspartitioniert (`inbox-triage.py:183`), der Analyst sieht sie nie, voice-transcriber löscht nicht. Der gültige Rest (Audio gehört zum löschbaren *source*-Set, ausgeführt von Hashi — NICHT Tomo) wandert ins Source-Model von #33. Original-Notiz: Audios werden nach Transcription nicht mehr gebraucht (User-Feedback 2026-05-01). Aktuell klassifiziert Analyst sie als `template:"asset"` mit destination `Atlas/290 Assets/295 Attachments/`, was suggeriert sie würden dorthin verschoben. Tatsächlich emittiert Pass 2 paired `delete_source` → Audio gelöscht. UI in suggestions.md verwirrend (zeigt destination die nie genutzt wird). Klassifikation sollte sein: (a) Skip + delete_source wenn transcription erfolgreich, oder (b) "delete after transcription" als expliziter Action-Type.
- **#16 Suggestions.md Checkbox-Layout review** — **✅ Folded into #33 2026-06-03.** Root cause identifiziert: `origin` und `source` sind zwei Namen für dasselbe Konzept, und bei Voice-Items gibt es 3 Dateien (m4a / transcript=source / note). Lösung im #33-Source-Model: Terminologie auf "source" vereinheitlichen, source = {m4a + transcript}, ein "Delete source" entfernt beide via Instruction→Hashi. Original-Notiz: User-Feedback 2026-05-01, Audio+Transcript-Pairs (S02/S03/S04) UI verwirrend.
- ~~**#18 Voice-Transcript Date-Field: `recorded:` statt `updated:`**~~ ✅ Done (commit `f6b264b`, already on main 2026-05-07). Fix Option 1 + 2 both shipped: `voice_render.py` v0.5.0 emits `recorded: <iso8601>` parsed from filename timestamps (`__YYYY-MM-DD HH:MM:SS` pattern); `inbox-analyst.md` Step 8 explicitly prefers event-date keys (`recorded`, `Recorded`, `created`, `Created`, `date`, `Date`, `event_date`, `EventDate`, `captured`, `Captured`) and ignores maintenance keys (`updated`, `Updated`, `modified`, `Modified`, `last_modified`, `LastModified`, `lastmod`). Verified via `lib/voice_render.py:_extract_recorded_iso` + `inbox-analyst.md:200-211` 2026-05-07.
- **#19 Audio-Worthiness-Gap: lange Transkripte verlieren Atomic-Note** — **✅ Resolved 2026-06-12 (F-41 / spec 016 shipped + live-validated).** Hälfte (a) — Worthiness gegen Full-Content — via `f6b264b`; Hälfte (c) Multi-Topic-Detection via F-41 (analyst Step 7.5 de-biased two-pass, Sonnet v0.17.0). **Live-Validation 2026-06-12:** das exakte Memo unten splittet jetzt korrekt — PKM-Gedanke → 1 `create_atomic_note`, Physio/Uro-Termine → daily-log (`log_entry`). Die befürchtete "verlorene" Atomic-Note ist da. WICHTIG: "≥2 Threads → ≥2 Atomics" war eine Fehlannahme — Termine gehören korrekt ins Tageslog, nicht als Atomic; das Memo hat *eine* evergreen-würdige Idee, also ist 1 Atomic richtig (enumeration≠emission, siehe decisions.md 2026-06-12). Original-Notiz: User-Feedback 2026-05-01. **Konkretes Symptom (gleiches Memo wie #18):** 183-Sek-Audio (~1500+ chars Transkript) mit zwei substantiellen Threads — (i) Medizin (Physio + Uro-Termin), (ii) Tomo/PKM-Gedanken (Cloud-Code, Kontextgröße, Max-Plan). Analyst emittierte nur `update_daily` (fleeting log), kein `create_atomic_note`. Die PKM-Gedanken wären atomic-note-würdig gewesen, gehen verloren. **Ursache:** Analyst verdichtet das Transkript zu einem ~350-char Summary und testet das gegen die Worthiness-Schwelle (`reasoning` < 500 chars in result.json) → fleeting log entry only. Worthiness-Scoring läuft am Summary, nicht am Original-Transkript. **Fix-Optionen:** (a) Worthiness gegen Original-Transkript-Länge prüfen, nicht gegen Summary; (b) Audio-Transkripte explizit immer `create_atomic_note` (bypass worthiness) wenn `source_type=voice-transcript`; (c) **Multi-Topic-Detection** — wenn ein Item mehrere distinct concepts hat, mehrere Aktionen emittieren (Medizin → daily-log, PKM-Gedanken → atomic-note). **Workaround heute:** Force Atomic Note Checkbox in suggestions.md ankreuzen (XDD 012). **Empfehlung:** (a) + (c) zusammen — Worthiness am Originaltranskript + Multi-Topic-Splitting. Touch points: `inbox-analyst.md` Step 7 + Worthiness-Gate-Logik + Multi-Topic-Branch in Step 8.

### Performance / Architektur (eigene Sessions)

- **#15 Pass 2 Happy-Path als deterministisches Script (Option B/C)** — `scripts/run-pass2.sh` schreiben das die 5 Pass-2-Scripts in fester Reihenfolge ausführt. Agent ruft nur noch run-pass2.sh + handelt Step 2.5 Fan-Resolve und Error-Recovery. Erwartete Ersparnis: 80-90% der Subagent-Tokens.
- **#17 Pass 1 Token-Audit: Easy Wins identifizieren** — Pass 1 verbraucht 14.7M tokens vs Pass 2 mit 440k (33× teurer). Hot Path: 19× inbox-analyst subagents (~370k each = 7.0M) + Parent /inbox session (7.14M). Investigationspunkte: Skills-Cache pro Dispatch, deterministische Arbeit auslagern, Bündelung von Steps, Item-Batching. Wichtig: nach `settings.json model: sonnet` Sync den Effekt auf Parent zuerst messen. Erwartetes Ziel: Pass 1 von 15M auf 5-7M.

### Optional / Cosmetic

- **#14 instruction-builder ICMDA-Refactor (optional)** — Body-Layout entspricht nicht TCS-ICMDA-Convention (Identity/Constraints/Mission/Decision/Activities/Output). Funktional kein Gewinn, nur Convention-Conformance. Nur angehen wenn andere Agents auch konvertiert werden.

## Deferred Review Items

From code review of `feat/018-inbox-routing-redesign` (2026-05-26, commit f1600e5).
27 of 33 findings were fixed; these 13 are deferred.

### R1 — instruction-render.py 1742 LOC refactor (2026-05-26)
- Location: tomo/scripts/instruction-render.py
- Concern: 3-6x Constitution L2 limit (300-500 LOC). Split into actions, render, resolve modules.
- Reason deferred: Large refactoring — needs dedicated PR to avoid regressions
- Branch: feat/018-inbox-routing-redesign

### R2 — suggestion-parser.py 1433 LOC refactor (2026-05-26)
- Location: tomo/scripts/suggestion-parser.py
- Concern: Approaching L2 limit. Extract moc_proposal_parser.py.
- Reason deferred: Same as R1 — dedicated refactoring PR
- Branch: feat/018-inbox-routing-redesign

### R3 — FakeKadoClient test duplication (2026-05-26)
- Location: tests/test_inbox_triage.py:30, tests/integration/test_018_pipeline.py:57
- Concern: FakeKadoClient copy-pasted between files, drift risk
- Reason deferred: Test maintenance, not a bug. Both copies work.
- Branch: feat/018-inbox-routing-redesign

### R4 — Action priority cascade untested (2026-05-26)
- Location: tests/test_inbox_triage.py
- Concern: No test verifies priority order when multiple conditions are true simultaneously
- Reason deferred: Individual actions tested; cascade is deterministic if/elif chain
- Branch: feat/018-inbox-routing-redesign

### R5 — mark-captured squelch-persist path untested (2026-05-26)
- Location: tomo/scripts/mark-captured.py:158-193
- Concern: MOC proposal rejection persistence path has no test coverage
- Reason deferred: Secondary code path, not in critical flow
- Branch: feat/018-inbox-routing-redesign

### R6 — /inbox --cleanup removal undocumented (2026-05-26)
- Location: tomo/dot_claude/commands/inbox.md
- Concern: Old --cleanup flag silently dropped; cleanup is now implicit
- Reason deferred: Docs gap, not a bug — cleanup behavior is correct
- Branch: feat/018-inbox-routing-redesign

### R7 — Private _extract_from_mcp_json import (2026-05-26)
- Location: scripts/strip-tomo-frontmatter.py:52
- Concern: Imports private API across module boundary
- Reason deferred: Dev-only tool, minor coupling
- Branch: feat/018-inbox-routing-redesign

### R8 — strip-tomo-frontmatter --recursive defaults True (2026-05-26)
- Location: scripts/strip-tomo-frontmatter.py:199
- Concern: Recursive vault mutation by default is risky
- Reason deferred: Dev-only tool; zero-config mode already overrides to non-recursive
- Branch: feat/018-inbox-routing-redesign

### R9 — Inbox cache contains full note bodies (2026-05-26)
- Location: tomo/scripts/inbox-triage.py:276
- Concern: tomo-tmp/inbox-cache/ stores full note content (Constitution L2 spirit)
- Reason deferred: Container-local, ephemeral. L2 advisory.
- Branch: feat/018-inbox-routing-redesign

### R10 — doc_frontmatter raises at import time (2026-05-26)
- Location: tomo/scripts/lib/doc_frontmatter.py:56
- Concern: Missing schema file crashes all importing scripts at import
- Reason deferred: Schema always present in Docker image; only affects broken deployments
- Branch: feat/018-inbox-routing-redesign

### R11 — No WHY docs for 6 new skills (2026-05-26)
- Location: docs/tomo/dot_claude/skills/ (missing directory)
- Concern: force-atomic-handling, instructions-coverage, kado-discovery-patterns, routing-plan-consumer, suggestions-doc-format, tomo-lifecycle-states — no WHY docs
- Reason deferred: Docs debt — track in backlog
- Branch: feat/018-inbox-routing-redesign

### R12 — Naming inconsistency _hits suffix (2026-05-26)
- Location: tomo/scripts/inbox-triage.py:66
- Concern: Mixed _hits suffix on raw fields vs processed fields
- Reason deferred: Internal naming, no external impact
- Branch: feat/018-inbox-routing-redesign

### R13 — XDD reference docs stale (2026-05-26)
- Location: docs/XDD/reference/tier-2/workflows/, docs/XDD/reference/tier-3/inbox/
- Concern: Still describe vault-executor, tag-captured.py, old tag-based lifecycle
- Reason deferred: Docs debt — track in backlog
- Branch: feat/018-inbox-routing-redesign

## Verifikation für nächste Pass-1/Pass-2 Runs

- Sonnet-Pin in `settings.json` greift → Parent /inbox sollte unter 2.5M tokens liegen (heute 7.14M auf opus)
- `before_first_line` für Morgen-Routine (oder ähnliche Notes mit Position-Hinweis im Content) erscheint in `instructions.json` als `position: before_first_line` — nicht mehr als Fallback `after_last_line`
- `link_to_moc` Actions emittieren `placement: "after"` statt `"inside"`
