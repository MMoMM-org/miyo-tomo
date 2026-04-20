---
title: "Voice Memo Transcription — Solution Design"
status: draft
version: "0.1"
---

# Solution Design Document

## Architecture Overview

```
┌─ HOST (macOS) ─────────────────────────────────────────────┐
│                                                            │
│  install-tomo.sh                                           │
│    └─ configure_voice()        ← new wizard function       │
│          ├─ asks enable? model? language?                  │
│          ├─ writes tomo-install.json → voice: {...}        │
│          └─ downloads model → tomo-instance/voice/models/  │
│                                                            │
│  tomo-instance/voice/models/faster-whisper-medium/         │
│    (mounted into container at /tomo/voice/models/)         │
└────────────────────────────────────────────────────────────┘
                             │
                             ▼  (bind mount)
┌─ DOCKER CONTAINER ─────────────────────────────────────────┐
│                                                            │
│  Dockerfile deltas:                                        │
│    + apt-get install ffmpeg python3-pip                    │
│    + ARG VOICE_ENABLED                                     │
│    + if VOICE_ENABLED: pip install faster-whisper          │
│                                                            │
│  /inbox run → inbox-orchestrator agent                     │
│     │                                                      │
│     ├─ Phase 0 (NEW): call voice-transcriber agent         │
│     │     │                                                │
│     │     ├─ kado-search audio files in inbox              │
│     │     ├─ for each: python3 scripts/voice-transcribe.py │
│     │     ├─ captures stdout (rendered markdown)           │
│     │     └─ kado-write sibling <basename>.md              │
│     │                                                      │
│     ├─ Phase A (existing): shared-ctx + state-file         │
│     ├─ Phase B (existing): fan-out subagents               │
│     └─ Phase C (existing): reduce + render + kado-write    │
│                                                            │
│  scripts/voice-transcribe.py  ← CLI entry                  │
│    └─ scripts/lib/voice_transcriber.py  ← faster-whisper   │
└────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### Install-side
- **`install-tomo.sh :: configure_voice()`** — ask enable/model/language,
  persist to `tomo-install.json`, download model.
- **`tomo-install.json :: voice`** — source of truth for install-time choices.
- **Dockerfile** — install ffmpeg unconditionally, `faster-whisper` only when
  `VOICE_ENABLED=1` build arg is set.

### Runtime-side
- **`scripts/voice-transcribe.py`** — CLI. Reads audio path from argv, prints
  rendered markdown to stdout. Scratch writes (if any) under `tomo-tmp/`.
  Never touches the vault.
- **`scripts/lib/voice_transcriber.py`** — thin wrapper over
  `faster_whisper.WhisperModel`. Returns a `TranscriptResult` dataclass
  (segments + metadata).
- **`scripts/lib/voice_render.py`** — deterministic markdown renderer:
  `TranscriptResult` → markdown string (same pattern as `instruction-render.py`).
- **`voice-transcriber` agent** — orchestrates discovery and kado-write calls.
  Invoked by `inbox-orchestrator` as pre-Phase-0 step.

## Install Wizard Flow

The wizard ALWAYS runs during `install-tomo.sh` and is stateful — it reads
the current `tomo-install.json` first and offers the current state as the
default action. No separate `--reconfigure-voice` flag needed.

```
install-tomo.sh :: configure_voice()
───────────────────────────────────
1. Read tomo-install.json → current = voice.enabled, voice.model.
2. Branch on current state:

   ── Case A: currently DISABLED (or not yet configured) ──
   2A. Ask: "Enable voice memo transcription? (default: no) [y/N]"
       If no → write voice: { enabled: false }. Done.
       If yes → continue to step 3.

   ── Case B: currently ENABLED with model X ──
   2B. Ask: "Voice transcription is currently ENABLED with model 'X'.
            Keep / Change model / Disable? [K/c/d] (default: keep)"
       Keep → no changes. Done.
       Disable → set enabled=false. Optionally prompt: "Remove model
                 files (~Y MB)? [Y/n]". Done.
       Change → continue to step 3.

3. Show model table:

       size       disk     quality
       tiny       39 MB    fast, weak German
       base      142 MB    decent English
       small     466 MB    solid German
       medium    1.5 GB    very good German   ← recommended
       large-v3  2.9 GB    best quality, slowest

   Default = current model if changing, else "medium".

4. Ask optional language hint: "Primary audio language? [de/en/auto]
   (default: current or 'de')"

5. Persist tomo-install.json:
     voice:
       enabled: true
       model: <chosen>
       language: <chosen>

6. Model-files step (only what's needed):
   - If chosen model dir already exists on disk → no download.
   - Otherwise: download huggingface.co/Systran/faster-whisper-{chosen}
     → tomo-instance/voice/models/faster-whisper-{chosen}/
     (curl + known-file manifest; no Python needed on host).
   - Optionally clean up unused model dirs (ask user; default keep
     for fast switch-back).

7. Set Docker build env: VOICE_ENABLED=1.
   Image rebuild only happens if VOICE_ENABLED transitioned
   (off ↔ on). Pure model swap = no rebuild needed (model is
   bind-mounted at runtime).
```

**Idempotency**: re-running with no intent to change → user picks "Keep" →
zero work done, zero downloads.

**Model swap path**: re-run wizard → "Change" → pick new size → only the
new model dir is downloaded; old one stays unless user opts to clean up.

**Disable path**: re-run wizard → "Disable" → `enabled=false`, optional
model cleanup, next image build drops faster-whisper (~200 MB smaller).

## Dockerfile Deltas

```Dockerfile
# (existing base stage unchanged)

# Add ffmpeg — unconditionally, tiny footprint (~60 MB)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Conditional Whisper
ARG VOICE_ENABLED=0
RUN if [ "$VOICE_ENABLED" = "1" ]; then \
      pip install --break-system-packages --no-cache-dir \
        faster-whisper==1.* ; \
    fi

# Volume mount point for models (host → container)
VOLUME /tomo/voice
```

Build-time penalty when enabled: ~200 MB (faster-whisper + ctranslate2 wheels).
Build-time penalty when disabled: 0 (pip step is a no-op). Model is NOT baked
in; it lives on host and mounts at runtime.

## Python Modules

### `scripts/lib/voice_transcriber.py`

```python
from dataclasses import dataclass
from pathlib import Path
from faster_whisper import WhisperModel

@dataclass
class Segment:
    start: float   # seconds
    end: float
    text: str

@dataclass
class TranscriptResult:
    audio_path: Path
    model_name: str
    language: str
    duration_sec: float
    segments: list[Segment]

def load_model(model_dir: Path) -> WhisperModel:
    # cpu-only, int8 compute for footprint/speed on ARM
    return WhisperModel(str(model_dir), device="cpu", compute_type="int8")

def transcribe(model: WhisperModel, audio_path: Path,
               language: str | None = None) -> TranscriptResult:
    segments_iter, info = model.transcribe(
        str(audio_path),
        language=language,              # None → auto-detect
        vad_filter=True,                # skip silences
        vad_parameters={"min_silence_duration_ms": 500},
        temperature=0.0,                # deterministic
    )
    segments = [Segment(s.start, s.end, s.text.strip())
                for s in segments_iter]
    return TranscriptResult(
        audio_path=audio_path,
        model_name=f"faster-whisper-{info.model_name_or_size}",
        language=info.language,
        duration_sec=info.duration,
        segments=segments,
    )
```

### `scripts/lib/voice_render.py`

```python
def render_markdown(result: TranscriptResult) -> str:
    lines = [
        f"source: {result.audio_path.name}",
        f"transcribed: {datetime.now().isoformat(timespec='seconds')}",
        f"model: {result.model_name}",
        f"language: {result.language}",
        f"duration_sec: {int(result.duration_sec)}",
        "",
        "---",
        "",
        f"![[{result.audio_path.name}]]",
        "",
    ]
    for seg in result.segments:
        mmss = f"{int(seg.start) // 60:02d}:{int(seg.start) % 60:02d}"
        lines.append(f"> [!voice] {mmss}")
        lines.append(f"> {seg.text}")
        lines.append("")
    return "\n".join(lines)
```

### `scripts/voice-transcribe.py`

```python
#!/usr/bin/env python3
# version: 0.1.0
"""CLI: transcribe one audio file, emit rendered markdown to stdout.

Usage: voice-transcribe.py <audio_path> [--model-dir PATH] [--language LANG]
"""
import sys, json, argparse
from pathlib import Path
from lib.voice_transcriber import load_model, transcribe
from lib.voice_render import render_markdown

MODEL_DIR_DEFAULT = Path("/tomo/voice/models/faster-whisper-medium")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("audio_path", type=Path)
    p.add_argument("--model-dir", type=Path, default=MODEL_DIR_DEFAULT)
    p.add_argument("--language", default=None)
    args = p.parse_args()

    if not args.audio_path.exists():
        print(json.dumps({"error": "audio_not_found"}), file=sys.stderr)
        sys.exit(2)

    model = load_model(args.model_dir)
    result = transcribe(model, args.audio_path, language=args.language)
    sys.stdout.write(render_markdown(result))

if __name__ == "__main__":
    main()
```

## Agent: `voice-transcriber`

New agent at `tomo/dot_claude/agents/voice-transcriber.md`.

Responsibilities:
- Check `tomo-install.json :: voice.enabled`. If false → return empty summary.
- `kado-search` inbox directory for audio extensions (`.m4a .mp3 .wav .ogg .opus .flac .aac`).
- For each audio path:
  1. Check if sibling `.md` already exists via `kado-read`. If yes → skip.
  2. Invoke `Bash`: `python3 scripts/voice-transcribe.py <path>` (one command per call, per existing orchestrator guardrails).
  3. Parse stdout → pass to `kado-write` for `<basename>.md`.
  4. On non-zero exit: call `kado-write` with error marker markdown (`<basename>.transcribe-error.md`).
- Return JSON summary: `{ transcribed: N, skipped: M, errors: [...] }`.

## Orchestrator Integration

`inbox-orchestrator.md` gains a new Phase 0, before Phase A:

```
Phase 0 (NEW, conditional):
  1. Read tomo-install.json. If voice.enabled != true → skip Phase 0.
  2. Invoke voice-transcriber agent with inbox path.
  3. Wait for completion, log summary.
  4. Continue to Phase A — newly-written .md files now visible to discovery.
```

No changes to Phase A/B/C beyond that.

## Data Flow (one audio file)

```
user drops memo.m4a in inbox
  │
/inbox runs
  │
orchestrator → voice-transcriber agent
                 │
                 ├─ kado-search *.m4a → [memo.m4a]
                 ├─ kado-read memo.md → not found
                 ├─ Bash: python3 voice-transcribe.py memo.m4a
                 │   │
                 │   └─ load model (int8, cpu) → transcribe → render MD
                 │       stdout: (rendered markdown)
                 │
                 └─ kado-write memo.md ← stdout
                 │
                 summary: {transcribed: 1, skipped: 0, errors: []}
  │
orchestrator → Phase A (shared-ctx), B (fan-out), C (reduce + render)
  └─ memo.md is now one of the fleeting notes analyzed by inbox-analyst
```

## Config Schema

### `tomo-install.json`

```json
{
  "voice": {
    "enabled": true,
    "model": "medium",
    "language": "de"
  }
}
```

All three fields optional when `enabled=false`.

### `vault-config.yaml` (optional)

```yaml
voice:
  language: de              # optional override for install-time setting
  exclude:                  # optional glob list
    - "+/recorded-meetings/**"
  warn_minutes: 20          # long-audio warning threshold
```

## Error Handling

| Condition | Behaviour |
|---|---|
| Audio file unreadable | `voice-transcribe.py` exit 2; agent writes `.transcribe-error.md` with stderr |
| Model dir missing at runtime | `voice-transcriber` agent logs warning and skips voice entirely (no crash — graceful degrade) |
| Transcription OOM or crash | Catch in agent, write error marker, continue to next audio |
| Audio > `warn_minutes` | Script logs warning on stderr, proceeds |
| Orchestrator unable to kado-write transcript | Standard orchestrator error — same as any vault-write failure |

## File Layout

```
tomo/
├── dot_claude/
│   └── agents/
│       └── voice-transcriber.md          NEW
scripts/
├── voice-transcribe.py                    NEW (CLI)
└── lib/
    ├── voice_transcriber.py               NEW (faster-whisper wrapper)
    └── voice_render.py                    NEW (markdown renderer)
docker/
└── Dockerfile                             MODIFIED (ffmpeg + conditional pip)
scripts/
└── install-tomo.sh                        MODIFIED (configure_voice())

tomo-instance/                             (at runtime)
└── voice/
    └── models/
        └── faster-whisper-medium/         (host-downloaded, mounted)
            ├── model.bin
            ├── tokenizer.json
            ├── vocabulary.json
            └── config.json
```

## Performance Targets

| Scenario | Target |
|---|---|
| 5-min voice memo, medium model, M-series CPU, int8 | ≤ 5 min wall-clock |
| 30-sec voice memo (typical "thought capture") | ≤ 45 sec wall-clock |
| Cold model load on first call | ≤ 5 sec |
| Subsequent calls (model cached in WhisperModel singleton) | negligible load |

Actual numbers to verify during plan phase with a real fixture.

## Testing Approach

- **Unit (`scripts/lib/voice_transcriber.py`)**: transcribe a 3-second fixture
  (included WAV of known content), assert segment count > 0 and text contains
  a known word. Marked with pytest marker `voice` so it's only run when model
  is available.
- **Unit (`scripts/lib/voice_render.py`)**: given a stub `TranscriptResult`,
  assert rendered markdown matches expected template (snapshot).
- **Integration (agent-level)**: dry-run the `voice-transcriber` agent against
  a fixture vault with one audio file, assert the sibling `.md` is written
  and contains the audio embed.
- **Idempotency**: re-run `/inbox` without changes — assert zero Whisper
  invocations on the second run.

## Non-Goals / Out-of-Scope (reaffirm)

- Speaker diarization.
- Cloud transcription fallback.
- GPU/Metal acceleration (Docker Desktop constraint).
- Word-level timestamps (segment-level only for MVP).
- Automatic audio deletion.
- Inbox-note template definition (backlog F-25).

## Risks & Open Items for Plan

- **Model download reliability**: HuggingFace rate-limits; wizard should
  retry and allow manual model-dir specification as escape hatch.
- **Model file size on macOS laptops**: 1.5 GB for medium is meaningful;
  the wizard's "recommended: medium" vs "default: off" must be clear.
- **faster-whisper version pinning**: 1.x is stable; confirm compatibility
  with Python 3.11 (Debian bookworm default).
- **Container memory**: medium model needs ~2 GB RAM during inference.
  Docker Desktop default is 4 GB — tight but should work.
- **Audio format edge cases**: opus and aac may require specific ffmpeg
  codec packages. `ffmpeg` from Debian includes them by default — verify.

## Next: Plan Phase

Suggested breakdown (to be expanded in `plan/`):
1. **Phase 1** — install wizard + Dockerfile + model download (no agent integration yet)
2. **Phase 2** — Python modules + CLI script (tested standalone against fixture audio)
3. **Phase 3** — `voice-transcriber` agent (standalone, not wired into orchestrator)
4. **Phase 4** — orchestrator integration (Phase 0 in `inbox-orchestrator`)
5. **Phase 5** — end-to-end live test + docs
