"""#78-B: drift checksum must hash the doc BODY only, so Tomo's own post-render
frontmatter mutation (tomo.state → approved, updated_at) does not register as
content drift. instruction-render (record side) and inbox-triage (check side)
must strip identically so recorded and current checksums stay comparable.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.doc_frontmatter import body_after_frontmatter  # noqa: E402


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod

_triage = _load("inbox_triage", "inbox-triage.py")
_render = _load("instruction_render", "instruction-render.py")


_BODY = "\n# Inbox Suggestions\n\n- [x] Approved\n\n### S01 — A\n- item\n"

DOC_PENDING = (
    "---\n"
    "type: tomo-suggestions\n"
    "tomo:\n"
    "  state: pending-approval\n"
    "  updated_at: 2026-06-20T19:37:19Z\n"
    "---\n" + _BODY
)
# Same body, only the Tomo-managed frontmatter changed (the post-render flip).
DOC_APPROVED = (
    "---\n"
    "type: tomo-suggestions\n"
    "tomo:\n"
    "  state: approved\n"
    "  updated_at: 2026-06-20T19:54:28Z\n"
    "---\n" + _BODY
)
# Real user edit: a body line changed.
DOC_EDITED = DOC_APPROVED.replace("- item", "- item edited")


# ── lib helper ───────────────────────────────────────────────────────────────

def test_body_after_frontmatter_strips_leading_block():
    assert body_after_frontmatter(DOC_PENDING) == _BODY
    assert body_after_frontmatter(DOC_APPROVED) == _BODY

def test_body_after_frontmatter_passthrough_without_frontmatter():
    plain = "# No frontmatter\n\n- x\n"
    assert body_after_frontmatter(plain) == plain

def test_body_after_frontmatter_unclosed_fence_passthrough():
    broken = "---\ntype: x\nno closing fence\n"
    assert body_after_frontmatter(broken) == broken


# ── #78-B: frontmatter-only change is NOT drift ──────────────────────────────

def test_state_flip_does_not_change_checksum():
    assert _triage._compute_checksum(DOC_PENDING) == _triage._compute_checksum(DOC_APPROVED)

def test_real_body_edit_changes_checksum():
    assert _triage._compute_checksum(DOC_EDITED) != _triage._compute_checksum(DOC_APPROVED)


# ── record (instruction-render) vs check (inbox-triage) parity ───────────────

def test_record_and_check_checksums_agree(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text(DOC_PENDING, encoding="utf-8")
    recorded = _render._compute_sha256(str(f))
    current = _triage._compute_checksum(DOC_APPROVED)  # post-flip on the check side
    assert recorded == current  # body-only hash → stable across the state flip
