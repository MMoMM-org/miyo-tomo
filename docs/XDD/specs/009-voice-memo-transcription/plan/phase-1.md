---
title: "Phase 1: Install wizard + Dockerfile + model download"
status: code-complete
version: "1.1"
phase: 1
---

# Phase 1: Install wizard + Dockerfile + model download

## Phase Context

**Dependencies**: None — first phase, host-side enablement.

**Key files**:
- `scripts/install-tomo.sh` (add `configure_voice()` function)
- `scripts/update-tomo.sh` (call same wizard)
- `tomo-install.json` (schema extension)
- `docker/Dockerfile` (ffmpeg + conditional faster-whisper)

**Out of scope this phase**: any Python transcription logic, agents, or
orchestrator changes. We only enable the *capability* and prove the model
arrives in the right place.

---

## Tasks

- [x] **T1.1 Add `configure_voice()` function to install-tomo.sh** `[activity: backend]` — implemented in `scripts/lib/configure-voice.sh`, sourced from install-tomo.sh (commit c7c9688)

  1. Prime: Read `install-tomo.sh` to find a sensible insertion point near
     existing config-collection steps. Note existing `print_step` / `print_ok`
     / `print_warn` helpers and how they read into `tomo-install.json` via jq.
  2. Implement: New bash function `configure_voice()` matching the stateful
     flow in `solution.md § Install Wizard Flow`:
     - Read current `voice.enabled` and `voice.model` from
       `tomo-install.json` (default to disabled if missing).
     - Branch on Case A (currently disabled) vs Case B (currently enabled).
     - Show model table when enabling/changing.
     - Persist updated `voice: { enabled, model, language }` via jq.
     - Export `VOICE_ENABLED=1|0` for the Docker build step.
     - Use existing helpers (`print_step`, `read -p`, etc.) — no new colors/formatting.
  3. Validate: bash 3.2 compatible (no `declare -A`, no `[[` extended tests
     beyond what bash 3.2 supports). `bash -n install-tomo.sh` passes.

- [x] **T1.2 Mirror `configure_voice()` call in update-tomo.sh** `[activity: backend]` — factored into `scripts/lib/configure-voice.sh` + sourced from both scripts; update-tomo.sh persists voice block via jq (c7c9688)

  1. Prime: Read `update-tomo.sh`. It already updates managed files; we want
     it to also re-prompt voice settings on update so users can change
     models without a full reinstall.
  2. Implement: Source the function from `install-tomo.sh` OR factor it into
     `scripts/lib/configure-voice.sh` and source from both. Latter is cleaner.
  3. Validate: Running `update-tomo.sh` triggers the wizard; pressing Enter
     keeps current settings (true no-op).

- [x] **T1.3 Model download helper** `[activity: backend]` — `scripts/download-whisper-model.sh` uses HF API + curl; tiny model E2E verified (83 MB, 6 files)

  1. Prime: HuggingFace `Systran/faster-whisper-<size>` repos contain a
     known set of files: `model.bin`, `tokenizer.json`, `vocabulary.txt`,
     `config.json`. Each downloadable via `https://huggingface.co/<repo>/resolve/main/<file>`.
  2. Implement: `scripts/download-whisper-model.sh <size> <dest_dir>`:
     - Validate size against known list (`tiny base small medium large-v3`).
     - For each known file in the manifest, `curl -L --fail -o <dest>/<file> <url>`.
     - Verify file sizes are non-zero after download.
     - Print final disk-size of `<dest_dir>`.
     - Exit non-zero on any failure; partial dir cleaned up.
  3. Validate: Run with `tiny` (39 MB, fast). Verify all 4 files arrive,
     `du -sh` matches expected size, exit 0.

- [x] **T1.4 Dockerfile: ffmpeg always, faster-whisper conditional** `[activity: backend]` — ffmpeg + python3-pip always; `ARG VOICE_ENABLED=0` gates `pip install faster-whisper>=1.0,<2`; `VOLUME /tomo/voice` declared

  1. Prime: Read `docker/Dockerfile`. Note the existing apt-get RUN block
     and `python3` / `python3-yaml` packages.
  2. Implement:
     - Add `ffmpeg python3-pip` to the existing apt-get install line.
     - Add `ARG VOICE_ENABLED=0` after existing ENV block.
     - Add conditional RUN: `if [ "$VOICE_ENABLED" = "1" ]; then pip install --break-system-packages --no-cache-dir faster-whisper==1.* ; fi`
     - Add `VOLUME /tomo/voice` for the model bind-mount.
     - Bump version comment in Dockerfile header.
  3. Validate: Build with `--build-arg VOICE_ENABLED=0` → image builds, no
     pip step ran (verify with `docker history`). Build with `=1` → faster-whisper
     present (`docker run --rm <img> python3 -c "import faster_whisper"`).

- [x] **T1.5 begin-tomo.sh: pass VOICE_ENABLED to docker build/run** `[activity: backend]` — build-arg + label (`tomo.voice_enabled`) with drift detection to auto-rebuild on voice toggle; `-v voice:/tomo/voice:ro` when enabled

  1. Prime: Read `begin-tomo.sh.template` (NOT the generated file). Find
     the docker build invocation and the docker run mount section.
  2. Implement:
     - Read `voice.enabled` from `tomo-install.json`; export as `VOICE_ENABLED`.
     - On docker build: pass `--build-arg VOICE_ENABLED=$VOICE_ENABLED`.
     - On docker run: if enabled, add `-v "$INSTANCE_PATH/voice:/tomo/voice:ro"`.
  3. Validate: Render template via install, inspect generated `begin-tomo.sh`
     to confirm both the build arg and the volume mount appear when enabled,
     are absent (or `=0` only) when disabled.

- [ ] **T1.6 Phase Validation** `[activity: validate]` *(pending — host-only, Docker required)*

  Sandbox-side done: syntax-check on all 5 scripts, wizard state transitions
  (non-interactive + interactive), HF download proven with tiny model, jq
  write-back round-trip on voice block.

  Manual end-to-end check on host (no agents, no transcription yet — just provisioning):
  - Run `install-tomo.sh` on a fresh instance, choose voice=no.
    → `tomo-install.json` has `voice: { enabled: false }`. Image builds without faster-whisper.
  - Re-run `install-tomo.sh`, choose voice=yes + tiny model (fast for testing).
    → Model dir `tomo-instance/voice/models/faster-whisper-tiny/` populated with 4 files.
    → Image rebuild includes faster-whisper.
    → `docker run --rm <img> python3 -c "from faster_whisper import WhisperModel; print('ok')"` prints "ok".
  - Re-run `install-tomo.sh`, press Enter through wizard.
    → No download, no rebuild. Settings preserved.
  - Re-run `install-tomo.sh`, change to base model.
    → Only base model dir downloaded; tiny stays on disk; no image rebuild.
  - Re-run `install-tomo.sh`, choose disable.
    → `voice.enabled=false`. Next image build excludes faster-whisper.
