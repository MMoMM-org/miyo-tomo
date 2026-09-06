#!/usr/bin/env python3
# version: 0.2.0
"""test_034_t3_3b_voice_path_recursion.py — XDD 034 T3.3b voice path sweep.

T3.2 made inbox discovery recursive; T3.3 fixed `check_audio` in
inbox-triage.py to pair by (folder, stem) instead of stem alone. The voice
path itself was never swept: `voice-precheck.py` still listed the inbox with
`depth=1` (hiding subfolder audio from the cheap pre-dispatch check
entirely), and `voice-transcriber.md` still composed both the sibling
membership check (Step 3) and the actual kado-write target (Step 5) as
`<inbox_path>/<...>` — the inbox ROOT, not the audio's own folder. A fourth
site surfaced on review: `voice-transcriber.md` Step 2 — the agent's OWN
discovery listDir — was still `depth: 1`, so even after Step 3/Step 5 compose
correctly, the agent never sees a subfolder audio file to act on in the first
place. The `depth: 1` param shape was justified in the runtime file as
"mirrors `inbox-orchestrator`'s call" — that agent was retired under spec
018 (agent-architecture-cleanup) and no longer exists anywhere in the repo;
the reference was stale and has been dropped, not redirected.

Before recursion this was harmless (all audio sat at the root, so
"root" and "own folder" were the same path). After T3.2 it is not: a
subfolder audio's transcript would be checked for and written at the wrong
path, so pairing never succeeds and the file is re-dispatched to the
transcriber on every run — the same repeated-dispatch shape as the historical
`:`-vs-`-` infinite transcribe loop, here caused by a folder mismatch instead
of a character mismatch.

`[ref: PRD/AC Feature 5]` — all sites (inbox-triage's `check_audio`,
`voice-precheck.py`, `voice-transcriber.md` Steps 2/3/5) must agree on where
a transcript lives, for any audio file at any depth.

This file covers:
  (a) `voice-precheck.py` sees subfolder audio at all — today `depth=1`
      hides it from the listing before pairing logic even runs.
  (b)/(c) cross-site agreement — `voice-precheck.precheck()` and
      `inbox-triage.check_audio()` are two independent implementations that
      must reach the same cached/uncached verdict per fixture.
  (d) root-level behaviour, including the `sanitize_stem` asymmetry, is
      unchanged by the fix.
  A static scan of `voice-transcriber.md`'s Step 2, Step 3, and Step 5
  instruction text — the only automated guard possible for LLM-loaded
  markdown (CON-5).
  A whole-chain test that walks precheck (executable) → the transcriber's own
  discovery (markdown-only, covered by static scan) → check_audio re-pairing
  after the write (executable), for one subfolder fixture.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
AGENTS_DIR = REPO_ROOT / "tomo" / "dot_claude" / "agents"

sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Module loaders
# ---------------------------------------------------------------------------

def _load_precheck():
    spec = importlib.util.spec_from_file_location(
        "voice_precheck_t33b", SCRIPTS_DIR / "voice-precheck.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["voice_precheck_t33b"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _load_triage():
    spec = importlib.util.spec_from_file_location(
        "inbox_triage_t33b", SCRIPTS_DIR / "inbox-triage.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["inbox_triage_t33b"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(path: str) -> dict:
    return {"path": path, "type": "file"}


class _DepthAwareClient:
    """Simulates real Kado listDir depth semantics (unlike a plain MagicMock
    that returns the same items regardless of `depth`). `depth=1` returns
    only direct children of `path`; `depth=None` recurses without limit —
    matching `KadoClient.list_dir`'s own docstring contract."""

    def __init__(self, items: list[dict]):
        self._items = items
        self.calls: list[tuple[str, int | None]] = []

    def list_dir(self, path: str, depth: int | None = None, limit: int = 500):
        self.calls.append((path, depth))
        base = Path(path)
        if depth is None:
            return list(self._items)
        out = []
        for item in self._items:
            rel_parts = Path(item["path"]).relative_to(base).parts
            if len(rel_parts) <= depth:
                out.append(item)
        return out


def _split(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Partition items into (audio, md) the way both check_audio's caller and
    voice-precheck expect — audio by extension, everything else with a .md
    suffix as markdown."""
    audio = [i for i in items if Path(i["path"]).suffix.lower() in {".m4a", ".mp3", ".wav"}]
    md = [i for i in items if Path(i["path"]).suffix.lower() == ".md"]
    return audio, md


# ---------------------------------------------------------------------------
# (a) voice-precheck sees subfolder audio at all — depth=1 hides it today
# ---------------------------------------------------------------------------

def test_precheck_sees_subfolder_audio_when_no_sibling_exists(monkeypatch):
    """A lone audio file two folders deep, with no sibling anywhere, must be
    counted by precheck. With today's `depth=1` listDir call, the item never
    reaches the listing at all — audio_count would read 0, not 1."""
    mod = _load_precheck()
    items = [_entry("100 Inbox/Archive/2026/memo.m4a")]
    fake_client = _DepthAwareClient(items)
    monkeypatch.setattr(mod, "KadoClient", lambda: fake_client)

    result = mod.precheck("100 Inbox")

    assert result["audio_count"] == 1
    assert result["missing"] == ["100 Inbox/Archive/2026/memo.m4a"]
    assert result["all_cached"] is False


# ---------------------------------------------------------------------------
# (b) subfolder audio + sibling beside it — cached by both sites
# ---------------------------------------------------------------------------

def test_subfolder_audio_with_own_sibling_is_cached_on_both_sites(monkeypatch):
    items = [
        _entry("100 Inbox/Voice/memo.m4a"),
        _entry("100 Inbox/Voice/memo.md"),
    ]
    precheck_mod = _load_precheck()
    triage_mod = _load_triage()
    fake_client = _DepthAwareClient(items)
    monkeypatch.setattr(precheck_mod, "KadoClient", lambda: fake_client)

    precheck_result = precheck_mod.precheck("100 Inbox")
    audio, md = _split(items)
    triage_uncached = triage_mod.check_audio(audio, md)

    assert precheck_result["all_cached"] is True
    assert triage_uncached is False


# ---------------------------------------------------------------------------
# (c) subfolder audio with no sibling — uncached by both sites
# ---------------------------------------------------------------------------

def test_subfolder_audio_without_sibling_is_uncached_on_both_sites(monkeypatch):
    items = [
        _entry("100 Inbox/Voice/memo.m4a"),
        _entry("100 Inbox/Archive/memo.md"),  # namesake elsewhere — must not pair
    ]
    precheck_mod = _load_precheck()
    triage_mod = _load_triage()
    fake_client = _DepthAwareClient(items)
    monkeypatch.setattr(precheck_mod, "KadoClient", lambda: fake_client)

    precheck_result = precheck_mod.precheck("100 Inbox")
    audio, md = _split(items)
    triage_uncached = triage_mod.check_audio(audio, md)

    assert precheck_result["all_cached"] is False
    assert precheck_result["missing"] == ["100 Inbox/Voice/memo.m4a"]
    assert triage_uncached is True


# ---------------------------------------------------------------------------
# (d) root-level audio is unchanged, including the sanitize_stem asymmetry
# ---------------------------------------------------------------------------

def test_root_level_audio_with_sibling_unchanged(monkeypatch):
    items = [_entry("100 Inbox/memo.m4a"), _entry("100 Inbox/memo.md")]
    precheck_mod = _load_precheck()
    triage_mod = _load_triage()
    fake_client = _DepthAwareClient(items)
    monkeypatch.setattr(precheck_mod, "KadoClient", lambda: fake_client)

    precheck_result = precheck_mod.precheck("100 Inbox")
    audio, md = _split(items)
    triage_uncached = triage_mod.check_audio(audio, md)

    assert precheck_result["all_cached"] is True
    assert triage_uncached is False


def test_root_level_audio_sanitize_stem_asymmetry_unchanged(monkeypatch):
    """Only the derived .md sibling is sanitised; the source audio filename
    keeps its raw colon. Preserved deliberately — see
    docs/tomo/scripts/inbox-triage.md and
    docs/tomo/dot_claude/agents/voice-transcriber.md."""
    items = [
        _entry("100 Inbox/Rec 2026-01-02 14:30.m4a"),
        _entry("100 Inbox/Rec 2026-01-02 14-30.md"),
    ]
    precheck_mod = _load_precheck()
    triage_mod = _load_triage()
    fake_client = _DepthAwareClient(items)
    monkeypatch.setattr(precheck_mod, "KadoClient", lambda: fake_client)

    precheck_result = precheck_mod.precheck("100 Inbox")
    audio, md = _split(items)
    triage_uncached = triage_mod.check_audio(audio, md)

    assert precheck_result["all_cached"] is True
    assert triage_uncached is False


def test_two_level_deep_audio_with_sibling_is_cached_on_both_sites(monkeypatch):
    """A two-levels-deep audio file (Archive/2026/memo.m4a) pairs with its
    own sibling in the same subfolder on both sites."""
    items = [
        _entry("100 Inbox/Archive/2026/memo.m4a"),
        _entry("100 Inbox/Archive/2026/memo.md"),
    ]
    precheck_mod = _load_precheck()
    triage_mod = _load_triage()
    fake_client = _DepthAwareClient(items)
    monkeypatch.setattr(precheck_mod, "KadoClient", lambda: fake_client)

    precheck_result = precheck_mod.precheck("100 Inbox")
    audio, md = _split(items)
    triage_uncached = triage_mod.check_audio(audio, md)

    assert precheck_result["all_cached"] is True
    assert triage_uncached is False


# ---------------------------------------------------------------------------
# Static scan — voice-transcriber.md is LLM-loaded markdown, never executed.
# This is the only automated guard possible (same technique used for the
# state-update.py call-site scan earlier in spec 034).
# ---------------------------------------------------------------------------

def _load_voice_transcriber_text() -> str:
    return (AGENTS_DIR / "voice-transcriber.md").read_text(encoding="utf-8")


def _extract(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _normalize(text: str) -> str:
    """Collapse markdown line-wrapping whitespace so a phrase spanning a
    line break still matches a literal substring check."""
    return " ".join(text.split())


def test_step3_composes_sibling_target_in_audios_own_folder():
    """Step 3's membership-check target must be relative to the audio file's
    own folder, never a hardcoded `<inbox_path>` — that literal composition
    is exactly the inbox-root bug this task closes."""
    step3 = _extract(_load_voice_transcriber_text(), "### Step 3", "### Step 4")

    assert "<inbox_path>/<SAFE_STEM>.md" not in _normalize(step3)
    assert "own containing folder" in _normalize(step3)


def test_step5_writes_target_beside_its_own_audio():
    """Step 5's kado-write path (both the success target and the
    transcribe-error marker) must resolve to the SAME folder Step 3 checked
    against — never `<inbox_path>` — so precheck's verdict and the write
    location can never disagree."""
    step5_raw = _extract(_load_voice_transcriber_text(), "### Step 5", "### Step 6")
    step5 = _normalize(step5_raw)

    assert "<inbox_path>/<results[i].target>" not in step5
    assert "<inbox_path>/<sanitised_stem>.transcribe-error.md" not in step5
    assert step5.count("containing folder of todo[i]") >= 2


def test_step2_discovery_listdir_has_no_depth_limit():
    """Step 2 is the transcriber's OWN discovery call — a fourth site. A
    `depth: 1` listDir here hides subfolder audio from the agent entirely,
    independent of how correctly Step 3/Step 5 compose paths afterward.
    Fixed Step 2 must drop the `depth: 1` param and must not justify itself
    by pointing at `inbox-orchestrator`, which no longer exists in this
    repo (retired under spec 018)."""
    step2 = _normalize(_extract(_load_voice_transcriber_text(), "### Step 2", "### Step 3"))

    assert "depth: 1" not in step2
    assert "inbox-orchestrator" not in step2


# ---------------------------------------------------------------------------
# Whole-chain fixture: precheck (executable) -> transcriber's own discovery
# (markdown-only, covered by the Step 2 static scan above) -> check_audio
# re-pairing after the write (executable).
# ---------------------------------------------------------------------------

def test_whole_chain_subfolder_audio_precheck_to_repair(monkeypatch):
    """A subfolder audio file with no sibling:
    1. (EXECUTED) `voice-precheck` reports it uncached — the dispatch must
       not be skipped.
    2. (STATIC SCAN — see test_step2_discovery_listdir_has_no_depth_limit)
       the transcriber's own Step 2 discovery is depth-unbounded, so it
       would see this file too; this leg lives in LLM-loaded markdown and
       cannot be executed by a unit test.
    3. (EXECUTED) once the transcriber writes the sibling beside its own
       audio (the folder Step 5 now resolves to), `check_audio` reports the
       pair as no longer uncached — the loop actually closes.
    """
    items_before = [_entry("100 Inbox/Voice/memo.m4a")]
    precheck_mod = _load_precheck()
    triage_mod = _load_triage()
    fake_client = _DepthAwareClient(items_before)
    monkeypatch.setattr(precheck_mod, "KadoClient", lambda: fake_client)

    # Leg 1 — precheck must not skip the dispatch.
    precheck_result = precheck_mod.precheck("100 Inbox")
    assert precheck_result["all_cached"] is False
    assert precheck_result["missing"] == ["100 Inbox/Voice/memo.m4a"]

    # Leg 3 — simulate the write Step 5 would perform (same folder as the
    # audio, sanitised stem) and confirm check_audio now agrees it's paired.
    items_after = items_before + [_entry("100 Inbox/Voice/memo.md")]
    audio, md = _split(items_after)
    assert triage_mod.check_audio(audio, md) is False


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
