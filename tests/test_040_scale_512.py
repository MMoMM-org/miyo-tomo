#!/usr/bin/env python3
# version: 0.1.0
"""test_040_scale_512.py — spec 040 T6.2: the reads at 512 eligible MOCs.

PRD F1-AC6: at 512 MOCs with typical titles the name read is delivered whole,
not as a preview, and longer titles raise a size warning at build. PRD F2-AC2:
nothing is shed. The fixtures are synthetic so the test is deterministic and
no vault titles enter the repo; their sizes follow the test instance (titles
~15.5 characters, the largest full entry ~1.46 KB).

Two shapes, because they produce different names:
  - distinct titles   → every name is its title (SDD bar: names ≤ 12 KB);
  - #173's duplication (every title held by several paths) → names collide and
    become paths, so the list is larger; it must still arrive whole.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "tomo" / "scripts"
SPILL_FLOOR_BYTES = 37_700  # tests/test_read_shared_ctx.py::TestOutputSize
STEP1 = "daily_notes,classification_keywords,tag_prefixes,asset_folder"


def _entry(path: str, title: str) -> dict:
    return {
        "path": path, "title": title, "tags": ["type/others/moc"],
        "topics": [f"{title.lower()} topic {j}" for j in range(6)],
        "headings": [{"text": f"{title} — section heading {j:02d}", "level": 2} for j in range(10)],
        "editable_callouts": [f"> [!blocks]- {title} editable callout {j}" for j in range(4)],
        "has_footer": True,
    }


def _distinct(n: int, title_len: int = 15) -> list[dict]:
    return [_entry(f"Atlas/200 Maps/T{i:03d}.md", f"T{i:03d} " + "x" * (title_len - 5)) for i in range(n)]


def _duplicated(n_titles: int, copies: int) -> list[dict]:
    return [_entry(("Atlas/200 Maps/" if c == 0 else f"Copy{c}/") + f"T{i:03d}.md", f"Topic {i:03d} (MOC)")
            for c in range(copies) for i in range(n_titles)]


def _build(tmp: Path, notes: list[dict]) -> tuple[Path, str]:
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "cache.yaml").write_text(yaml.safe_dump({"map_notes": notes}), encoding="utf-8")
    (tmp / "vault-config.yaml").write_text(yaml.safe_dump({
        "profile": "miyo", "tags": {"prefixes": {}},
        "concepts": {"map_note": {"paths": ["Atlas/200 Maps/"]},
                     "calendar": {"granularities": {"daily": {"enabled": True, "path": "Calendar/301 Daily/"}}}},
    }), encoding="utf-8")
    out = subprocess.run([
        sys.executable, str(SCRIPTS / "shared-ctx-builder.py"), "--cache", str(tmp / "cache.yaml"),
        "--vault-config", str(tmp / "vault-config.yaml"), "--profiles-dir", str(REPO_ROOT / "tomo" / "profiles"),
        "--run-id", "s512", "--output", str(tmp / "ctx.json"), "--skip-reconcile",
    ], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return tmp / "ctx.json", out.stderr


def _read(ctx: Path, *args: str) -> str:
    out = subprocess.run([sys.executable, str(SCRIPTS / "read-shared-ctx.py"), "--ctx", str(ctx),
                          "--run-id", "s512", *args], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout


def _warns(stderr: str) -> list[str]:
    return [ln for ln in stderr.splitlines() if ln.startswith("WARN:")]


def test_512_distinct_typical_titles(tmp_path):
    notes = _distinct(512)
    ctx, stderr = _build(tmp_path, notes)
    names = _read(ctx, "--moc-names")
    assert len(json.loads(names)) == 512
    assert len(names.encode("utf-8")) <= 12 * 1024
    assert _warns(stderr) == []

    names_file = tmp_path / "n.txt"
    names_file.write_text("\n".join(json.loads(names)[:20]) + "\n", encoding="utf-8")
    detail = _read(ctx, "--mocs-from", str(names_file))
    assert len(json.loads(detail)["mocs"]) == 20
    assert len(detail.encode("utf-8")) <= 30 * 1024

    by_path = {e["path"]: e for e in notes}
    for moc in json.loads(ctx.read_text())["mocs"]:  # nothing is shed (F2-AC2)
        assert moc["headings"] == by_path[moc["path"]]["headings"][:8]
        assert moc["editable_callouts"] == by_path[moc["path"]]["editable_callouts"][:4]


def test_512_duplicated_as_in_173_still_arrive_whole(tmp_path):
    ctx, stderr = _build(tmp_path, _duplicated(64, 8))
    names = _read(ctx, "--moc-names")
    assert len(json.loads(names)) == 512
    assert len(names.encode("utf-8")) < SPILL_FLOOR_BYTES
    assert _warns(stderr) == []


def test_the_step_1_batch_does_not_grow_with_the_vault(tmp_path):
    small, _ = _build(tmp_path / "small", _distinct(64))
    large, _ = _build(tmp_path / "large", _distinct(512))
    assert _read(small, "--fields", STEP1) == _read(large, "--fields", STEP1)


def test_long_titles_raise_the_names_warning(tmp_path):
    _ctx, stderr = _build(tmp_path, _distinct(512, title_len=64))
    # The fixture repeats the title inside every heading, so 'detail' may warn too.
    assert [w for w in _warns(stderr) if "'names'" in w], stderr
