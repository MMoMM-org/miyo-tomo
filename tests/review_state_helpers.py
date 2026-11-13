#!/usr/bin/env python3
# version: 0.1.0
"""review_state_helpers.py — the fixtures the review_state tests share: constants, a review document's frontmatter,
the stem's meta.json, the move and insert actions, the set JSON and a Kado-backed fake vault.

Moved out of test_review_state.py (#261) so test_review_state.py, test_review_state_listing.py and
test_review_state_finished.py import them from one place instead of from a test module. Not named `test_*`, so
pytest does not collect it. All data is synthetic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from review_fake_vault import ReviewFakeVault  # noqa: E402
from lib.review_vault import Vault  # noqa: E402

INBOX = "100 Inbox/"
STEM = "2026-W13_review"
SET = INBOX + STEM + "_instructions.json"
TARGET = "Calendar/2026-W13.md"
COPY = INBOX + "2026-W13.md"
PENDING, APPROVED = "pending-approval", "approved"


def _doc(period: str, kind: str, state: str = PENDING, stem: str | None = None) -> dict:
    fm = {"tomo": {"doc_type": "review", "state": state, "run_id": "r1", "updated_at": "2026-11-11T10:00:00"},
          "review_period": period, "review_kind": kind, "review_target": f"Calendar/{period}.md",
          "review_target_exists": True, "review_language": "de"}
    if stem is not None:
        fm["review_stem"] = stem
    return fm


def _meta(root: Path, stem: str, **fields) -> None:
    stage = root / stem
    stage.mkdir(parents=True)
    (stage / "meta.json").write_text(json.dumps({"stem": stem, **fields}), encoding="utf-8")


def _move(applied: bool = False, source: str = COPY, destination: str = TARGET) -> dict:
    return {"id": "I01", "action": "move_note", "source": source, "destination": destination,
            "title": "2026-W13", "rendered_file": "2026-W13.md", "source_inbox_item": None, "applied": applied}


def _insert(applied: bool = False, action: str = "insert_under_marker", target: str = TARGET) -> dict:
    return {"id": "I01", "action": action, "target_path": target, "anchor": {"type": "heading", "value": "X"},
            "placement": "before", "content": "## Tomo Review\n", "applied": applied}


def _set(*actions) -> dict:
    return {"schema_version": "3.0.0", "type": "tomo-instructions", "generated": "2026-11-11T10:00:00Z",
            "profile": "miyo", "md_peer": STEM + "_instructions", "actions": list(actions)}


def _set_bytes(*actions) -> bytes:
    return (json.dumps(_set(*actions)) + "\n").encode("utf-8")


def _vault(files: dict | None = None) -> tuple[Vault, ReviewFakeVault]:
    fake = ReviewFakeVault(files or {})
    return Vault(fake), fake


def _empty_vault() -> Vault:
    return _vault()[0]


def _probes(fake: ReviewFakeVault) -> list:
    return [(m, p) for m, p in fake.events if m in ("read_file", "read_frontmatter", "read_note", "path_exists")]
