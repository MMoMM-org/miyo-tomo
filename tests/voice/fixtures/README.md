# Voice Test Fixtures

## `hello-world.wav`

**Format**: RIFF / WAVE, 16-bit PCM, mono, 22050 Hz (Whisper resamples
internally — 16 kHz is not required for the engine to accept it).

**Content**: "Hello, this is a longer sentence for a test fixture that
should actually have some content." (English)

**Size**: ~220 KB.

**Used by**: `tests/voice/test_transcriber.py::test_live_load_and_transcribe`
(opt-in via `@pytest.mark.voice_model` + `TOMO_TEST_MODEL_DIR`).

### Regenerating on macOS

```bash
# Any macOS system voice works — Daniel is the default English voice.
say -o /tmp/hello.aiff "Hello, this is a longer sentence for a test fixture that should actually have some content."
afconvert -f WAVE -d LEI16 -c 1 -r 16000 /tmp/hello.aiff tests/voice/fixtures/hello-world.wav
rm /tmp/hello.aiff
```

Note: `afconvert` honors the `-r` flag only when the source
sample-rate differs; AIFF-C output from `say` may already be 22 kHz,
in which case the produced WAV stays at 22 kHz. Whisper accepts
either and resamples internally, so the exact rate is not load-bearing.

### Regenerating on Linux

```bash
# espeak-ng is the most reliable cross-distro TTS.
apt install espeak-ng sox
espeak-ng -v en "Hello, this is a longer sentence for a test fixture that should actually have some content." -w /tmp/hello.wav
sox /tmp/hello.wav -c 1 -b 16 -r 16000 tests/voice/fixtures/hello-world.wav
rm /tmp/hello.wav
```

### Verification

```bash
file tests/voice/fixtures/hello-world.wav
# Expected: RIFF (little-endian) data, WAVE audio, Microsoft PCM, 16 bit, mono …
```

### Sandbox note (macOS)

When running `say` inside a sandboxed environment (Claude Code's
default sandbox, for example), audio synthesis can silently produce a
4 KB empty AIFF-C file without erroring. If the regenerated WAV is
unexpectedly small (< 100 KB), re-run the `say` command outside the
sandbox.
