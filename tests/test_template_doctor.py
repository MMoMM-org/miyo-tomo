#!/usr/bin/env python3
# version: 0.1.0
"""Tests for template-doctor.py — audit + dry-render of Tomo note templates.

The load-bearing behaviour: a template must open with a literal ``---`` fence, or
Tomo (which does not run Templater) strands its frontmatter in the note body when
it stamps the ``tomo:`` block. These tests prove the doctor PASSES a well-formed
template and FAILS a delegated-fence template — the exact bug found in ADR-026
live testing (miyo-tomo#138).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCTOR = REPO_ROOT / "tomo" / "scripts" / "template-doctor.py"

GOOD_TEMPLATE = "\n".join([
    "---",
    "UUID: {{uuid}}",
    "DateStamp: {{datestamp}}",
    "title: {{title}}",
    "tags:{{tags}}",
    "Summary: {{summary}}",
    "---",
    "",
    "# [[{{title}}]]",
    "",
    "{{body}}",
    "",
]) + "\n"

# Opening fence delegated to a Templater include — Tomo never runs it.
DELEGATED_FENCE_TEMPLATE = "\n".join([
    '<%await tp.file.include("[[x_frontmatter]]")-%>',
    "title: {{title}}",
    "tags:{{tags}}",
    "---",
    "",
    "# [[{{title}}]]",
    "",
    "{{body}}",
]) + "\n"

UNCLOSED_FENCE_TEMPLATE = "\n".join([
    "---",
    "UUID: {{uuid}}",
    "DateStamp: {{datestamp}}",
    "title: {{title}}",
    "",
    "# [[{{title}}]]",
]) + "\n"

USER_TOMO_KEY_TEMPLATE = "\n".join([
    "---",
    "UUID: {{uuid}}",
    "DateStamp: {{datestamp}}",
    "title: {{title}}",
    "tomo:",
    "  doc_type: rendered-note",
    "---",
    "",
    "# [[{{title}}]]",
]) + "\n"

UNKNOWN_TOKEN_TEMPLATE = "\n".join([
    "---",
    "UUID: {{uuid}}",
    "DateStamp: {{datestamp}}",
    "title: {{title}}",
    "mystery: {{not_a_real_token}}",
    "---",
    "",
    "# [[{{title}}]]",
]) + "\n"


def _run(mode, template_path):
    proc = subprocess.run(
        [sys.executable, str(DOCTOR), mode, "--template", str(template_path)],
        capture_output=True, text=True,
    )
    return proc.returncode, json.loads(proc.stdout)


def _status(report, check):
    for f in report["findings"]:
        if f["check"] == check:
            return f["status"]
    return None


def _write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


# ── audit ──────────────────────────────────────────────────────────────

def test_audit_good_template_passes(tmp_path):
    rc, report = _run("audit", _write(tmp_path, "good.md", GOOD_TEMPLATE))
    assert rc == 0
    assert report["ok"] is True
    assert _status(report, "leading_fence") == "PASS"
    assert _status(report, "frontmatter_closed") == "PASS"
    assert _status(report, "no_user_tomo_key") == "PASS"


def test_audit_delegated_fence_fails(tmp_path):
    rc, report = _run("audit", _write(tmp_path, "bad.md", DELEGATED_FENCE_TEMPLATE))
    assert rc == 1
    assert report["ok"] is False
    assert _status(report, "leading_fence") == "FAIL"
    assert _status(report, "frontmatter_closed") == "FAIL"


def test_audit_unclosed_fence_fails(tmp_path):
    rc, report = _run("audit", _write(tmp_path, "u.md", UNCLOSED_FENCE_TEMPLATE))
    assert rc == 1
    assert _status(report, "leading_fence") == "PASS"
    assert _status(report, "frontmatter_closed") == "FAIL"


def test_audit_user_tomo_key_fails(tmp_path):
    rc, report = _run("audit", _write(tmp_path, "t.md", USER_TOMO_KEY_TEMPLATE))
    assert rc == 1
    assert _status(report, "no_user_tomo_key") == "FAIL"


def test_audit_unknown_token_warns(tmp_path):
    rc, report = _run("audit", _write(tmp_path, "w.md", UNKNOWN_TOKEN_TEMPLATE))
    assert rc == 0  # WARN does not fail the run
    assert _status(report, "unknown_tokens") == "WARN"


def test_audit_missing_file_fails():
    rc, report = _run("audit", REPO_ROOT / "does-not-exist-xyz.md")
    assert rc == 1
    assert report["ok"] is False
    assert _status(report, "file") == "FAIL"


# ── dry-render ─────────────────────────────────────────────────────────

def test_dry_render_good_template_passes(tmp_path):
    rc, report = _run("dry-render", _write(tmp_path, "good.md", GOOD_TEMPLATE))
    assert rc == 0
    assert report["ok"] is True
    assert _status(report, "token_resolution") == "PASS"
    assert _status(report, "no_stranded_frontmatter") == "PASS"
    # The tomo: block lands inside the leading frontmatter, keys preserved.
    assert report["rendered_preview"].startswith("---\ntomo:")
    assert "title: Sample Title" in report["rendered_preview"]


def test_dry_render_delegated_fence_strands_frontmatter(tmp_path):
    rc, report = _run(
        "dry-render", _write(tmp_path, "bad.md", DELEGATED_FENCE_TEMPLATE))
    assert rc == 1
    assert report["ok"] is False
    assert _status(report, "no_stranded_frontmatter") == "FAIL"


def test_dry_render_reference_note_template_passes():
    """The shipped atomic template renders clean — regression guard."""
    tmpl = REPO_ROOT / "tomo" / "config" / "templates" / "t_note_tomo.md"
    rc, report = _run("dry-render", tmpl)
    assert rc == 0
    assert report["ok"] is True


# ── scaffold ───────────────────────────────────────────────────────────

def _scaffold(note_type):
    proc = subprocess.run(
        [sys.executable, str(DOCTOR), "scaffold", "--type", note_type],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout


def test_scaffold_requires_type():
    proc = subprocess.run(
        [sys.executable, str(DOCTOR), "scaffold"], capture_output=True, text=True)
    assert proc.returncode != 0


def test_scaffold_every_type_is_dry_render_clean(tmp_path):
    """Every scaffold must pass its own dry-render — a scaffold that strands
    frontmatter would defeat the skill's purpose."""
    for note_type in ("atomic", "moc", "daily", "project", "source"):
        rc, body = _scaffold(note_type)
        assert rc == 0, note_type
        assert body.startswith("---\n"), note_type  # literal opening fence
        p = _write(tmp_path, f"{note_type}.md", body)
        rc2, report = _run("dry-render", p)
        assert report["ok"] is True, (note_type, report["findings"])
