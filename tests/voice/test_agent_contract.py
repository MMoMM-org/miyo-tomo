#!/usr/bin/env python3
# version: 0.1.0
"""test_agent_contract.py — Static contract checks between the
voice-transcriber agent spec, the CLI, and the install wizard.

These aren't behavior tests — they assert that the string constants
these three components agree on (paths, model-size list) stay in sync.
Review finding M14.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AGENT_MD = REPO_ROOT / "tomo/dot_claude/agents/voice-transcriber.md"
# Runtime Python moved from scripts/ to tomo/scripts/ on 2026-04-22 so
# that scripts/ holds only the user-invoked install/update helpers.
CLI_PY = REPO_ROOT / "tomo/scripts/voice-transcribe.py"
CONFIGURE_SH = REPO_ROOT / "scripts/lib/configure-voice.sh"


def test_agent_model_dir_template_matches_runtime_mount():
    """The agent tells the CLI to look under `/tomo/voice/models/...`.
    This matches the container-side bind-mount target in
    begin-tomo.sh.template (`-v $INSTANCE_PATH/voice:/tomo/voice:ro`).
    A change on either side without the other = silent exit-3 failure."""
    agent = AGENT_MD.read_text()
    assert "/tomo/voice/models/faster-whisper-<model>" in agent, (
        "Agent spec must document the `/tomo/voice/models/faster-whisper-<model>` "
        "template — this is the path the container sees. Update both the agent "
        "and begin-tomo.sh.template's bind-mount together."
    )


def test_configure_voice_model_list_matches_sdd_decision():
    """The wizard allowlist (tiny|base|small|medium|large-v3) is the
    authoritative set of supported sizes. If this list changes, the
    download manifest URL contract (Systran/faster-whisper-<size>)
    and the README recommendations must be updated together."""
    configure = CONFIGURE_SH.read_text()
    match = re.search(r'^_voice_size_list="([^"]+)"', configure, re.MULTILINE)
    assert match is not None, "could not locate _voice_size_list in configure-voice.sh"
    sizes = set(match.group(1).split())
    assert sizes == {"tiny", "base", "small", "medium", "large-v3"}, (
        f"Model-size list changed: {sizes}. If this is intentional, "
        "update the HF repo naming expectation and README."
    )


def test_cli_requires_model_dir_flag():
    """The CLI must require --model-dir — no hidden default that
    silently targets faster-whisper-medium (review finding H3).
    A grep check is cheaper than a subprocess assertion and catches the
    regression faster."""
    cli = CLI_PY.read_text()
    assert 'MODEL_DIR_DEFAULT' not in cli, (
        "voice-transcribe.py reintroduced MODEL_DIR_DEFAULT — this was "
        "removed because a hardcoded default silently mismatched wizard "
        "model choices (small, large-v3)."
    )
    assert 'required=True' in cli, (
        "voice-transcribe.py --model-dir must be required=True; a hidden "
        "default breaks non-medium wizard configurations."
    )
