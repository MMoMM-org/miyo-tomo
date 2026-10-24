#!/usr/bin/env python3
# version: 0.1.0
"""test_040_reader_modes.py — spec 040 T2.1: `--moc-names`, `--mocs-from`, `--run-id`.

Each analyst reads the names of all eligible MOCs and the detail of the few it
nominates (SDD ADR-2), and refuses a context written by another run (ADR-8).
Exit codes are asserted as `== 1` with the SDD's stderr text: an unknown flag
already exits 2 on `main` (argparse), so "non-zero" would prove nothing.

Contexts are built with the builder's own `build_mocs`, so `name` follows the
real collision rule rather than a hand-written copy of it.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
READER = SCRIPTS_DIR / "read-shared-ctx.py"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location("shared_ctx_builder_040r", SCRIPTS_DIR / "shared-ctx-builder.py")
scb = importlib.util.module_from_spec(_spec)
sys.modules["shared_ctx_builder_040r"] = scb
_spec.loader.exec_module(scb)

FOLDERS = ("Atlas/200 Maps/",)
RUN = "2026-10-24T12-00-00Z-abc123"


def _moc(path, title):
    return {"path": path, "title": title, "topics": [title.lower()], "tags": ["type/others/moc"],
            "headings": [{"text": f"{title} intro", "level": 2}],
            "editable_callouts": [f"> [!blocks]- {title}"]}


def _cache():
    return {"map_notes": [
        _moc("Atlas/200 Maps/Projects.md", "Projects"),
        _moc("Efforts/Work/Projects.md", "Projects"),
        _moc("Atlas/200 Maps/Movies and Series (MOC).md", "Movies and Series (MOC)"),
        _moc("Atlas/200 Maps/Café (MOC).md", "Café (MOC)"),
        _moc("Atlas/200 Maps/Wine (MOC).md", "Wine (MOC)"),
        _moc("Atlas/200 Maps/wine  (MOC).md", "wine  (MOC)"),
    ]}


def _write_ctx(tmp_path: Path, mocs=None, **overrides) -> Path:
    ctx = {
        "schema_version": "1",
        "run_id": RUN,
        "mocs": scb.build_mocs(_cache(), FOLDERS) if mocs is None else mocs,
        "tag_prefixes": [],
        "classification_keywords": {},
        "asset_folder": "Atlas/290 Assets/295 Attachments/",
        "placeholder_targets": ["Weinbau (MOC)"],
    }
    ctx.update(overrides)
    p = tmp_path / "shared-ctx.json"
    p.write_text(json.dumps(ctx, ensure_ascii=False), encoding="utf-8")
    return p


def _run(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(READER), *argv], capture_output=True, text=True)


def _names_file(tmp_path: Path, *lines: str) -> Path:
    p = tmp_path / "item.moc-names.txt"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def _select(tmp_path: Path, *lines: str) -> dict:
    ctx = _write_ctx(tmp_path)
    out = _run("--ctx", str(ctx), "--mocs-from", str(_names_file(tmp_path, *lines)))
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


# ── --moc-names ──────────────────────────────────────────────────────────────

def test_moc_names_prints_every_name_in_mocs_order_compact(tmp_path):
    ctx = _write_ctx(tmp_path)
    out = _run("--ctx", str(ctx), "--moc-names")
    assert out.returncode == 0, out.stderr
    expected = [m["name"] for m in json.loads(ctx.read_text())["mocs"]]
    assert json.loads(out.stdout) == expected
    assert out.stdout.strip() == json.dumps(expected, ensure_ascii=False, separators=(",", ":"))
    assert "Efforts/Work/Projects.md" in expected  # the path-form name is delivered


def test_moc_names_on_a_context_without_name_fails(tmp_path):
    old = [{"path": "Atlas/x.md", "title": "X (MOC)", "topics": ["x"]}]
    out = _run("--ctx", str(_write_ctx(tmp_path, mocs=old)), "--moc-names")
    assert out.returncode == 1
    assert out.stdout == ""
    assert "context predates spec 040" in out.stderr
    assert len(out.stderr.strip().splitlines()) == 1


def test_512_moc_names_stay_under_12_kb(tmp_path):
    cache = {"map_notes": [_moc(f"Atlas/200 Maps/Topic {i:03d} (MOC).md", f"Topic {i:03d} (MOC)")
                           for i in range(512)]}
    ctx = _write_ctx(tmp_path, mocs=scb.build_mocs(cache, FOLDERS))
    out = _run("--ctx", str(ctx), "--moc-names")
    assert out.returncode == 0, out.stderr
    assert len(json.loads(out.stdout)) == 512
    assert len(out.stdout.encode("utf-8")) <= 12 * 1024


# ── --mocs-from ──────────────────────────────────────────────────────────────

def test_each_delivered_name_returns_exactly_its_entry(tmp_path):
    got = _select(tmp_path, "Projects", "Efforts/Work/Projects.md", "Café (MOC)")
    assert [m["path"] for m in got["mocs"]] == [
        "Atlas/200 Maps/Projects.md", "Efforts/Work/Projects.md", "Atlas/200 Maps/Café (MOC).md",
    ]
    assert got["mocs"][0]["headings"] == [{"text": "Projects intro", "level": 2}]  # full entry
    assert got["unresolved"] == [] and got["omitted"] == []


def test_a_case_whitespace_nfc_variant_resolves_when_unique(tmp_path):
    decomposed = "Café (MOC)"  # NFD form of "Café (MOC)"
    got = _select(tmp_path, "movies  AND series (moc)", decomposed)
    assert [m["path"] for m in got["mocs"]] == [
        "Atlas/200 Maps/Movies and Series (MOC).md", "Atlas/200 Maps/Café (MOC).md",
    ]
    assert got["unresolved"] == []


def test_a_variant_matching_two_names_is_unresolved(tmp_path):
    """`Wine (MOC)` and `wine  (MOC)` are both delivered names; `WINE (MOC)` matches both."""
    got = _select(tmp_path, "WINE (MOC)")
    assert got["mocs"] == []
    assert got["unresolved"] == ["WINE (MOC)"]


def test_an_exact_name_wins_over_its_ambiguous_variants(tmp_path):
    got = _select(tmp_path, "Wine (MOC)")
    assert [m["path"] for m in got["mocs"]] == ["Atlas/200 Maps/Wine (MOC).md"]


def test_unknown_names_are_unresolved_with_exit_zero(tmp_path):
    got = _select(tmp_path, "Gardening (MOC)", "Projects")
    assert [m["path"] for m in got["mocs"]] == ["Atlas/200 Maps/Projects.md"]
    assert got["unresolved"] == ["Gardening (MOC)"]


def test_blank_lines_and_duplicates_are_ignored(tmp_path):
    got = _select(tmp_path, "", "Projects", "   ", "Projects", "projects")
    assert [m["path"] for m in got["mocs"]] == ["Atlas/200 Maps/Projects.md"]
    assert got["unresolved"] == [] and got["omitted"] == []


def test_the_21st_distinct_name_is_omitted(tmp_path):
    cache = {"map_notes": [_moc(f"Atlas/200 Maps/T{i:02d}.md", f"T{i:02d}") for i in range(25)]}
    ctx = _write_ctx(tmp_path, mocs=scb.build_mocs(cache, FOLDERS))
    names = _names_file(tmp_path, *[f"T{i:02d}" for i in range(22)])
    out = _run("--ctx", str(ctx), "--mocs-from", str(names))
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    assert [m["name"] for m in got["mocs"]] == [f"T{i:02d}" for i in range(20)]
    assert got["omitted"] == ["T20", "T21"]


def test_a_missing_names_file_fails(tmp_path):
    missing = tmp_path / "nope.moc-names.txt"
    out = _run("--ctx", str(_write_ctx(tmp_path)), "--mocs-from", str(missing))
    assert out.returncode == 1
    assert out.stdout == ""
    assert str(missing) in out.stderr
    assert len(out.stderr.strip().splitlines()) == 1


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root reads any file")
def test_an_unreadable_names_file_fails(tmp_path):
    names = _names_file(tmp_path, "Projects")
    names.chmod(0)
    try:
        out = _run("--ctx", str(_write_ctx(tmp_path)), "--mocs-from", str(names))
    finally:
        names.chmod(0o600)
    assert out.returncode == 1
    assert out.stdout == ""
    assert str(names) in out.stderr


# ── --run-id ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mode", [
    ["--moc-names"], ["--mocs-from", "NAMES"], ["--field", "asset_folder"],
    ["--fields", "asset_folder,placeholder_targets"], ["--keys"],
])
def test_run_id_mismatch_fails_in_every_mode(tmp_path, mode):
    ctx = _write_ctx(tmp_path)
    argv = [str(_names_file(tmp_path, "Projects")) if a == "NAMES" else a for a in mode]
    out = _run("--ctx", str(ctx), "--run-id", "other-run", *argv)
    assert out.returncode == 1
    assert out.stdout == ""
    assert out.stderr.strip() == f"read-shared-ctx: shared-ctx belongs to run {RUN}, expected other-run"


def test_a_matching_run_id_changes_nothing(tmp_path):
    ctx = str(_write_ctx(tmp_path))
    plain = _run("--ctx", ctx, "--fields", "asset_folder,placeholder_targets")
    checked = _run("--ctx", ctx, "--run-id", RUN, "--fields", "asset_folder,placeholder_targets")
    assert checked.returncode == 0 and checked.stdout == plain.stdout


# ── one mode at a time ───────────────────────────────────────────────────────

@pytest.mark.parametrize("modes", [
    [], ["--moc-names", "--keys"], ["--mocs-from", "x.txt", "--moc-names"],
    ["--mocs-from", "x.txt", "--field", "run_id"], ["--moc-names", "--fields", "run_id"],
])
def test_exactly_one_of_five_modes(tmp_path, modes):
    out = _run("--ctx", str(_write_ctx(tmp_path)), *modes)
    assert out.returncode == 2
    # Not just argparse's "unrecognized arguments", which names both flags too.
    assert "choose exactly one of" in out.stderr
    assert "--moc-names" in out.stderr and "--mocs-from" in out.stderr
