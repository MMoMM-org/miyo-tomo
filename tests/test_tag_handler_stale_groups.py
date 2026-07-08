#!/usr/bin/env python3
# version: 0.1.0
"""test_tag_handler_stale_groups.py — stale tag-handler group leak (both fixes).

Root cause: tag-handler-groups/ is per-run staging carrying no run_id. A group whose
sources were consumed by an earlier run leaked into the next suggestions doc because
(A) reset-tomo-tmp didn't clear the dir and (B) the reducer loaded every group without
checking source existence.

Covers:
  (A) reset-tomo-tmp.sh --pass1 removes tag-handler-groups/ + tag-handler-group-stubs.json
  (B) filter_stale_tag_handler_groups drops a group whose sources are ALL missing,
      keeps a group with ≥1 present source, and fail-opens (None client / transient error).
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_reducer = _load("suggestions_reducer", "suggestions-reducer.py")
filter_stale_tag_handler_groups = _reducer.filter_stale_tag_handler_groups


class _FakeClient:
    """path_exists mirrors kado_client: False only on genuine NOT_FOUND; other
    errors raise (the filter must fail-open on the raise)."""

    def __init__(self, present: set[str], raise_on: set[str] | None = None):
        self.present = present
        self.raise_on = raise_on or set()

    def path_exists(self, path: str) -> bool:
        if path in self.raise_on:
            raise RuntimeError("transient kado error")
        return path in self.present


def _group(sources: list[str], gid: str = "g") -> dict:
    return {
        "group_id": gid,
        "handler": "tsukai",
        "target_path": "Efforts/Log.md",
        "marker": "## Captures",
        "source_paths": sources,
    }


# ── (B) reducer filter ───────────────────────────────────────────────────────


def test_drops_group_when_all_sources_missing():
    g = _group(["100 Inbox/gone.md"])
    kept, dropped = filter_stale_tag_handler_groups([g], _FakeClient(present=set()))
    assert kept == [] and dropped == 1


def test_keeps_group_with_at_least_one_present_source():
    g = _group(["100 Inbox/gone.md", "100 Inbox/live.md"])
    client = _FakeClient(present={"100 Inbox/live.md"})
    kept, dropped = filter_stale_tag_handler_groups([g], client)
    assert kept == [g] and dropped == 0


def test_none_client_keeps_everything():
    g = _group(["100 Inbox/gone.md"])
    kept, dropped = filter_stale_tag_handler_groups([g], None)
    assert kept == [g] and dropped == 0


def test_transient_error_fails_open_keeps_group():
    g = _group(["100 Inbox/maybe.md"])
    client = _FakeClient(present=set(), raise_on={"100 Inbox/maybe.md"})
    kept, dropped = filter_stale_tag_handler_groups([g], client)
    assert kept == [g] and dropped == 0


def test_group_without_sources_is_kept():
    g = _group([])
    kept, dropped = filter_stale_tag_handler_groups([g], _FakeClient(present=set()))
    assert kept == [g] and dropped == 0


# ── (A) reset-tomo-tmp clears the staging ────────────────────────────────────


def test_reset_pass1_removes_tag_handler_staging(tmp_path):
    tmp = tmp_path / "tomo-tmp"
    groups = tmp / "tag-handler-groups"
    groups.mkdir(parents=True)
    (groups / "0.json").write_text("{}", encoding="utf-8")
    (tmp / "tag-handler-group-stubs.json").write_text("[]", encoding="utf-8")

    out = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts" / "reset-tomo-tmp.sh"),
         "--pass1", "--instance", str(tmp)],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    assert not groups.exists(), "tag-handler-groups/ must be removed"
    assert not (tmp / "tag-handler-group-stubs.json").exists(), "stubs must be removed"
