---
title: "Phase 2: Python modules + CLI script (standalone)"
status: done
version: "1.1"
phase: 2
---

# Phase 2: Python modules + CLI script (standalone)

## Phase Context

**Dependencies**: None on Phase 1 in dev (we test against a manually-installed
faster-whisper); production runs require Phase 1 image. Can develop in parallel.

**Key files**:
- `scripts/lib/voice_transcriber.py` (new — faster-whisper wrapper)
- `scripts/lib/voice_render.py` (new — markdown renderer)
- `scripts/voice-transcribe.py` (new — CLI)
- `tests/voice/` (new — pytest fixtures)

**Out of scope this phase**: agents, orchestrator integration, kado-write.
We prove the script runs against a real audio file and produces correct markdown.

---

## Tasks

- [x] **T2.1 `scripts/lib/voice_transcriber.py`** `[activity: backend]`

  1. Prime: Read solution.md § Python Modules for the dataclass shapes and
     `transcribe()` signature. Confirm `faster-whisper` 1.x API: `WhisperModel(model_size_or_path, device, compute_type)`, `model.transcribe(audio_file, vad_filter=, vad_parameters=, temperature=, language=)`.
  2. Implement: Module with `Segment`, `TranscriptResult` dataclasses,
     `load_model(model_dir: Path) -> WhisperModel`, and
     `transcribe(model, audio_path, language=None) -> TranscriptResult`.
     CPU-only, int8 compute, VAD on with min_silence=500ms, temperature=0.
  3. Validate: Module imports cleanly. Type hints present. No prints — all
     output via return values (caller decides logging).

- [x] **T2.2 `scripts/lib/voice_render.py`** `[activity: backend]`

  1. Prime: Read PRD § F3 for the exact markdown shape (plain-text metadata
     block, `---` separator, audio embed, per-segment callouts with `mm:ss`).
  2. Implement: Pure function `render_markdown(result: TranscriptResult) -> str`.
     - First lines: `source:`, `transcribed:`, `model:`, `language:`, `duration_sec:`
     - Blank line, `---`, blank line
     - `![[<audio_filename>]]`, blank line
     - For each segment: `> [!voice] mm:ss\n> <text>\n` + blank line
     - Final newline
  3. Validate: Pytest snapshot test against a stub `TranscriptResult` —
     output matches expected string exactly (deterministic).

- [x] **T2.3 `scripts/voice-transcribe.py` (batch CLI)** `[activity: backend]`

  1. Prime: Read existing CLI patterns in `scripts/*.py` (e.g. `instruction-render.py`)
     for argparse style, error handling, exit codes. Confirm the batch shape
     in `solution.md § scripts/voice-transcribe.py`.
  2. Implement: argparse with `audio_paths` positional (`nargs="+"`),
     `--model-dir` (default `/tomo/voice/models/faster-whisper-medium`),
     `--language` (default None → auto-detect). **Load model ONCE**, then
     loop over `audio_paths`, accumulating per-file results. Emit a single
     JSON manifest on stdout:
     ```json
     {"model_dir": "...", "results": [
       {"audio": "x.m4a", "target": "x.md", "markdown": "...", "error": null},
       {"audio": "y.m4a", "target": "y.md", "markdown": null,
        "error": {"code": "transcription_error", "detail": "..."}}
     ]}
     ```
     Per-file errors go INSIDE the manifest (never crash the whole batch).
     Exit codes: 0 = batch completed (inspect `results[].error`), 2 = usage
     error, 3 = model_dir missing (fatal, no files attempted).
  3. Validate: `python3 scripts/voice-transcribe.py --help` prints usage.
     Missing model-dir → exit 3. One real file + one bogus path in same
     batch → exit 0, manifest has `markdown` for the real one and `error`
     for the bogus one.

- [x] **T2.4 Test fixture** `[activity: testing]`

  1. Prime: Need a small real audio file for tests — ideally 3-5 seconds,
     known content, royalty-free.
  2. Implement: Generate or record `tests/voice/fixtures/hello-world.wav`:
     - 16 kHz mono WAV (Whisper-native, avoids ffmpeg dependency for unit test).
     - Spoken: "Hello, this is a test." in English, OR a German equivalent.
     - Use `say` (macOS) or eSpeak to generate; commit ≤100 KB file.
  3. Validate: File exists, plays back, contains the spoken text.

- [x] **T2.5 Pytest unit tests** `[activity: testing]`

  1. Prime: Existing test structure (if any) under `tests/` — match style.
     Note: tests requiring a model file are gated by pytest marker.
  2. Implement:
     - `tests/voice/test_render.py`: snapshot test for `render_markdown()`
       (no model needed, fast, always runs).
     - `tests/voice/test_transcriber.py`: marked `@pytest.mark.voice_model`.
       Loads tiny model from `$TOMO_TEST_MODEL_DIR` env var, transcribes
       fixture, asserts segment count > 0 AND text contains "test" (or "Test").
     - `pytest.ini` or `pyproject.toml`: register `voice_model` marker as
       opt-in (not run by default).
  3. Validate: `pytest tests/voice/test_render.py -v` — passes without model.
     `TOMO_TEST_MODEL_DIR=path/to/tiny pytest -m voice_model -v` — passes
     with model.

- [x] **T2.6 Manual CLI smoke test** `[activity: validate]`

  - Download tiny model manually (or use Phase 1's download script).
  - **Single-file batch**:
    `python3 scripts/voice-transcribe.py tests/voice/fixtures/hello-world.wav --model-dir <tiny-dir>`
    → stdout is a JSON object with `results[0].markdown` containing
    `source: hello-world.wav`, `---` separator, `![[hello-world.wav]]` embed,
    and at least one `> [!voice] 00:00` callout.
  - **Multi-file batch** (copy the fixture to `hello-world-2.wav` first):
    `python3 scripts/voice-transcribe.py hello-world.wav hello-world-2.wav --model-dir <tiny-dir>`
    → manifest has two `results[]` entries, both with `markdown` populated.
    Wall-clock should be ~1× load + 2× transcribe (not 2× load).

- [x] **T2.7 Phase Validation** `[activity: validate]`

  - All unit tests green (with and without `voice_model` marker).
  - CLI runs end-to-end on fixture audio and produces valid markdown
    matching PRD § F3 shape exactly.
  - No imports from `faster_whisper` in `voice_render.py` (separation of
    concerns — render is pure, transcribe is engine-coupled).
  - Module versions: each `scripts/lib/*.py` and `scripts/*.py` has a
    `# version: 0.1.0` header per project convention.
