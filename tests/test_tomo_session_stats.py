# version: 0.2.0
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

import pytest

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


# --- Per step: cost at per-model rates, wall time, peak context (spec 047 T7.3, F8-AC1) ---

SENTINEL = "SENTINEL-NOTE-TEXT-7f3a"
TOKEN_USAGE = ROOT / "scripts" / "tomo-token-usage.py"


def _price_table():
    import importlib.util
    spec = importlib.util.spec_from_file_location("tomo_token_usage", TOKEN_USAGE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.PRICE


def _cost(fam, u):
    p = _price_table()[fam]
    return (u["input_tokens"] * p["in"] + u["output_tokens"] * p["out"]
            + u["cache_creation_input_tokens"] * p["cache_w"]
            + u["cache_read_input_tokens"] * p["cache_r"]) / 1_000_000


def _at(record, ts):
    record["timestamp"] = ts
    return record


def _text(msg_id, model, usage, ts):
    return _at(_reply(msg_id, {"type": "text", "text": SENTINEL}, usage, model=model), ts)


USAGE_BIG = {"input_tokens": 20, "output_tokens": 4000, "cache_creation_input_tokens": 10_000,
             "cache_read_input_tokens": 300_000}

STEPS = [  # agent type, model id as transcripts write it, usage, first ts, last ts, seconds
    ("review-digester", "claude-haiku-4-5-20251001", USAGE_A, "2026-11-20T10:01:00Z", "2026-11-20T10:01:30Z", 30),
    ("review-carryover", "claude-sonnet-4-6", USAGE_B, "2026-11-20T10:02:00Z", "2026-11-20T10:02:45Z", 45),
    ("review-proposer", "claude-opus-4-1-20250805", USAGE_BIG, "2026-11-20T10:03:00Z", "2026-11-20T10:05:00Z", 120),
]


def _review_session(tmp_path, unknown_model=None):
    session = _write(tmp_path / "s.jsonl", [
        _at({"type": "user", "message": {"content": SENTINEL}}, "2026-11-20T10:00:00Z"),
        _text("msg_M1", "claude-sonnet-4-6", USAGE_B, "2026-11-20T10:00:05Z"),
        _text("msg_M2", "claude-sonnet-4-6", USAGE_A, "2026-11-20T10:06:40Z"),
    ])
    sub = tmp_path / "s" / "subagents"
    sub.mkdir(parents=True)
    for i, (agent, model, usage, t0, t1, _sec) in enumerate(STEPS):
        _write(sub / f"agent-a{i}.jsonl", [
            _at({"type": "user", "message": {"content": SENTINEL}}, t0),
            _text(f"msg_S{i}", unknown_model or model, usage, t1),
        ])
        (sub / f"agent-a{i}.meta.json").write_text(json.dumps(
            {"agentType": agent, "description": SENTINEL}), encoding="utf-8")
    return session


def _step_line(out, label):
    part = out.split("=== Per step ===")[1]
    line = next((ln for ln in part.splitlines() if ln.strip().startswith(label)), None)
    assert line, (label, part)
    return line


def _num(line, key):
    match = re.search(rf"{key}=\$?([\d,.]+)", line)
    assert match, (key, line)
    return float(match.group(1).replace(",", ""))


def test_each_step_lists_cost_at_its_model_rate_time_and_peak(tmp_path):
    out = _run(_review_session(tmp_path))
    main = _step_line(out, "main")
    assert abs(_num(main, "cost") - round(_cost("sonnet", USAGE_A) + _cost("sonnet", USAGE_B), 4)) < 0.00005
    assert _num(main, "time") == 400  # 10:00:00 → 10:06:40, first to last timestamp
    assert _num(main, "peak") == 100_010
    for (agent, _model, usage, _t0, _t1, seconds), fam in zip(STEPS, ("haiku", "sonnet", "opus")):
        line = _step_line(out, agent)
        assert abs(_num(line, "cost") - round(_cost(fam, usage), 4)) < 0.00005, line
        assert _num(line, "time") == seconds, line
        assert _num(line, "peak") == usage["input_tokens"] + usage["cache_read_input_tokens"], line
        assert fam in line, line
    assert "default price" not in out


def test_the_total_sums_the_per_model_costs(tmp_path):
    out = _run(_review_session(tmp_path))
    expected = (_cost("sonnet", USAGE_A) + _cost("sonnet", USAGE_B) + _cost("haiku", USAGE_A)
                + _cost("sonnet", USAGE_B) + _cost("opus", USAGE_BIG))
    assert abs(_field(out.split("=== Total ===")[1], "Grand total cost") - round(expected, 2)) < 0.005


def test_unknown_model_falls_back_to_the_default_price_and_says_so(tmp_path):
    out = _run(_review_session(tmp_path, unknown_model="mystery-model-9"))
    line = _step_line(out, "review-proposer")
    sonnet = _price_table()["sonnet"]
    expected = (USAGE_BIG["input_tokens"] * sonnet["in"] + USAGE_BIG["output_tokens"] * sonnet["out"]
                + USAGE_BIG["cache_creation_input_tokens"] * sonnet["cache_w"]
                + USAGE_BIG["cache_read_input_tokens"] * sonnet["cache_r"]) / 1_000_000
    assert abs(_num(line, "cost") - round(expected, 4)) < 0.00005, line
    assert "default price" in line
    assert "mystery-model-9" in out


def test_the_report_carries_counts_only_never_message_text(tmp_path):
    p = subprocess.run([sys.executable, str(SCRIPT), "--session", str(_review_session(tmp_path))],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert SENTINEL not in p.stdout + p.stderr


def test_a_zero_usage_synthetic_reply_is_not_flagged_as_default_price(tmp_path):
    """Claude Code writes `<synthetic>` replies with zero usage; nothing is priced, so nothing is defaulted."""
    zero = {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    session = _write(tmp_path / "s.jsonl", [
        _text("msg_M1", "claude-sonnet-4-6", USAGE_B, "2026-11-20T10:00:05Z"),
        _text("msg_M2", "<synthetic>", zero, "2026-11-20T10:00:09Z"),
    ])
    assert "default price" not in _run(session)


def _session_with_meta(tmp_path, meta_text):
    session = _write(tmp_path / "s.jsonl", [_text("msg_M1", "claude-sonnet-4-6", USAGE_B, "2026-11-20T10:00:05Z")])
    sub = tmp_path / "s" / "subagents"
    sub.mkdir(parents=True)
    _write(sub / "agent-a0.jsonl", [_text("msg_S0", "claude-haiku-4-5", USAGE_A, "2026-11-20T10:01:00Z")])
    if meta_text is not None:
        (sub / "agent-a0.meta.json").write_text(meta_text, encoding="utf-8")
    return session



@pytest.mark.parametrize("meta_text", [None, "{not json", '["agentType"]', '{"description": "x"}', '{"agentType": ""}'],
                         ids=["missing", "corrupt", "not-an-object", "no-agentType", "empty-agentType"])
def test_subagent_label_falls_back_to_the_transcript_stem(tmp_path, meta_text):
    out = _run(_session_with_meta(tmp_path, meta_text))
    assert _step_line(out, "agent-a0")
