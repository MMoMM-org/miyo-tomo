# Context — Tomo
<!-- Current sprint focus, active work, known blockers. Updated: 2026-05-01 -->
<!-- This file is short-lived — prune entries older than 2 weeks via /memory-cleanup -->

## Open tasks from session 2026-05-01

Persisted here so they survive session resets. Move to backlog.md when long-term, mark resolved when done.

### Operational follow-ups (do soon)

- **#11 Origin/main pushen** — lokaler `main` ist 11+ Commits voraus von `origin/main`. Inhalt: outbox archive, Hashi handoff drafts, link-anchor + paired-delete feature, spinner verbs, hashi-spinner-verbs, skill-paths + instruction-builder script + audit fixes, version bumps, /inbox dispatch fix, troubleshooting cutoff doc, sonnet pin in settings.json, placement+position bugfix.
- **#12 Hashi response handoffs archivieren** — `_outbox/for-hashi/` enthält uncommitted `status: pending → done` flips auf `2026-04-30_tomo-to-hashi_link-placement-mode-response.md` und `2026-04-30_tomo-to-hashi_move-note-implicit-origin-delete-response.md`. Hashi hat geacknowledged. Nach Pattern vom Session-Anfang: nach `_archive/outbox/2026-04/` verschieben + committen.
- **#13 Memory: 3 pending learnings + 2026-05-01 learnings** — Session-Start hatte 3 pending learnings in der Queue. Dazu kommen aus dieser Session: (a) Impersonation vs Dispatch ~60% Token-Differenz, (b) haiku ist nicht stark genug für STRICT-orchestration agents (zweimal Pass 2 selbst gerendert), (c) `instruction-render.py:1254` `read_template("asset")` ist ein Auto-Render-on-template-Fallstrick, (d) Parent-Modell-Inheritance über `settings.json model:` field steuerbar (Pass 1 Test ausstehend), (e) Reducer-Field-Drop-Pattern (position dropped beim Übergang result.json → suggestions.md → instructions.json — gleiches Risiko bei jedem neuen Feld), (f) `link_to_moc` placement default war `inside` statt vereinbartem `after` (Contract-Drift in der Implementierung). `/memory-add` laufen lassen.

### Technische Bug-Fixes & Verifikation

- **#9 Analyst: Audio-Klassifikation post-transcription korrigieren** — Audios werden nach Transcription nicht mehr gebraucht (User-Feedback 2026-05-01). Aktuell klassifiziert Analyst sie als `template:"asset"` mit destination `Atlas/290 Assets/295 Attachments/`, was suggeriert sie würden dorthin verschoben. Tatsächlich emittiert Pass 2 paired `delete_source` → Audio gelöscht. UI in suggestions.md verwirrend (zeigt destination die nie genutzt wird). Klassifikation sollte sein: (a) Skip + delete_source wenn transcription erfolgreich, oder (b) "delete after transcription" als expliziter Action-Type.
- **#16 Suggestions.md Checkbox-Layout review** — User-Feedback 2026-05-01: bei Audio+Transcript-Pairs (S02/S03/S04) ist die UI verwirrend. Detail-Diskussion deferred bis nach Hashi-Bug-Pass. "Keep origin" Default `false` ist korrekt für Audios; Layout-Probleme bei der Checkboxen-Gruppe noch zu prüfen.
- **#18 Voice-Transcript Date-Field: `recorded:` statt `updated:`** — User-Feedback 2026-05-01. Zwei Seiten: (a) **Voice-Transcriber-Seite (sauber)**: statt `updated:` ein `recorded:` Feld in den Transcript-Frontmatter schreiben, abgeleitet aus dem Filename (z.B. `2026-05-01-08-30_voice-memo.m4a` → `recorded: 2026-05-01T08:30`). `updated:` ganz weglassen. (b) **Analyst-Seite**: `updated:` als Date-Source explizit ignorieren (es ist ein Maintenance-Timestamp, kein Event-Datum). Touch points: voice-transcriber pipeline + `inbox-analyst.md` date-source priority list + ggf. `daily_log.date_source_priority` in vault-config.
- **#19 Audio-Worthiness-Gap: lange Transkripte verlieren Atomic-Note** — User-Feedback 2026-05-01. Symptom: 183-Sek-Audio (~1500+ chars Transkript mit mehreren Themen) → Analyst emittiert nur `update_daily`, kein `create_atomic_note`. Ursache: Analyst verdichtet das Transkript zu einem ~350-char Summary und testet das gegen die Worthiness-Schwelle. Das verdichtete Summary fällt unter den Threshold (< 500 chars `reasoning` aus result.json) → fleeting log entry only, Inhalt geht verloren. Mögliche Fixes: (a) Worthiness gegen Original-Transkript-Länge prüfen, nicht gegen Summary; (b) Audio-Transkripte explizit immer `create_atomic_note` (bypass worthiness) wenn `source_type=voice-transcript`; (c) Multi-Theme-Detection → mehrere kleine atomic notes statt ein Summary. Touch points: `inbox-analyst.md` Step 7 + Worthiness-Gate-Logik.

### Performance / Architektur (eigene Sessions)

- **#15 Pass 2 Happy-Path als deterministisches Script (Option B/C)** — `scripts/run-pass2.sh` schreiben das die 5 Pass-2-Scripts in fester Reihenfolge ausführt. Agent ruft nur noch run-pass2.sh + handelt Step 2.5 Fan-Resolve und Error-Recovery. Erwartete Ersparnis: 80-90% der Subagent-Tokens.
- **#17 Pass 1 Token-Audit: Easy Wins identifizieren** — Pass 1 verbraucht 14.7M tokens vs Pass 2 mit 440k (33× teurer). Hot Path: 19× inbox-analyst subagents (~370k each = 7.0M) + Parent /inbox session (7.14M). Investigationspunkte: Skills-Cache pro Dispatch, deterministische Arbeit auslagern, Bündelung von Steps, Item-Batching. Wichtig: nach `settings.json model: sonnet` Sync den Effekt auf Parent zuerst messen. Erwartetes Ziel: Pass 1 von 15M auf 5-7M.

### Optional / Cosmetic

- **#14 instruction-builder ICMDA-Refactor (optional)** — Body-Layout entspricht nicht TCS-ICMDA-Convention (Identity/Constraints/Mission/Decision/Activities/Output). Funktional kein Gewinn, nur Convention-Conformance. Nur angehen wenn andere Agents auch konvertiert werden.

## Verifikation für nächste Pass-1/Pass-2 Runs

- Sonnet-Pin in `settings.json` greift → Parent /inbox sollte unter 2.5M tokens liegen (heute 7.14M auf opus)
- `before_first_line` für Morgen-Routine (oder ähnliche Notes mit Position-Hinweis im Content) erscheint in `instructions.json` als `position: before_first_line` — nicht mehr als Fallback `after_last_line`
- `link_to_moc` Actions emittieren `placement: "after"` statt `"inside"`
