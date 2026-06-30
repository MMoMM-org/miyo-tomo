# Context — Archived 2026-06
<!-- Done/resolved items moved here by /memory-cleanup 2026-06-29. GitHub is SSoT for status. -->
<!-- Trivial done-markers (#11/#12/#13) were pruned, not archived. -->
<!-- Appended by /memory-cleanup 2026-06-30: resolved R11/R13 + open blocks relocated off context.md. -->

## Deferred review item R11 (WHY-docs for 6 skills) — ✅ Resolved 2026-06-30 (PR #102, D-05)

WHY-docs created at `docs/tomo/dot_claude/skills/` for force-atomic-handling, instructions-coverage, kado-discovery-patterns, routing-plan-consumer, suggestions-doc-format, tomo-lifecycle-states.

## Deferred review item R13 (XDD reference docs stale) — ✅ Resolved 2026-06-30 (PR #102, D-06)

Post-018 deprecation banners added to the 7 tier-2/tier-3 inbox reference docs.

## Open items relocated off context.md (2026-06-30) — tracked in GitHub/backlog

The 2026-05-01 / 05-26 working blocks were removed from the live `context.md` to keep it lean; all remain tracked at their canonical home (GitHub is SSoT):
- **F-32** parent-model sonnet-pin cost verification → GH **#40** + `backlog.md`.
- **#15** Pass-2 happy-path script · **#17** Pass-1 token audit → GH **#24** (Performance & Cost).
- **#14** instruction-builder ICMDA refactor (optional / cosmetic).
- **Deferred review items R1–R10, R12** (018 code review, commit `f1600e5`) — refactors / test-coverage / docs debt; tracked via `backlog.md` (D-07→#42, D-08) + epic **#25**.
- **Pass-1/Pass-2 verification checklist** (sonnet-pin token target, `before_first_line`, `link_to_moc` placement) — fold into the next live `/inbox` run.

## #9 Analyst: Audio-Klassifikation post-transcription — ✅ Resolved 2026-06-03 → #33

Die `asset`-Fehlklassifikation ist obsolet: Audios werden vor dem Dispatch herauspartitioniert (`inbox-triage.py:183`), der Analyst sieht sie nie, voice-transcriber löscht nicht. Der gültige Rest (Audio gehört zum löschbaren *source*-Set, ausgeführt von Hashi — NICHT Tomo) wandert ins Source-Model von #33. Original-Notiz: Audios werden nach Transcription nicht mehr gebraucht (User-Feedback 2026-05-01). Aktuell klassifiziert Analyst sie als `template:"asset"` mit destination `Atlas/290 Assets/295 Attachments/`, was suggeriert sie würden dorthin verschoben. Tatsächlich emittiert Pass 2 paired `delete_source` → Audio gelöscht. UI in suggestions.md verwirrend (zeigt destination die nie genutzt wird). Klassifikation sollte sein: (a) Skip + delete_source wenn transcription erfolgreich, oder (b) "delete after transcription" als expliziter Action-Type.

## #16 Suggestions.md Checkbox-Layout review — ✅ Folded into #33 2026-06-03

Root cause identifiziert: `origin` und `source` sind zwei Namen für dasselbe Konzept, und bei Voice-Items gibt es 3 Dateien (m4a / transcript=source / note). Lösung im #33-Source-Model: Terminologie auf "source" vereinheitlichen, source = {m4a + transcript}, ein "Delete source" entfernt beide via Instruction→Hashi. Original-Notiz: User-Feedback 2026-05-01, Audio+Transcript-Pairs (S02/S03/S04) UI verwirrend.

## #18 Voice-Transcript Date-Field: `recorded:` statt `updated:` — ✅ Done (commit `f6b264b`, on main 2026-05-07)

Fix Option 1 + 2 both shipped: `voice_render.py` v0.5.0 emits `recorded: <iso8601>` parsed from filename timestamps (`__YYYY-MM-DD HH:MM:SS` pattern); `inbox-analyst.md` Step 8 explicitly prefers event-date keys (`recorded`, `Recorded`, `created`, `Created`, `date`, `Date`, `event_date`, `EventDate`, `captured`, `Captured`) and ignores maintenance keys (`updated`, `Updated`, `modified`, `Modified`, `last_modified`, `LastModified`, `lastmod`). Verified via `lib/voice_render.py:_extract_recorded_iso` + `inbox-analyst.md:200-211` 2026-05-07.

## #19 Audio-Worthiness-Gap: lange Transkripte verlieren Atomic-Note — ✅ Resolved 2026-06-12 (F-41 / spec 016 shipped + live-validated)

Hälfte (a) — Worthiness gegen Full-Content — via `f6b264b`; Hälfte (c) Multi-Topic-Detection via F-41 (analyst Step 7.5 de-biased two-pass, Sonnet v0.17.0). **Live-Validation 2026-06-12:** das exakte Memo unten splittet jetzt korrekt — PKM-Gedanke → 1 `create_atomic_note`, Physio/Uro-Termine → daily-log (`log_entry`). Die befürchtete "verlorene" Atomic-Note ist da. WICHTIG: "≥2 Threads → ≥2 Atomics" war eine Fehlannahme — Termine gehören korrekt ins Tageslog, nicht als Atomic; das Memo hat *eine* evergreen-würdige Idee, also ist 1 Atomic richtig (enumeration≠emission, siehe decisions.md 2026-06-12). Original-Notiz: User-Feedback 2026-05-01. **Konkretes Symptom (gleiches Memo wie #18):** 183-Sek-Audio (~1500+ chars Transkript) mit zwei substantiellen Threads — (i) Medizin (Physio + Uro-Termin), (ii) Tomo/PKM-Gedanken (Cloud-Code, Kontextgröße, Max-Plan). Analyst emittierte nur `update_daily` (fleeting log), kein `create_atomic_note`. Die PKM-Gedanken wären atomic-note-würdig gewesen, gehen verloren. **Ursache:** Analyst verdichtet das Transkript zu einem ~350-char Summary und testet das gegen die Worthiness-Schwelle (`reasoning` < 500 chars in result.json) → fleeting log entry only. Worthiness-Scoring läuft am Summary, nicht am Original-Transkript. **Fix-Optionen:** (a) Worthiness gegen Original-Transkript-Länge prüfen, nicht gegen Summary; (b) Audio-Transkripte explizit immer `create_atomic_note` (bypass worthiness) wenn `source_type=voice-transcript`; (c) **Multi-Topic-Detection** — wenn ein Item mehrere distinct concepts hat, mehrere Aktionen emittieren (Medizin → daily-log, PKM-Gedanken → atomic-note). **Workaround heute:** Force Atomic Note Checkbox in suggestions.md ankreuzen (XDD 012). **Empfehlung:** (a) + (c) zusammen — Worthiness am Originaltranskript + Multi-Topic-Splitting. Touch points: `inbox-analyst.md` Step 7 + Worthiness-Gate-Logik + Multi-Topic-Branch in Step 8.
