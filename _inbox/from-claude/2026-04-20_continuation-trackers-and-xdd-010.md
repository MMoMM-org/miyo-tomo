---
from: claude
to: claude-next-session
date: 2026-04-20
status: pending
priority: high
---

# Continuation — 2026-04-20 afternoon session

## Session summary (what shipped)

**Repo changes on `main`** (all merged + pushed):

| Commit | Subject |
|--------|---------|
| `70bb33a` | Rename `tomo/.claude/` → `tomo/dot_claude/` (template source) |
| `e18164d` | 007/008 spec status sync |
| `c7a8193` | Retire vault-explorer Step 3 (Frontmatter Detection) |
| `7f9d779` | Wizard skills → `<name>/SKILL.md` dir format |
| `efdb957` | Reference skills → `<name>/SKILL.md` dir format (all 4) |
| `baebf5c` | install-tomo.sh: no more `git init` in tomo-instance |
| `50ef8ac` | XDD 011 spec + `backup-tomo.sh` + `restore-tomo.sh` |
| `8882f58` | Backup fix: instanceName in filename, correct `homePath` field |
| `a1d6707` | vault-explorer Step 7 v0.8.0: template + recent daily notes, no gate |

**Instance state (tomo-instance is gitignored; changes not in repo commits)**:

- Fresh install 2026-04-20, 24 tracker fields migrated from
  `daily_log.trackers` (where old Step 7 wrote them by mistake) to correct
  schema location `trackers.daily_note_trackers.{yesterday_fields,today_fields}`
  and `trackers.end_of_day_fields.fields`.
- YAML valid, counts: 5 yesterday + 11 today + 8 end_of_day = 24 total.
- Backup archive exists in `tomo-backups/` (sibling to tomo-instance).

## Immediate next step

vault-config.yaml has 24 tracker fields at the correct schema location BUT
no `syntax`/`description`/`positive_keywords`/`negative_keywords` yet beyond
the brief one-line descriptions copied from the migration. Run the wizard
to populate them:

1. In running Tomo session: `/tomo-trackers-wizard`
   (or `/tomo-setup trackers` — delegates to same skill).

2. Wizard should now find 24 fields at the correct schema location.

3. Walk per-field: syntax (`inline_field` is the default — it's what
   `t_day_privat.md` uses), description (pre-filled, edit if needed),
   positive + negative keywords. User will likely want to keep most
   syntax as inline_field and add keywords for inbox classification
   accuracy.

## Known-open items after this

### XDD 010 — Custom File Picker (branch `feat/xdd-010-impl`, Phase 1 partial)

Branch not yet merged to main. Contains:

- `tomo/dot_claude/scripts/file-suggestion.sh` skeleton with prefix routing
- settings.json fileSuggestion entry
- install/update script copy steps
- `scripts/spikes/xdd-010/` — live-test scripts for T1.1 (exit-code
  behavior) and T1.2 (suffix-marker viability) that NEED user to run in
  a Tomo session to confirm behavior before Phase 2 handler impl

Next: run the spikes to resolve T1.1-T1.3, then implement Phase 2
(handlers for open-notes / inbox / vault).

### XDD 008 — Deterministic Instruction Render (PLAN, not started)

Plan-dir exists with 3 phases. See
`docs/XDD/specs/008-deterministic-instruction-render/plan/`. Pending
because user prioritized 010. Tomo Hashi plugin depends on this.

### XDD 009 — Voice Memo Transcription (PLAN, not started)

Full spec + plan. Depends on faster-whisper + ffmpeg in Docker (needs
build change). See `docs/XDD/specs/009-voice-memo-transcription/`.

### Lean follow-ups (backlog)

- **F-28** — install-tomo.sh should copy profile's `frontmatter_defaults`
  into vault-config.yaml `frontmatter:` so `token-render.py` finds token
  defaults without relying on the retired vault-explorer Step 3.
- **XDD 011 F3** — install-time warning about nested-git trap +
  `git clean -fdX` risk. Deferred from XDD 011 MVP.
- **Tracker bootstrap wizard mode** (discussed, not speced) — if future
  users hit an empty trackers case, a wizard path that accepts
  user-listed field names would be the clean solution.

## Useful state

- Active memory notes relevant to this continuation:
  - `project_tomo_hashi_plugin.md` — Obsidian plugin renamed from "Seigyo"
  - `feedback_skill_format_distinction.md` — all skills need dir format
  - `feedback_no_nested_git_in_bind_mounts.md` — why we removed git init
  - `feedback_profile_gap_decisions.md` — frontmatter baselines YAGNI

- Open branches (local, not pushed):
  - `feat/xdd-010-impl` — commit `ae03886` (Phase 1 partial)
  - `fix/vault-config-trackers-location` — no commits (instance gitignored,
    edits applied directly to `tomo-instance/config/vault-config.yaml`)
  - `chore/handoff-continuation-2026-04-20` — this file

- Backup: `tomo-backups/tomo-instance-2026-04-20_*.tar.gz` (latest via
  fixed script includes `tomo-home/` ~5MB).

## Action required on pickup

1. `inbox-set-status.sh in-progress` on this file when starting.
2. Confirm tracker fields are usable via `/tomo-trackers-wizard`.
3. Either: (a) continue wizard metadata work, or (b) pick one of
   XDD 010 / 008 / 009.
4. When picked up direction is complete, `inbox-set-status.sh done "<note>"`.

## References

- Session transcripts: `~/.claude/projects/-Volumes-Moon-Coding-MiYo-Tomo/`
  (JSONL, for debugging if needed).
