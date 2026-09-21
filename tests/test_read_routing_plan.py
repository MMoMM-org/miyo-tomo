"""read-routing-plan.py — the sanctioned replacement for inline Python.

The suggestion conductor forbids `python3 -c` in a STRICT block, and Claude
Code's Bash validator flags such calls on their `#` characters. In the
2026-09-14 12:34 run the model ran one anyway, to turn routing-plan.json into
a numbered list of source paths, and filed a bug against itself for doing so.
Its own stated cause was expediency — there was no sanctioned way to get the
list, and `cat` hands back a document to re-derive it from.

These tests cover the three jobs that replaces: reading a field, listing the
sources, and slicing them into dispatch batches.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "tomo" / "scripts" / "read-routing-plan.py"

_spec = importlib.util.spec_from_file_location("read_routing_plan", SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def _plan(tmp_path: Path, **overrides) -> Path:
    data = {
        "action": "suggest",
        "inbox_path": "100 Inbox/",
        "fresh_sources": [
            {"path": f"100 Inbox/note{i}.md", "modified": str(i)} for i in range(12)
        ],
        "handled": [],
        "metrics": {"item_count": 13},
    }
    data.update(overrides)
    p = tmp_path / "routing-plan.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _run(capsys, *argv) -> list[str]:
    assert _mod.main(list(argv)) == 0
    return capsys.readouterr().out.splitlines()


class TestFieldReads:
    def test_scalar_field(self, tmp_path, capsys):
        assert _run(capsys, "--plan", str(_plan(tmp_path)), "--field", "action") == ["suggest"]

    def test_dotted_field(self, tmp_path, capsys):
        out = _run(capsys, "--plan", str(_plan(tmp_path)), "--field", "metrics.item_count")
        assert out == ["13"]

    def test_inbox_path_loses_its_trailing_slash(self, tmp_path, capsys):
        """The plan stores "100 Inbox/"; a template joining with "/" made
        "100 Inbox//<stem>". Kado normalises that, which is the kind of
        dependency that holds until the day it does not."""
        out = _run(capsys, "--plan", str(_plan(tmp_path)), "--field", "inbox_path")
        assert out == ["100 Inbox"]

    def test_inbox_path_without_a_slash_is_unchanged(self, tmp_path, capsys):
        p = _plan(tmp_path, inbox_path="Inbox")
        assert _run(capsys, "--plan", str(p), "--field", "inbox_path") == ["Inbox"]

    def test_a_missing_field_is_an_error_not_an_empty_string(self, tmp_path):
        """The conductor branches on these values. An empty string would route
        the run down a wrong path instead of stopping it."""
        with pytest.raises(SystemExit) as exc:
            _mod.main(["--plan", str(_plan(tmp_path)), "--field", "nope"])
        assert "no such field" in str(exc.value)

    def test_a_list_field_comes_back_as_json(self, tmp_path, capsys):
        p = _plan(tmp_path, handled=[{"handler": "tsukai"}])
        out = _run(capsys, "--plan", str(p), "--field", "handled")
        assert json.loads(out[0]) == [{"handler": "tsukai"}]


class TestSourceListing:
    def test_sources_one_path_per_line(self, tmp_path, capsys):
        out = _run(capsys, "--plan", str(_plan(tmp_path)), "--sources")
        assert len(out) == 12
        assert out[0] == "100 Inbox/note0.md"

    def test_count(self, tmp_path, capsys):
        assert _run(capsys, "--plan", str(_plan(tmp_path)), "--count") == ["12"]

    def test_absent_fresh_sources_is_empty_not_an_error(self, tmp_path, capsys):
        """A fan-resolve or idle plan carries no fresh_sources."""
        p = tmp_path / "routing-plan.json"
        p.write_text(json.dumps({"action": "idle"}), encoding="utf-8")
        assert _run(capsys, "--plan", str(p), "--count") == ["0"]

    def test_a_source_without_a_path_is_an_error(self, tmp_path):
        p = _plan(tmp_path, fresh_sources=[{"modified": "1"}])
        with pytest.raises(SystemExit) as exc:
            _mod.main(["--plan", str(p), "--sources"])
        assert "needs a 'path'" in str(exc.value)


class TestBatching:
    def test_batch_count_rounds_up(self, tmp_path, capsys):
        p = str(_plan(tmp_path))
        assert _run(capsys, "--plan", p, "--batch-count", "--size", "5") == ["3"]

    def test_first_batch(self, tmp_path, capsys):
        out = _run(capsys, "--plan", str(_plan(tmp_path)), "--sources", "--batch", "1", "--size", "5")
        assert out == [f"100 Inbox/note{i}.md" for i in range(5)]

    def test_last_batch_is_the_remainder(self, tmp_path, capsys):
        """12 items at 5 leaves 2 — the case where an LLM doing the arithmetic
        either drops the tail or dispatches a phantom sixth item."""
        out = _run(capsys, "--plan", str(_plan(tmp_path)), "--sources", "--batch", "3", "--size", "5")
        assert out == ["100 Inbox/note10.md", "100 Inbox/note11.md"]

    def test_every_source_appears_exactly_once_across_batches(self, tmp_path, capsys):
        p = str(_plan(tmp_path))
        seen: list[str] = []
        for batch in (1, 2, 3):
            seen += _run(capsys, "--plan", p, "--sources", "--batch", str(batch), "--size", "5")
        assert seen == [f"100 Inbox/note{i}.md" for i in range(12)]

    def test_batch_past_the_end_is_an_error(self, tmp_path):
        with pytest.raises(SystemExit) as exc:
            _mod.main(["--plan", str(_plan(tmp_path)), "--sources", "--batch", "4", "--size", "5"])
        assert "out of range (1..3)" in str(exc.value)

    def test_batch_zero_is_rejected(self, tmp_path):
        """1-based on purpose — "batch 1 of 3" is what the skill tells the model
        to report, and a 0-based flag invites an off-by-one at the call site."""
        with pytest.raises(SystemExit):
            _mod.main(["--plan", str(_plan(tmp_path)), "--sources", "--batch", "0", "--size", "5"])


class TestFailureModes:
    def test_missing_file(self, tmp_path):
        with pytest.raises(SystemExit) as exc:
            _mod.main(["--plan", str(tmp_path / "gone.json"), "--count"])
        assert "no such file" in str(exc.value)

    def test_malformed_json(self, tmp_path):
        p = tmp_path / "routing-plan.json"
        p.write_text("{not json", encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            _mod.main(["--plan", str(p), "--count"])
        assert "not valid JSON" in str(exc.value)

    def test_exactly_one_mode_required(self, tmp_path):
        with pytest.raises(SystemExit):
            _mod.main(["--plan", str(_plan(tmp_path))])
        with pytest.raises(SystemExit):
            _mod.main(["--plan", str(_plan(tmp_path)), "--count", "--sources"])
