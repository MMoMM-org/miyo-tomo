#!/usr/bin/env python3
# version: 0.1.0
"""ADR-026 — Pass-2 change-detected precedence for _suggestions.json.

The vault-published wire is an override surface: the parser always parses the
markdown, and applies the wire's editable fields ONLY when the wire was edited
(its embedded emit_digest no longer matches a recomputation). These tests prove:

  - changed wire  ⇒ JSON overrides win (MOC selection + proposed-MOC approve/rename)
  - unchanged wire ⇒ output byte-identical to the no-wire run (no-Hashi guarantee)
  - absent / unparseable / unknown-version ⇒ markdown path, no error

The wire is built from the same suggestions-doc the markdown renders from, then
mutated in-place (leaving emit_digest stale) to simulate a Hashi edit.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
PARSER = SCRIPTS_DIR / "suggestion-parser.py"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_render_mod():
    spec = importlib.util.spec_from_file_location(
        "suggestions_render_prec", SCRIPTS_DIR / "suggestions-render.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MOD = _load_render_mod()

_TOPIC_MOC = "Atlas/200 Maps/Topic MOC"

_ATOMIC_MD = (
    "**Source:** [[memo]]\n"
    "**Suggested name:** My Note\n"
    "**Template:** [[t_note_tomo]]    ← change if you want a different template\n"
    "**Location:** [[Atlas/202 Notes/]]    ← change if you want a different folder\n"
    "\n"
    "**Decision (atomic note):**\n"
    "- [x] Approve\n"
    "- [ ] Keep source files"
)


def _doc() -> dict:
    return {
        "schema_version": "1",
        "generated": "2026-07-03T10:00:00Z",
        "run_id": "2026-07-03-1000-prec",
        "profile": "miyo",
        "source_items": 1,
        "conventions": {
            "parent_marker": "up::",
            "peer_marker": "related::",
            "moc_suffix": " MOC",
        },
        "sections": [
            {
                "id": "S01",
                "stem": "memo",
                "actions": [
                    {
                        "kind": "create_atomic_note",
                        "suggestion_id": "S01",
                        # No Link-to-MOC block ⇒ markdown parent_mocs == [].
                        "rendered_md": _ATOMIC_MD,
                        "item": {
                            "title": "My Note", "template": "t_note_tomo.md",
                            "location": "Atlas/202 Notes/", "tags": [],
                            "audio_peer": None, "worthiness": 0.9,
                            "suppressed": False, "force_atomic": False,
                        },
                        "candidate_mocs": [
                            {
                                "path": f"{_TOPIC_MOC}.md",
                                "pre_check": False,
                                "score": 0.2,
                                "anchor": {
                                    "type": "heading",
                                    "value": "Notes",
                                    "placement": "inside",
                                },
                            }
                        ],
                    }
                ],
            }
        ],
        "proposed_mocs": [
            {
                "topic": "Widgets",
                "items": ["S01"],
                "parent": "Root MOC",
                "name": "Widgets MOC",
                "tags": ["topic/widgets"],
                "reason": "cluster",
            }
        ],
        "needs_attention": [],
    }


def _full_md(doc: dict) -> str:
    sugg = "\n".join(_MOD.render_suggestions(doc))
    prop = "\n".join(_MOD.render_proposed_mocs(doc))
    return "\n".join(
        [
            "---",
            "type: tomo-suggestions",
            "generated: 2026-07-03T10:00:00Z",
            'tomo_version: "0.1.0"',
            "profile: miyo",
            "source_items: 1",
            "run_id: 2026-07-03-1000-prec",
            "---",
            "",
            "# Inbox Suggestions — 2026-07-03",
            "",
            "- [x] Approved",
            "",
            "## Summary",
            "",
            "- Items processed: 1",
            "",
            sugg,
            "",
            prop,
        ]
    )


def _run(tmp_path: Path, *, wire: dict | str | None) -> dict:
    md_path = tmp_path / "2026-07-03_1000_suggestions.md"
    md_path.write_text(_full_md(_doc()), encoding="utf-8")
    cmd = [sys.executable, str(PARSER), "--file", str(md_path)]
    if wire is not None:
        wire_path = tmp_path / "2026-07-03_1000_suggestions.json"
        if isinstance(wire, str):
            wire_path.write_text(wire, encoding="utf-8")
        else:
            wire_path.write_text(json.dumps(wire), encoding="utf-8")
        cmd += ["--suggestions-json", str(wire_path)]
    # cwd=tmp_path isolates the parser from any repo-root tomo-tmp/ doc cache.
    result = subprocess.run(
        cmd, capture_output=True, text=True, check=False, cwd=str(tmp_path)
    )
    assert result.returncode == 0, f"exit {result.returncode}\n{result.stderr}"
    return json.loads(result.stdout)


def _atomic(out: dict) -> dict:
    items = [c for c in out["confirmed_items"] if c.get("action") != "create_moc"]
    assert len(items) == 1, items
    return items[0]


def _create_mocs(out: dict) -> list[dict]:
    return [c for c in out["confirmed_items"] if c.get("action") == "create_moc"]


# ── Baseline ──────────────────────────────────────────────────────────────

def test_no_wire_has_no_moc_and_no_created_moc(tmp_path):
    out = _run(tmp_path, wire=None)
    assert _atomic(out)["parent_mocs"] == []
    assert _create_mocs(out) == []


# ── Unchanged wire ≡ markdown path (no-Hashi guarantee) ─────────────────────

def test_unchanged_wire_is_noop(tmp_path):
    baseline = _run(tmp_path, wire=None)
    wire = _MOD.build_wire_payload(_doc())  # emit_digest matches payload
    withwire = _run(tmp_path, wire=wire)
    assert withwire["confirmed_items"] == baseline["confirmed_items"]


# ── Changed wire is authoritative ───────────────────────────────────────────

def test_changed_wire_overrides_moc_selection(tmp_path):
    wire = _MOD.build_wire_payload(_doc())
    # user ticks the MOC in the editor; emit_digest left stale ⇒ "changed"
    wire["suggestions"][0]["candidate_mocs"][0]["selected"] = True
    out = _run(tmp_path, wire=wire)
    item = _atomic(out)
    assert item["parent_mocs"] == [_TOPIC_MOC]
    assert item["parent_moc"] == _TOPIC_MOC
    assert [c["path"] for c in item["candidate_mocs"]] == [_TOPIC_MOC]


def test_changed_wire_approves_and_renames_proposed_moc(tmp_path):
    wire = _MOD.build_wire_payload(_doc())
    wire["proposed_mocs"][0]["decision"] = "approve"
    wire["proposed_mocs"][0]["name"] = "Renamed MOC"
    out = _run(tmp_path, wire=wire)
    mocs = _create_mocs(out)
    assert len(mocs) == 1
    assert mocs[0]["title"] == "Renamed MOC"


def test_changed_wire_skip_default_creates_no_moc(tmp_path):
    # Only the note selection changed; proposed MOC keeps its default skip.
    wire = _MOD.build_wire_payload(_doc())
    wire["suggestions"][0]["candidate_mocs"][0]["selected"] = True
    out = _run(tmp_path, wire=wire)
    assert _create_mocs(out) == []


# ── Degraded wires fall back to markdown ────────────────────────────────────

def test_absent_wire_uses_markdown(tmp_path):
    baseline = _run(tmp_path, wire=None)
    # point at a path that will not exist
    md_path = tmp_path / "2026-07-03_1000_suggestions.md"
    md_path.write_text(_full_md(_doc()), encoding="utf-8")
    cmd = [
        sys.executable, str(PARSER), "--file", str(md_path),
        "--suggestions-json", str(tmp_path / "missing.json"),
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, check=False, cwd=str(tmp_path)
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["confirmed_items"] == baseline["confirmed_items"]


def test_unparseable_wire_falls_back(tmp_path):
    baseline = _run(tmp_path, wire=None)
    out = _run(tmp_path, wire="{ this is not json ]")
    assert out["confirmed_items"] == baseline["confirmed_items"]


def test_unknown_version_wire_ignored(tmp_path):
    baseline = _run(tmp_path, wire=None)
    wire = _MOD.build_wire_payload(_doc())
    wire["schema_version"] = "9"  # stale digest + unknown version
    wire["suggestions"][0]["candidate_mocs"][0]["selected"] = True
    out = _run(tmp_path, wire=wire)
    # ignored despite the edit — markdown path wins
    assert out["confirmed_items"] == baseline["confirmed_items"]
