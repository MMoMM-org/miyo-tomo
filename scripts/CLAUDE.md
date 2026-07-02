# scripts/ — User-invoked scripts only

## Nature of this directory

**Only user-invoked shell scripts live here.** Runtime code, tests, and
install-time helpers were split out on 2026-04-22 after a test cascade
(`test-phase1.sh` → `install-tomo.sh` at default path → `rm -rf`) wiped
real installations. The new layout contains the blast radius: anything
that can `rm -rf` lives behind an explicit confirmation and never
targets a path anyone else writes to.

Contents:

- `install-tomo.sh` — creates / updates a Tomo instance.
- `update-tomo.sh` — syncs runtime changes from the source tree into an
  existing instance.
- `backup-tomo.sh` — tars the instance to `tomo-backups/`.
- `restore-tomo.sh` — restores an instance from a backup archive.
- `cleanup-tomo.sh` — retires one instance via two SEPARATE operations:
  `registry-only` (drop it from `~/.tomo/instances.json`, print the
  on-disk paths for the user to delete themselves — never touches files)
  and `delete-disk` (also remove files; needs `--force` to skip the
  confirm). Interactive runs are asked `r/d/N`; non-interactive runs
  default to the SAFE registry-only action. `--instance <name>` targets a
  registered instance (may live outside the repo since spec 020); default
  targets the repo-root dev instance. A hardened guard refuses `/`,
  `$HOME`, the repo root, non-absolute, and shallow paths before any
  deletion. `--list` shows registered instances.
- `download-whisper-model.sh` — fetches a faster-whisper model dir.
- `lib/configure-voice.sh` — sourced by install/update for the voice
  wizard.
- `lib/begin-tomo.sh.template` — launcher template substituted by
  install-tomo.sh into `$REPO_ROOT/begin-tomo.sh`.

## What moved where

- **Runtime Python** (`cache-builder.py`, `shared-ctx-builder.py`,
  `voice-transcribe.py`, every `*-parser/render/reducer` etc.) →
  `tomo/scripts/` (source tree; `update-tomo.sh` copies into the
  instance at `$INSTANCE_PATH/scripts/`).
- **Runtime Python libs** (`kado_client.py`, `voice_render.py`,
  `voice_transcriber.py`, `obsidian_filename.py`) →
  `tomo/scripts/lib/`.
- **Runtime shell** (`tomo-statusline.sh`) → `tomo/scripts/`.
- **Integration & unit tests** (`test-phase*.sh`, `test-004-phase*.sh`,
  `test-005-phase*.sh`, `test-kado.py`, `test-splash.sh`,
  `vault-reset.sh`) → `tests/`.
- **Test fixtures** (`scripts/fixtures/`) → `tests/fixtures/`.

## Conventions

- Shell scripts must run on bash 3.2 (macOS default) — no `declare -A`.
- `$TOMO_SOURCE` = `$REPO_ROOT/tomo` — the template source dir.
- Template source: `tomo/dot_claude/` (visible name, renamed at install
  → `.claude/`).
- Instance destination paths keep `.claude/` (Claude Code runtime
  requires it).
- Any `rm -rf` must be guarded by (a) a user confirmation OR (b) a
  path check that refuses the repo root / outside-repo targets OR (c)
  strict scoping to a tmpdir. See `cleanup-tomo.sh` for the pattern.
- Integration tests that need an install MUST pass
  `--instance-location <TMPDIR> --instance-name <isolated>
  --home-dir <TMPDIR> --config-file <TMPDIR>/*.json` so the test
  never touches `$REPO_ROOT/tomo-instance`.
