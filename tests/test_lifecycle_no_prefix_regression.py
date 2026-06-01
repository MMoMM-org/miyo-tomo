#!/usr/bin/env python3
# version: 0.1.1
"""test_lifecycle_no_prefix_regression.py — F6-AC4 regression guard (T4.4).

Asserts that the /inbox lifecycle (capture → active → cleanup) is entirely
driven by `tomo.state` frontmatter with NO tag prefix involvement:

  Primary (behavioural):
    B1 — mark-captured writes tomo.state=captured via write_frontmatter (no tag)
    B2 — inbox-triage discovers items via search_by_frontmatter("tomo.state=...")
          not via byTag; captured items are excluded from new_sources
    B3 — state-promoter advances pending-approval → approved via write_frontmatter
          (the "active → cleanup" transition)
    B4 — end-to-end: a note progresses capture→active→cleanup through frontmatter
          calls only (no tag field at any stage)

  Secondary (source-invariant):
    S1 — mark-captured.py source has no tag_prefix / byTag references in the
          lifecycle path (belt-and-suspenders; primary B-tests are the real guard)

Spec: docs/XDD/specs/020-multi-instance-install/ — Phase 4 T4.4, F6-AC4
"""
from __future__ import annotations

import contextlib
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
LIB_DIR = SCRIPTS_DIR / "lib"

sys.path.insert(0, str(SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# Shared fake infrastructure (matches mark-captured test pattern)
# ---------------------------------------------------------------------------


def _inject_doc_frontmatter_fake() -> types.ModuleType:
    """Inject a lightweight fake lib.doc_frontmatter to avoid the jsonschema dep."""
    import datetime

    fake_mod = types.ModuleType("lib.doc_frontmatter")

    def _build_tomo_block(doc_type: str, state: str, run_id: str, **extra: str) -> dict:
        return {
            "doc_type": doc_type,
            "state": state,
            "run_id": run_id,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            **extra,
        }

    class _FakeSchemaValidationError(Exception):
        pass

    fake_mod.build_tomo_block = _build_tomo_block  # type: ignore[attr-defined]
    fake_mod.SchemaValidationError = _FakeSchemaValidationError  # type: ignore[attr-defined]

    return fake_mod


_FAKE_DOC_FM = _inject_doc_frontmatter_fake()


@contextlib.contextmanager
def _forced_fake_doc_fm():
    """Force the fake doc_frontmatter into sys.modules for the duration of an
    exec_module(), then restore the prior entries.

    setdefault is order-dependent: if test_doc_frontmatter.py registered the
    real (jsonschema-dependent) module first, a setdefault-based inject is a
    no-op and the loaded script picks up the broken real module. Forcing +
    restoring makes the harness hermetic regardless of import order — the
    loaded module captures fake.build_tomo_block by reference at import time,
    so restoring afterward is safe.
    """
    keys = ("lib.doc_frontmatter", "doc_frontmatter")
    saved = {k: sys.modules.get(k) for k in keys}
    for k in keys:
        sys.modules[k] = _FAKE_DOC_FM
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def _load_mark_captured():
    spec = importlib.util.spec_from_file_location("mark_captured", SCRIPTS_DIR / "mark-captured.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    with _forced_fake_doc_fm():
        spec.loader.exec_module(mod)
    return mod


def _load_inbox_triage():
    spec = importlib.util.spec_from_file_location("inbox_triage", SCRIPTS_DIR / "inbox-triage.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["inbox_triage"] = mod
    with _forced_fake_doc_fm():
        spec.loader.exec_module(mod)
    return mod


def _load_state_promoter():
    spec = importlib.util.spec_from_file_location("state_promoter", SCRIPTS_DIR / "state-promoter.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    with _forced_fake_doc_fm():
        spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixture: minimal state file with one done .md item
# ---------------------------------------------------------------------------

INBOX_PATH = "100 Inbox/"
NOTE_PATH = INBOX_PATH + "Asahikawa.md"
SUGG_PATH = INBOX_PATH + "2026-05-31_1200_suggestions.md"


@pytest.fixture()
def done_state_file(tmp_path: Path) -> Path:
    p = tmp_path / "inbox-state.jsonl"
    p.write_text(
        json.dumps({
            "stem": "Asahikawa",
            "path": NOTE_PATH,
            "status": "done",
            "run_id": "run-t44",
        }) + "\n"
    )
    return p


# ---------------------------------------------------------------------------
# B1: mark-captured writes tomo.state=captured via write_frontmatter
#     — no tag field anywhere in the payload
# ---------------------------------------------------------------------------


def test_capture_writes_frontmatter_state_not_tag(done_state_file, monkeypatch):
    """mark-captured writes tomo.state=captured via write_frontmatter; no tags key."""
    mod = _load_mark_captured()

    recorded: list[dict] = []

    def _fake_write(path, frontmatter, mode="merge", expected_modified=None):
        recorded.append(frontmatter)
        return {"path": path, "modified": 1}

    fake_client = MagicMock()
    fake_client.read_frontmatter.return_value = {"modified": 1}
    fake_client.write_frontmatter.side_effect = _fake_write

    monkeypatch.setattr(mod, "KadoClient", lambda: fake_client)
    monkeypatch.setattr(
        sys, "argv",
        ["mark-captured.py", "--state", str(done_state_file), "--run-id", "run-t44"],
    )

    rc = mod.main()
    assert rc == 0

    assert recorded, "No write_frontmatter calls made"
    payload = recorded[0]

    # Primary: tomo.state must be 'captured'
    tomo = payload.get("tomo", {})
    assert tomo.get("state") == "captured", (
        f"Expected tomo.state='captured', got {tomo.get('state')!r}"
    )
    assert tomo.get("doc_type") == "source"

    # No tag field at any level in the payload
    def _has_tags(obj) -> bool:
        if isinstance(obj, dict):
            return "tags" in obj or any(_has_tags(v) for v in obj.values())
        if isinstance(obj, list):
            return any(_has_tags(i) for i in obj)
        return False

    assert not _has_tags(payload), (
        f"Tag field found in write_frontmatter payload: {payload}"
    )

    # No prefix-shaped string values (belt-and-suspenders)
    def _has_prefix_value(obj) -> bool:
        if isinstance(obj, str):
            return "#" in obj and ("captured" in obj or "tomo" in obj.lower())
        if isinstance(obj, dict):
            return any(_has_prefix_value(v) for v in obj.values())
        if isinstance(obj, list):
            return any(_has_prefix_value(i) for i in obj)
        return False

    assert not _has_prefix_value(payload), (
        f"Tag-prefix value found in write_frontmatter payload: {payload}"
    )


# ---------------------------------------------------------------------------
# B2: inbox-triage discovery uses search_by_frontmatter("tomo.state=captured")
#     — NOT byTag; captured items excluded from new_sources
# ---------------------------------------------------------------------------


def test_discovery_uses_frontmatter_not_tag(tmp_path):
    """inbox-triage discover() calls search_by_frontmatter for tomo.state,
    and items returned by 'tomo.state=captured' are excluded from new_sources."""
    mod = _load_inbox_triage()

    fresh_path = INBOX_PATH + "fresh-note.md"
    captured_path = INBOX_PATH + "already-captured.md"

    class RecordingClient:
        """Records every method call; mirrors FakeKadoClient pattern from test_inbox_triage."""
        def __init__(self):
            self.calls: list[tuple[str, str | None]] = []

        def list_dir(self, path, *, depth=None, limit=500):
            self.calls.append(("list_dir", path))
            return [
                {"path": fresh_path, "type": "file", "modified": 1, "size": 10},
                {"path": captured_path, "type": "file", "modified": 1, "size": 10},
            ]

        def search_by_frontmatter(self, query, *, path_prefix=None, limit=500,
                                   modified_after=None):
            self.calls.append(("search_by_frontmatter", query))
            if query == "tomo.state=captured":
                return [{"path": captured_path, "modified": 1,
                         "frontmatter": {"tomo": {"doc_type": "source",
                                                   "state": "captured",
                                                   "run_id": "old"}}}]
            return []

        def read_note(self, path):
            self.calls.append(("read_note", path))
            return {"content": "", "modified": 0}

    client = RecordingClient()
    state = mod.discover(client, INBOX_PATH, output_dir=str(tmp_path))

    # Assert: search_by_frontmatter was called with tomo.state= queries
    fm_queries = [q for method, q in client.calls if method == "search_by_frontmatter"]
    assert any(q.startswith("tomo.state=") for q in fm_queries), (
        f"No tomo.state= frontmatter query found; calls={fm_queries}"
    )

    # Assert: byTag was NOT called (no tag-based discovery)
    tag_calls = [q for method, q in client.calls
                 if method == "search_by_frontmatter" and q is not None
                 and q.startswith("byTag")]
    assert not tag_calls, f"byTag calls detected (should not exist): {tag_calls}"

    # Assert: captured item not in new_sources (frontmatter exclusion works)
    new_source_paths = {f["path"] for f in state.new_sources}
    assert captured_path not in new_source_paths, (
        "Captured item leaked into new_sources — frontmatter exclusion broken"
    )
    assert fresh_path in new_source_paths, (
        "Fresh item missing from new_sources — discovery broken"
    )


# ---------------------------------------------------------------------------
# B3: state-promoter flips pending-approval → approved via write_frontmatter
#     (the "active → cleanup" transition in the lifecycle)
# ---------------------------------------------------------------------------


APPROVED_BODY = """\
---
tomo:
  doc_type: suggestions
  state: pending-approval
---

# Inbox Suggestions — 2026-05-31

- [x] Approved — check this box when you have finished reviewing, then run `/inbox` for Pass 2

## Summary

- Items processed: 1
"""


def test_state_promoter_active_to_cleanup_via_frontmatter():
    """state-promoter flip_state writes tomo.state=approved via write_frontmatter.

    pending-approval → approved is the 'active → cleanup' arc for suggestions docs.
    The write must go through write_frontmatter, not tag mutation.
    """
    mod = _load_state_promoter()

    recorded: list[dict] = []

    fake_client = MagicMock()
    fake_client.read_frontmatter.return_value = {"modified": 42}

    def _fake_write(path, frontmatter, mode="merge", expected_modified=None):
        recorded.append(frontmatter)
        return {"path": path, "modified": 43}

    fake_client.write_frontmatter.side_effect = _fake_write

    result = mod.flip_state(
        fake_client,
        SUGG_PATH,
        "suggestions",
        "pending-approval",
        "approved",
        "run-t44-promoter",
    )

    assert result is True, "flip_state returned False — transition rejected"
    assert recorded, "No write_frontmatter call made during flip_state"

    tomo = recorded[0].get("tomo", {})
    assert tomo.get("state") == "approved", (
        f"Expected tomo.state='approved', got {tomo.get('state')!r}"
    )

    # No tags key in the written payload
    assert "tags" not in recorded[0], (
        f"Tags key found in state-promoter write payload: {recorded[0]}"
    )


# ---------------------------------------------------------------------------
# B4: end-to-end lifecycle — three stages, all through tomo.state frontmatter
# ---------------------------------------------------------------------------


def test_end_to_end_lifecycle_all_stages_use_frontmatter(done_state_file, monkeypatch,
                                                           tmp_path):
    """Full lifecycle passes through tomo.state frontmatter at every stage.

    Stage 1 (capture): mark-captured writes tomo.state=captured
    Stage 2 (active):  inbox-triage discover() finds it via tomo.state=captured
                       and excludes it from new_sources
    Stage 3 (cleanup): state-promoter flip_state promotes pending-approval → approved
                        (simulated as a separate doc)

    All write_frontmatter calls across all stages must carry tomo.state — no tags.
    """
    all_writes: list[dict] = []

    # --- Stage 1: capture via mark-captured ---
    mc_mod = _load_mark_captured()

    mc_client = MagicMock()
    mc_client.read_frontmatter.return_value = {"modified": 1}

    def _mc_write(path, frontmatter, mode="merge", expected_modified=None):
        all_writes.append({"stage": "capture", "path": path, "payload": frontmatter})
        return {"path": path, "modified": 2}

    mc_client.write_frontmatter.side_effect = _mc_write
    monkeypatch.setattr(mc_mod, "KadoClient", lambda: mc_client)
    monkeypatch.setattr(
        sys, "argv",
        ["mark-captured.py", "--state", str(done_state_file), "--run-id", "run-e2e"],
    )
    rc = mc_mod.main()
    assert rc == 0, "mark-captured failed"

    # --- Stage 2: discovery via inbox-triage ---
    it_mod = _load_inbox_triage()

    class DiscoveryClient:
        def list_dir(self, path, *, depth=None, limit=500):
            return [{"path": NOTE_PATH, "type": "file", "modified": 1, "size": 10}]

        def search_by_frontmatter(self, query, *, path_prefix=None, limit=500,
                                   modified_after=None):
            if query == "tomo.state=captured":
                return [{"path": NOTE_PATH, "modified": 2,
                         "frontmatter": {"tomo": {"doc_type": "source",
                                                   "state": "captured",
                                                   "run_id": "run-e2e"}}}]
            return []

        def read_note(self, path):
            return {"content": "", "modified": 0}

    disc_state = it_mod.discover(DiscoveryClient(), INBOX_PATH, output_dir=str(tmp_path))
    # Captured note must not appear as a new source (discovery worked)
    new_paths = {f["path"] for f in disc_state.new_sources}
    assert NOTE_PATH not in new_paths, (
        "Captured note leaked into new_sources — discovery frontmatter exclusion broken"
    )

    # --- Stage 3: cleanup via state-promoter ---
    sp_mod = _load_state_promoter()

    sp_client = MagicMock()
    sp_client.read_frontmatter.return_value = {"modified": 5}

    def _sp_write(path, frontmatter, mode="merge", expected_modified=None):
        all_writes.append({"stage": "cleanup", "path": path, "payload": frontmatter})
        return {"path": path, "modified": 6}

    sp_client.write_frontmatter.side_effect = _sp_write
    result = sp_mod.flip_state(
        sp_client, SUGG_PATH, "suggestions",
        "pending-approval", "approved", "run-e2e",
    )
    assert result is True, "flip_state returned False"

    # --- Assertions across all stages ---
    assert all_writes, "No write_frontmatter calls recorded across any stage"

    for write in all_writes:
        tomo = write["payload"].get("tomo", {})
        assert "state" in tomo, (
            f"Stage '{write['stage']}': tomo.state missing from payload: {write['payload']}"
        )
        assert "tags" not in write["payload"], (
            f"Stage '{write['stage']}': tags key found in payload: {write['payload']}"
        )

    # Capture stage must produce tomo.state=captured
    capture_writes = [w for w in all_writes if w["stage"] == "capture"]
    assert capture_writes, "No capture-stage write found"
    assert capture_writes[0]["payload"]["tomo"]["state"] == "captured"

    # Cleanup stage must produce tomo.state=approved
    cleanup_writes = [w for w in all_writes if w["stage"] == "cleanup"]
    assert cleanup_writes, "No cleanup-stage write found"
    assert cleanup_writes[0]["payload"]["tomo"]["state"] == "approved"


# ---------------------------------------------------------------------------
# S1: source-invariant — no tag_prefix / byTag in mark-captured lifecycle path
# ---------------------------------------------------------------------------


def test_mark_captured_source_has_no_tag_prefix_references():
    """mark-captured.py must not reference tag_prefix or byTag in any form.

    Secondary guard: the primary behavioural tests (B1-B4) are the real
    regression guard; this assertion catches drift at the source level.
    """
    script_path = SCRIPTS_DIR / "mark-captured.py"
    source = script_path.read_text(encoding="utf-8")

    assert "tag_prefix" not in source, (
        "mark-captured.py references 'tag_prefix' — vestigial prefix code present"
    )
    assert "byTag" not in source, (
        "mark-captured.py references 'byTag' — should use byFrontmatter only"
    )
    assert "lifecycle.tag_prefix" not in source, (
        "mark-captured.py references 'lifecycle.tag_prefix' — vestigial config read"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
