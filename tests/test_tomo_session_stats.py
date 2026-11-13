# version: 0.1.0
"""Tests for scripts/tomo-session-stats.py (#262).

Claude Code writes one transcript line per content block of an API reply. Every line repeats the
reply's ``message.id`` and its ``usage``, so summing per line counted one reply's tokens once for each
of its blocks: about 2× the real cost on the spec 045 live walk (session 68459faa: $5.41 reported,
$2.66 with each id counted once). The script is run as a subprocess, the way the user runs it.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "tomo-session-stats.py"


def _reply(msg_id, block, usage, model="claude-sonnet-5-5"):
    message = {"id": msg_id, "model": model, "content": [block], "usage": usage}
    if msg_id is None:
        del message["id"]
    return {"type": "assistant", "message": message}


USAGE_A = {"input_tokens": 10, "output_tokens": 1000, "cache_creation_input_tokens": 2000,
           "cache_read_input_tokens": 100_000}
USAGE_B = {"input_tokens": 5, "output_tokens": 200, "cache_creation_input_tokens": 0,
           "cache_read_input_tokens": 50_000}


def _write(path, records):
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return path


def _run(path):
    p = subprocess.run([sys.executable, str(SCRIPT), "--session", str(path)], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout


def _field(out, label):
    match = re.search(rf"{label}:\s+\$?\s*([\d,.]+)", out)
    assert match, (label, out)
    return float(match.group(1).replace(",", ""))


def test_one_reply_written_as_three_blocks_counts_once(tmp_path):
    """Reply A has three content blocks (thinking, text, tool_use): three lines, one usage."""
    session = _write(tmp_path / "s.jsonl", [
        {"type": "user", "message": {"content": "hi"}},
        _reply("msg_A", {"type": "thinking", "thinking": "…"}, USAGE_A),
        _reply("msg_A", {"type": "text", "text": "…"}, USAGE_A),
        _reply("msg_A", {"type": "tool_use", "name": "Bash", "input": {}}, USAGE_A),
        _reply("msg_B", {"type": "text", "text": "…"}, USAGE_B),
    ])
    out = _run(session)
    assert _field(out, "Turns") == 2
    assert _field(out, "Output tokens") == 1200
    assert _field(out, "Cache read") == 150_000
    assert _field(out, "Cache create") == 2000
    expected = (15 * 3 + 1200 * 15 + 2000 * 3.75 + 150_000 * 0.30) / 1_000_000
    assert abs(_field(out, "Est. cost") - round(expected, 2)) < 0.005


def test_a_reply_without_an_id_is_counted_per_line(tmp_path):
    """Old transcripts may lack `message.id`; each such line is its own reply (nothing to dedupe on)."""
    session = _write(tmp_path / "s.jsonl", [
        _reply(None, {"type": "text", "text": "…"}, USAGE_B),
        _reply(None, {"type": "text", "text": "…"}, USAGE_B),
    ])
    out = _run(session)
    assert _field(out, "Turns") == 2
    assert _field(out, "Output tokens") == 400


def test_subagent_transcripts_are_deduplicated_too(tmp_path):
    session = _write(tmp_path / "s.jsonl", [_reply("msg_M", {"type": "text", "text": "…"}, USAGE_B)])
    sub = tmp_path / "s" / "subagents"
    sub.mkdir(parents=True)
    _write(sub / "agent-1.jsonl", [
        _reply("msg_S", {"type": "text", "text": "…"}, USAGE_A),
        _reply("msg_S", {"type": "tool_use", "name": "Read", "input": {}}, USAGE_A),
    ])
    out = _run(session)
    sub_part = out.split("=== Subagents")[1]
    assert _field(sub_part, "Turns") == 1
    assert _field(sub_part, "Output tokens") == 1000
