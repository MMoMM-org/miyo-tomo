"""shared-ctx-builder.py --warnings-out (spec 043 findings F4, Plan B).

suggest-handling step 3 relays the builder's `WARN:` lines by running
`cat tomo-tmp/setup-warnings.txt` and copying its stdout. These tests prove the
file holds exactly the `WARN:` lines the builder printed on stderr, is empty
when there were none, is rewritten (never appended) on every run — also on an
error exit — and that omitting the flag writes nothing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILDER = REPO_ROOT / "tomo" / "scripts" / "shared-ctx-builder.py"
PROFILES = REPO_ROOT / "tomo" / "profiles"


def _write_inputs(tmp_path: Path, keywords: bool) -> None:
    field = {"name": "Mood", "type": "text", "syntax": "inline_field", "description": "Mood."}
    if keywords:
        field["positive_keywords"] = ["froh"]
    cfg = {
        "profile": "miyo",
        "tags": {"prefixes": {}},
        "concepts": {
            "map_note": {"paths": ["Atlas/200 Maps/"]},
            "calendar": {"granularities": {"daily": {"enabled": True, "path": "Calendar/301 Daily/"}}},
        },
        "trackers": {
            "enabled": True,
            "daily_note_trackers": {"section": "Habit", "today_fields": [field]},
        },
    }
    (tmp_path / "vault-config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    (tmp_path / "cache.yaml").write_text(yaml.safe_dump({"map_notes": []}), encoding="utf-8")


def _build(tmp_path: Path, *extra: str, cache: str = "cache.yaml") -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable, str(BUILDER),
            "--cache", str(tmp_path / cache),
            "--vault-config", str(tmp_path / "vault-config.yaml"),
            "--profiles-dir", str(PROFILES),
            "--run-id", "r043",
            "--output", str(tmp_path / "ctx.json"),
            "--skip-reconcile",
            *extra,
        ],
        capture_output=True,
        text=True,
    )


def _warn_lines(stderr: str) -> list[str]:
    return [line for line in stderr.splitlines() if line.startswith("WARN:")]


def test_the_file_holds_exactly_the_warn_lines_printed(tmp_path):
    _write_inputs(tmp_path, keywords=False)
    out = tmp_path / "tmp" / "setup-warnings.txt"
    r = _build(tmp_path, "--warnings-out", str(out))
    assert r.returncode == 0, r.stderr
    printed = _warn_lines(r.stderr)
    assert any("active tracker field(s) have no keywords" in line for line in printed)
    assert out.read_text(encoding="utf-8") == "".join(line + "\n" for line in printed)


def test_no_warnings_leaves_an_empty_file(tmp_path):
    _write_inputs(tmp_path, keywords=True)
    out = tmp_path / "setup-warnings.txt"
    r = _build(tmp_path, "--warnings-out", str(out))
    assert r.returncode == 0, r.stderr
    assert _warn_lines(r.stderr) == []
    assert out.exists() and out.read_text(encoding="utf-8") == ""


def test_a_clean_run_truncates_an_earlier_warning(tmp_path):
    out = tmp_path / "setup-warnings.txt"
    out.write_text("WARN: stale line from an earlier run\n", encoding="utf-8")
    _write_inputs(tmp_path, keywords=True)
    assert _build(tmp_path, "--warnings-out", str(out)).returncode == 0
    assert out.read_text(encoding="utf-8") == ""


def test_an_error_exit_still_rewrites_the_file(tmp_path):
    out = tmp_path / "setup-warnings.txt"
    out.write_text("WARN: stale line from an earlier run\n", encoding="utf-8")
    _write_inputs(tmp_path, keywords=False)
    r = _build(tmp_path, "--warnings-out", str(out), cache="missing.yaml")
    assert r.returncode == 1
    assert "ERROR: cache not found" in r.stderr
    assert out.read_text(encoding="utf-8") == ""


def test_without_the_flag_no_file_is_written_and_stderr_is_unchanged(tmp_path):
    _write_inputs(tmp_path, keywords=False)
    r = _build(tmp_path)
    assert r.returncode == 0, r.stderr
    assert len(_warn_lines(r.stderr)) == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["cache.yaml", "ctx.json", "vault-config.yaml"]


def test_stderr_is_passed_through_with_the_flag(tmp_path):
    _write_inputs(tmp_path, keywords=False)
    plain = _build(tmp_path).stderr
    flagged = _build(tmp_path, "--warnings-out", str(tmp_path / "w.txt")).stderr
    assert flagged == plain
