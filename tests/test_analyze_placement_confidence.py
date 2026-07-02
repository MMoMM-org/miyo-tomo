#!/usr/bin/env python3
# version: 0.1.0
"""test_analyze_placement_confidence.py — tests for the #71 tuning aid.

Verifies scripts/analyze-placement-confidence.py:
  - walks the real suggestions-doc.json shape (sections[].actions[].
    candidate_mocs[].anchor) and collects tier-1 heading fit_confidence values
  - flags structural headings at/above the threshold (the Asakusa "Content"
    gate-slip from #71) and NOT topical headings
  - respects --threshold and --structural-heading extension
  - exits 1 when a gate-slip is present, 0 otherwise

Doc fixtures mirror tomo/schemas/suggestions-doc.schema.json (read 2026-07-02).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "analyze-placement-confidence.py"

# Load the hyphenated script as a module.
_spec = importlib.util.spec_from_file_location("analyze_placement_confidence", SCRIPT_PATH)
mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["analyze_placement_confidence"] = mod
_spec.loader.exec_module(mod)


def _heading_anchor(moc_path, heading, fit, new_section=None):
    anchor = {
        "type": "heading",
        "value": heading,
        "placement": "after",
        "new_section": new_section,
        "fit_confidence": fit,
    }
    return {"path": moc_path, "anchor": anchor}


def _new_section_anchor(moc_path, section_name):
    return {
        "path": moc_path,
        "anchor": {
            "type": "line", "value": None, "placement": "after",
            "new_section": section_name, "fit_confidence": None,
        },
    }


def _doc(*section_specs) -> dict:
    """section_specs: list of (stem, [candidate_moc, ...])."""
    sections = []
    for i, (stem, cands) in enumerate(section_specs):
        sections.append({
            "id": f"S{i:02d}",
            "stem": stem,
            "actions": [{
                "kind": "create_atomic_note",
                "rendered_md": "# note\n",
                "candidate_mocs": cands,
            }],
        })
    return {
        "schema_version": "2",
        "generated": "2026-07-02T12:00:00Z",
        "run_id": "test",
        "profile": "miyo",
        "source_items": len(section_specs),
        "sections": sections,
    }


def _write(tmp_path: Path, doc: dict, name="suggestions-doc.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return p


# ── analyze() core ───────────────────────────────────────────────────────────


def test_collects_tier1_heading_values(tmp_path):
    doc = _doc(
        ("FPT", [_heading_anchor("Atlas/Frameworks (MOC)", "Thinking Frameworks", 0.9)]),
        ("Beppu", [_heading_anchor("Atlas/Japan (MOC)", "Onsen", 0.72)]),
    )
    path = _write(tmp_path, doc)
    report = mod.analyze([path], {"content"}, 0.6)
    assert report["tier1_heading"] == 2
    assert sorted(report["values"]) == [0.72, 0.9]
    assert report["flagged"] == []


def test_flags_structural_gate_slip(tmp_path):
    """The Asakusa case: 'Content' scored >= 0.6 and must be flagged."""
    doc = _doc(
        ("Asakusa Senso-ji", [_heading_anchor("Atlas/Japan (MOC)", "Content", 0.62)]),
        ("Sapporo", [_new_section_anchor("Atlas/Japan (MOC)", "Hokkaido")]),
    )
    path = _write(tmp_path, doc)
    report = mod.analyze([path], {"content"}, 0.6)

    assert report["tier2_new_section"] == 1
    assert len(report["flagged"]) == 1
    slip = report["flagged"][0]
    assert slip.heading == "Content"
    assert slip.fit_confidence == 0.62
    assert slip.stem == "Asakusa Senso-ji"


def test_structural_below_threshold_not_flagged(tmp_path):
    """A structural heading that correctly scored LOW is not a gate-slip."""
    doc = _doc(("X", [_heading_anchor("Atlas/M (MOC)", "Content", 0.4)]))
    path = _write(tmp_path, doc)
    report = mod.analyze([path], {"content"}, 0.6)
    # Below threshold → not flagged (and, in reality, would route to tier-2).
    assert report["flagged"] == []
    assert report["values"] == [0.4]


def test_topical_heading_never_flagged(tmp_path):
    doc = _doc(("X", [_heading_anchor("Atlas/M (MOC)", "Onsen", 0.95)]))
    path = _write(tmp_path, doc)
    report = mod.analyze([path], {"content"}, 0.6)
    assert report["flagged"] == []


def test_case_insensitive_structural_match(tmp_path):
    doc = _doc(("X", [_heading_anchor("Atlas/M (MOC)", "  content  ", 0.8)]))
    path = _write(tmp_path, doc)
    report = mod.analyze([path], {"content"}, 0.6)
    assert len(report["flagged"]) == 1


def test_bool_fit_confidence_excluded(tmp_path):
    """A stray boolean must not be counted as a numeric confidence."""
    doc = _doc(("X", [_heading_anchor("Atlas/M (MOC)", "Onsen", True)]))
    path = _write(tmp_path, doc)
    report = mod.analyze([path], {"content"}, 0.6)
    assert report["tier1_heading"] == 0
    assert report["values"] == []


def test_multi_doc_aggregation(tmp_path):
    d1 = _write(tmp_path, _doc(("A", [_heading_anchor("M", "Onsen", 0.7)])), "a.json")
    d2 = _write(tmp_path, _doc(("B", [_heading_anchor("M", "Content", 0.65)])), "b.json")
    report = mod.analyze([d1, d2], {"content"}, 0.6)
    assert report["docs_loaded"] == 2
    assert report["tier1_heading"] == 2
    assert len(report["flagged"]) == 1


def test_malformed_doc_is_skipped(tmp_path):
    good = _write(tmp_path, _doc(("A", [_heading_anchor("M", "Onsen", 0.7)])), "good.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    report = mod.analyze([good, bad], {"content"}, 0.6)
    assert report["docs_loaded"] == 1
    assert report["tier1_heading"] == 1


# ── CLI exit codes ───────────────────────────────────────────────────────────


def test_main_exit_1_on_gate_slip(tmp_path, monkeypatch, capsys):
    path = _write(tmp_path, _doc(("Asakusa", [_heading_anchor("M", "Content", 0.62)])))
    monkeypatch.setattr(sys, "argv", ["analyze-placement-confidence.py", str(path)])
    rc = mod.main()
    assert rc == 1
    out = capsys.readouterr().out
    assert "Content" in out and "0.62" in out


def test_main_exit_0_when_clean(tmp_path, monkeypatch, capsys):
    path = _write(tmp_path, _doc(("FPT", [_heading_anchor("M", "Thinking Frameworks", 0.9)])))
    monkeypatch.setattr(sys, "argv", ["analyze-placement-confidence.py", str(path)])
    rc = mod.main()
    assert rc == 0
    assert "No structural-heading placements" in capsys.readouterr().out


def test_cli_structural_heading_extension(tmp_path, monkeypatch):
    """--structural-heading extends the flagged set."""
    path = _write(tmp_path, _doc(("X", [_heading_anchor("M", "Meta", 0.8)])))
    monkeypatch.setattr(
        sys, "argv",
        ["analyze-placement-confidence.py", str(path), "--structural-heading", "Meta"],
    )
    assert mod.main() == 1


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
