# Context — Tomo
<!-- Current sprint focus, active work, known blockers. Updated: 2026-05-07 -->
<!-- This file is short-lived — prune entries older than 2 weeks via /memory-cleanup -->

## Open tasks from session 2026-05-01

Persisted here so they survive session resets. Move to backlog.md when long-term, mark resolved when done.

### Operational follow-ups (do soon)

- ~~**#11 Origin/main pushen**~~ ✅ Done — `main` is in sync with `origin/main` as of 2026-05-07.
- ~~**#12 Hashi response handoffs archivieren**~~ ✅ Done — both 2026-04-30 hashi response items are in `_archive/outbox/2026-04/`.
- ~~**#13 Memory: pending learnings**~~ ✅ Done 2026-05-07 — (a)/(b) → `general.md`, (c)/(e)/(f) already in `troubleshooting.md`, (d) tracked below.

### In-flight cost / model investigations

- **F-32 parent-model sonnet pin verification** — `settings.json` `model:` field controls the parent /inbox session's model (parent-model inheritance). Last unpinned Pass-1 cost was ~$26 on opus main thread, ~79% of total Pass-1 cost despite only 30% of messages. Hypothesis: pinning sonnet at the parent drops main-thread cost to ~$7 with no quality regression on orchestration phases (A/A5/C are prompt-only). **Pending verification:** next /inbox live run with the sonnet pin active; record main-thread token count and cost. Touch points: `tomo/dot_claude/settings.json` `model:` field, F-32 in `backlog.md`.

### Technische Bug-Fixes & Verifikation

- **#9 Analyst: Audio-Klassifikation post-transcription korrigieren** — Audios werden nach Transcription nicht mehr gebraucht (User-Feedback 2026-05-01). Aktuell klassifiziert Analyst sie als `template:"asset"` mit destination `Atlas/290 Assets/295 Attachments/`, was suggeriert sie würden dorthin verschoben. Tatsächlich emittiert Pass 2 paired `delete_source` → Audio gelöscht. UI in suggestions.md verwirrend (zeigt destination die nie genutzt wird). Klassifikation sollte sein: (a) Skip + delete_source wenn transcription erfolgreich, oder (b) "delete after transcription" als expliziter Action-Type.
- **#16 Suggestions.md Checkbox-Layout review** — User-Feedback 2026-05-01: bei Audio+Transcript-Pairs (S02/S03/S04) ist die UI verwirrend. Detail-Diskussion deferred bis nach Hashi-Bug-Pass. "Keep origin" Default `false` ist korrekt für Audios; Layout-Probleme bei der Checkboxen-Gruppe noch zu prüfen.
- ~~**#18 Voice-Transcript Date-Field: `recorded:` statt `updated:`**~~ ✅ Done (commit `f6b264b`, already on main 2026-05-07). Fix Option 1 + 2 both shipped: `voice_render.py` v0.5.0 emits `recorded: <iso8601>` parsed from filename timestamps (`__YYYY-MM-DD HH:MM:SS` pattern); `inbox-analyst.md` Step 8 explicitly prefers event-date keys (`recorded`, `Recorded`, `created`, `Created`, `date`, `Date`, `event_date`, `EventDate`, `captured`, `Captured`) and ignores maintenance keys (`updated`, `Updated`, `modified`, `Modified`, `last_modified`, `LastModified`, `lastmod`). Verified via `lib/voice_render.py:_extract_recorded_iso` + `inbox-analyst.md:200-211` 2026-05-07.
- **#19 Audio-Worthiness-Gap: lange Transkripte verlieren Atomic-Note** — User-Feedback 2026-05-01. **Konkretes Symptom (gleiches Memo wie #18):** 183-Sek-Audio (~1500+ chars Transkript) mit zwei substantiellen Threads — (i) Medizin (Physio + Uro-Termin), (ii) Tomo/PKM-Gedanken (Cloud-Code, Kontextgröße, Max-Plan). Analyst emittierte nur `update_daily` (fleeting log), kein `create_atomic_note`. Die PKM-Gedanken wären atomic-note-würdig gewesen, gehen verloren. **Ursache:** Analyst verdichtet das Transkript zu einem ~350-char Summary und testet das gegen die Worthiness-Schwelle (`reasoning` < 500 chars in result.json) → fleeting log entry only. Worthiness-Scoring läuft am Summary, nicht am Original-Transkript. **Fix-Optionen:** (a) Worthiness gegen Original-Transkript-Länge prüfen, nicht gegen Summary; (b) Audio-Transkripte explizit immer `create_atomic_note` (bypass worthiness) wenn `source_type=voice-transcript`; (c) **Multi-Topic-Detection** — wenn ein Item mehrere distinct concepts hat, mehrere Aktionen emittieren (Medizin → daily-log, PKM-Gedanken → atomic-note). **Workaround heute:** Force Atomic Note Checkbox in suggestions.md ankreuzen (XDD 012). **Empfehlung:** (a) + (c) zusammen — Worthiness am Originaltranskript + Multi-Topic-Splitting. Touch points: `inbox-analyst.md` Step 7 + Worthiness-Gate-Logik + Multi-Topic-Branch in Step 8.

### Performance / Architektur (eigene Sessions)

- **#15 Pass 2 Happy-Path als deterministisches Script (Option B/C)** — `scripts/run-pass2.sh` schreiben das die 5 Pass-2-Scripts in fester Reihenfolge ausführt. Agent ruft nur noch run-pass2.sh + handelt Step 2.5 Fan-Resolve und Error-Recovery. Erwartete Ersparnis: 80-90% der Subagent-Tokens.
- **#17 Pass 1 Token-Audit: Easy Wins identifizieren** — Pass 1 verbraucht 14.7M tokens vs Pass 2 mit 440k (33× teurer). Hot Path: 19× inbox-analyst subagents (~370k each = 7.0M) + Parent /inbox session (7.14M). Investigationspunkte: Skills-Cache pro Dispatch, deterministische Arbeit auslagern, Bündelung von Steps, Item-Batching. Wichtig: nach `settings.json model: sonnet` Sync den Effekt auf Parent zuerst messen. Erwartetes Ziel: Pass 1 von 15M auf 5-7M.

### Optional / Cosmetic

- **#14 instruction-builder ICMDA-Refactor (optional)** — Body-Layout entspricht nicht TCS-ICMDA-Convention (Identity/Constraints/Mission/Decision/Activities/Output). Funktional kein Gewinn, nur Convention-Conformance. Nur angehen wenn andere Agents auch konvertiert werden.

## Verifikation für nächste Pass-1/Pass-2 Runs

- Sonnet-Pin in `settings.json` greift → Parent /inbox sollte unter 2.5M tokens liegen (heute 7.14M auf opus)
- `before_first_line` für Morgen-Routine (oder ähnliche Notes mit Position-Hinweis im Content) erscheint in `instructions.json` als `position: before_first_line` — nicht mehr als Fallback `after_last_line`
- `link_to_moc` Actions emittieren `placement: "after"` statt `"inside"`
