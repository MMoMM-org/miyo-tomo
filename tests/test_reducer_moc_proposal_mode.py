#!/usr/bin/env python3
# version: 0.1.0
"""test_reducer_moc_proposal_mode.py — T3.1: suggestions-reducer --moc-proposal-mode

Six tests cover the new `--moc-proposal-mode` branch and `render_moc_proposal_doc`
function added to `suggestions-reducer.py`:

  test_single_cluster_render       — 1 cluster → 1 ### MOC01 section with exact shape
  test_multi_cluster_render        — 3 clusters → 3 sections sorted by confidence DESC
  test_overflow_footer             — max_results=5, 7 clusters → 5 sections + footer
  test_filename_top_confidence_slug — filename follows ADR-2 pattern
  test_per_child_existing_up_annotation — all three annotation branches (valid/absent/broken)
  test_template_why_narrative      — Why-section template, parent-present + parent-null branches
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "suggestions-reducer.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load suggestions-reducer.py as a module (hyphen in filename → importlib).
_spec = importlib.util.spec_from_file_location("suggestions_reducer", SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["suggestions_reducer"] = _mod
_spec.loader.exec_module(_mod)

render_moc_proposal_doc = _mod.render_moc_proposal_doc  # type: ignore[attr-defined]


# ── Stub config ─────────────────────────────────────────────────────────────


class _Cfg:
    """Minimal duck-typed config stub exposing only max_results."""

    def __init__(self, max_results: int = 5):
        self.max_results = max_results


# ── Report builder helpers ───────────────────────────────────────────────────


def _candidate(
    stem: str,
    *,
    existing_up: str | None = None,
    existing_up_broken: bool = False,
    topics: list[str] | None = None,
    classification: str | None = None,
    level: int = 0,
    path: str = "",
) -> dict:
    return {
        "stem": stem,
        "path": path or f"Atlas/202 Notes/{stem}.md",
        "topics": topics or [],
        "existing_up": existing_up,
        "existing_up_broken": existing_up_broken,
        "classification": classification,
        "level": level,
    }


def _cluster(
    cluster_id: str,
    *,
    title: str,
    confidence: float,
    candidate_stems: list[str],
    topic_keywords: list[str] | None = None,
    slug: str | None = None,
    location: str = "Atlas/200 Maps/",
    template: str = "t_moc_tomo",
    existing_up: list[dict] | None = None,
) -> dict:
    """Build a topic_cluster dict as moc-discovery.py would emit."""
    return {
        "cluster_id": cluster_id,
        "title": title,
        "confidence": confidence,
        "candidate_stems": candidate_stems,
        "topic_keywords": topic_keywords or [],
        "slug": slug or title.lower().replace(" ", "-"),
        "location": location,
        "template": template,
        "existing_up": existing_up or [],
    }


def _empty_report() -> dict:
    """Minimal DiscoveryReport skeleton."""
    return {
        "schema_version": "1",
        "run_id": "test-run-id",
        "mode": "tag",
        "trigger_arg": "topic/applied/zsh",
        "profile": "miyo",
        "candidates_total": 0,
        "candidates_after_prefilter": 0,
        "candidates_capped": False,
        "candidates": [],
        "topic_clusters": [],
        "parent_options_per_cluster": {},
        "duplicates_skipped": [],
        "squelched": [],
        "abort_reason": None,
        "abort_message": None,
        "extracted_via_llm_count": 0,
        "cache_miss_batches_used": 0,
    }


# ── Tests ────────────────────────────────────────────────────────────────────


def test_single_cluster_render() -> None:
    """1 cluster → 1 ### MOC01 section with correct shape per ADR-4 + UI Visualization Guide."""
    report = _empty_report()
    report["candidates"] = [
        _candidate("oh-my-zsh"),
        _candidate("zsh-aliases"),
        _candidate("iterm-config"),
    ]
    report["topic_clusters"] = [
        _cluster(
            "MOC01",
            title="Shell & Terminal (MOC)",
            confidence=0.78,
            candidate_stems=["oh-my-zsh", "zsh-aliases", "iterm-config"],
            topic_keywords=["shell", "terminal", "zsh"],
            slug="shell-terminal-moc",
            location="Atlas/200 Maps/",
            template="t_moc_tomo",
        )
    ]
    report["parent_options_per_cluster"] = {
        "MOC01": [
            {"moc_stem": "2600 - Applied Sciences", "confidence": 0.85, "label": "Applied Sciences (Dewey 2600)"},
        ]
    }

    path, body = render_moc_proposal_doc(report, _Cfg())

    # Section heading format (ADR-4)
    assert "### MOC01 — Shell & Terminal (MOC)" in body

    # Top-level Accept list-item (ADR-4)
    assert "- [ ] Accept" in body

    # Editable text fields
    assert "**Title:**" in body
    assert "Shell & Terminal (MOC)" in body
    assert "**Location:**" in body
    assert "Atlas/200 Maps/" in body
    assert "**Template:**" in body
    assert "t_moc_tomo" in body

    # Trigger + Confidence + Cluster summary
    assert "**Trigger:**" in body
    assert "**Confidence:**" in body
    assert "78%" in body
    assert "**Cluster:**" in body

    # Parent section present
    assert "#### Parent" in body

    # Children section present
    assert "#### Children" in body

    # Override section present
    assert "#### up::-Handling Override" in body

    # Why section present
    assert "#### Why this proposal" in body


def test_multi_cluster_render() -> None:
    """3 clusters → sections MOC01, MOC02, MOC03; sorted by confidence DESC."""
    report = _empty_report()
    report["candidates"] = [
        _candidate("note-a"),
        _candidate("note-b"),
        _candidate("note-c"),
        _candidate("note-d"),
    ]
    report["topic_clusters"] = [
        _cluster("MOC01", title="Low Confidence (MOC)", confidence=0.30,
                 candidate_stems=["note-a"], slug="low-confidence-moc"),
        _cluster("MOC02", title="High Confidence (MOC)", confidence=0.90,
                 candidate_stems=["note-b", "note-c"], slug="high-confidence-moc"),
        _cluster("MOC03", title="Medium Confidence (MOC)", confidence=0.55,
                 candidate_stems=["note-d"], slug="medium-confidence-moc"),
    ]
    report["parent_options_per_cluster"] = {}

    path, body = render_moc_proposal_doc(report, _Cfg())

    # All three MOC headings present
    assert "### MOC01 — " in body
    assert "### MOC02 — " in body
    assert "### MOC03 — " in body

    # Sorted by confidence DESC: High (0.90) first, Medium (0.55) second, Low (0.30) last
    pos_high = body.index("High Confidence (MOC)")
    pos_medium = body.index("Medium Confidence (MOC)")
    pos_low = body.index("Low Confidence (MOC)")
    assert pos_high < pos_medium < pos_low, (
        "Clusters must be sorted by confidence DESC: "
        f"high={pos_high} medium={pos_medium} low={pos_low}"
    )


def test_overflow_footer() -> None:
    """max_results=5 with 7 clusters → 5 sections + '2 additional cluster(s) found' footer."""
    report = _empty_report()
    report["candidates"] = [_candidate(f"note-{i}") for i in range(7)]
    report["topic_clusters"] = [
        _cluster(
            f"MOC{i+1:02d}",
            title=f"Topic {i+1} (MOC)",
            confidence=round(0.90 - i * 0.05, 2),
            candidate_stems=[f"note-{i}"],
            slug=f"topic-{i+1}-moc",
        )
        for i in range(7)
    ]
    report["parent_options_per_cluster"] = {}

    cfg = _Cfg(max_results=5)
    path, body = render_moc_proposal_doc(report, cfg)

    # Exactly 5 MOC sections rendered
    section_count = body.count("### MOC")
    assert section_count == 5, f"Expected 5 sections, got {section_count}"

    # Footer present for the 2 overflow clusters
    assert "2 additional cluster(s) found" in body


def test_filename_top_confidence_slug() -> None:
    """Filename = <YYYY-MM-DD>_<HHMM>_moc-proposal-<top-confidence-slug>.md.

    Matches the canonical Tomo artifact pattern shared with suggestions,
    instructions, and suggestions-fan.
    """
    report = _empty_report()
    report["candidates"] = [_candidate("note-a"), _candidate("note-b")]
    report["topic_clusters"] = [
        _cluster("MOC01", title="Low Topic (MOC)", confidence=0.20,
                 candidate_stems=["note-a"], slug="low-topic-moc"),
        _cluster("MOC02", title="Shell Terminal (MOC)", confidence=0.88,
                 candidate_stems=["note-b"], slug="shell-terminal-moc"),
    ]
    report["parent_options_per_cluster"] = {}

    # Two-arg form returns (filename_str, body); file-write is caller's responsibility.
    filename, body = render_moc_proposal_doc(report, _Cfg())

    # Must end with .md
    assert filename.endswith(".md"), f"Bad suffix: {filename!r}"

    # Must include the top-confidence slug (shell-terminal-moc, confidence 0.88)
    assert "shell-terminal-moc" in filename, (
        f"Top-confidence slug 'shell-terminal-moc' not in filename {filename!r}"
    )

    # Pattern: YYYY-MM-DD_HHMM_moc-proposal-<slug>.md
    import re
    pattern = r"^\d{4}-\d{2}-\d{2}_\d{4}_moc-proposal-"
    assert re.match(pattern, filename), (
        f"Filename does not match YYYY-MM-DD_HHMM_moc-proposal- pattern: {filename!r}"
    )


def test_per_child_existing_up_annotation() -> None:
    """Children rendered with correct parenthetical for valid / absent / broken existing_up."""
    report = _empty_report()
    report["candidates"] = [
        _candidate("note-valid", existing_up="[[2600 - Applied Sciences]]"),
        _candidate("note-absent", existing_up=None),
        _candidate("note-broken", existing_up="[[NonExistentMOC]]", existing_up_broken=True),
    ]
    report["topic_clusters"] = [
        _cluster(
            "MOC01",
            title="Test Topic (MOC)",
            confidence=0.70,
            candidate_stems=["note-valid", "note-absent", "note-broken"],
            slug="test-topic-moc",
            existing_up=[
                {"stem": "note-valid", "state": "valid", "target": "2600 - Applied Sciences"},
                {"stem": "note-absent", "state": "absent", "target": None},
                {"stem": "note-broken", "state": "broken", "target": "NonExistentMOC"},
            ],
        )
    ]
    report["parent_options_per_cluster"] = {}

    path, body = render_moc_proposal_doc(report, _Cfg())

    # Valid: "existing up:: [[...]] → wird `related::`"
    assert "wird `related::`" in body, (
        f"Valid annotation not found in:\n{body}"
    )

    # Absent: "kein up:: bisher"
    assert "kein up:: bisher" in body, f"Absent annotation not found in:\n{body}"

    # Broken: full annotation string
    assert "(existing up:: broken — ignored)" in body, f"Broken annotation not found in:\n{body}"


def test_template_why_narrative() -> None:
    """Why-section uses template fields; covers parent-present and parent-null branches."""
    # ── Branch 1: parent present ──────────────────────────────────────────────
    report_with_parent = _empty_report()
    report_with_parent["candidates"] = [
        _candidate(f"note-{i}", existing_up="[[2600 - Applied Sciences]]")
        for i in range(5)
    ]
    report_with_parent["topic_clusters"] = [
        _cluster(
            "MOC01",
            title="Shell Topic (MOC)",
            confidence=0.80,
            candidate_stems=[f"note-{i}" for i in range(5)],
            topic_keywords=["shell", "terminal"],
            slug="shell-topic-moc",
            existing_up=[
                {"stem": f"note-{i}", "state": "valid", "target": "2600 - Applied Sciences"}
                for i in range(5)
            ],
        )
    ]
    report_with_parent["parent_options_per_cluster"] = {
        "MOC01": [
            {"moc_stem": "2600 - Applied Sciences", "confidence": 0.85, "label": "Applied Sciences (Dewey 2600)"},
        ]
    }

    path1, body1 = render_moc_proposal_doc(report_with_parent, _Cfg())

    # Middle sentence present when parent exists
    assert "haben up:: zur Klassifikation" in body1, (
        f"Middle sentence missing from Why section:\n{body1}"
    )
    assert "Diese MOC würde die Lücke füllen" in body1

    # ── Branch 2: no parent ───────────────────────────────────────────────────
    report_no_parent = _empty_report()
    report_no_parent["candidates"] = [
        _candidate(f"note-{i}") for i in range(3)
    ]
    report_no_parent["topic_clusters"] = [
        _cluster(
            "MOC01",
            title="Orphan Topic (MOC)",
            confidence=0.60,
            candidate_stems=[f"note-{i}" for i in range(3)],
            topic_keywords=["orphan"],
            slug="orphan-topic-moc",
            existing_up=[
                {"stem": f"note-{i}", "state": "absent", "target": None}
                for i in range(3)
            ],
        )
    ]
    report_no_parent["parent_options_per_cluster"] = {}

    path2, body2 = render_moc_proposal_doc(report_no_parent, _Cfg())

    # Middle sentence MUST NOT appear when no parent
    assert "haben up:: zur Klassifikation" not in body2, (
        f"Middle sentence should NOT appear when parent is null:\n{body2}"
    )
    # First + last sentences still present
    assert "Notes mit Topic-Overlap" in body2
    assert "Diese MOC würde die Lücke füllen" in body2

    # Deterministic: calling render_moc_proposal_doc twice with same input
    # produces same body (modulo datetime in frontmatter)
    path3, body3 = render_moc_proposal_doc(report_no_parent, _Cfg())
    # Strip first-line (frontmatter created timestamp may differ by seconds)
    body2_lines = [line for line in body2.splitlines() if "created:" not in line]
    body3_lines = [line for line in body3.splitlines() if "created:" not in line]
    assert body2_lines == body3_lines, "render_moc_proposal_doc is not deterministic"


# ── CLI error-path tests (W3) ────────────────────────────────────────────────

_SCRIPT = str(SCRIPT_PATH)


def test_cli_missing_input_flag(tmp_path: Path) -> None:
    """--moc-proposal-mode without --input → exit 1."""
    result = subprocess.run(
        ["python3", _SCRIPT, "--moc-proposal-mode", "--output-dir", str(tmp_path)],
        capture_output=True,
    )
    assert result.returncode == 1, (
        f"Expected exit 1 for missing --input, got {result.returncode};\n"
        f"stderr: {result.stderr.decode()}"
    )


def test_cli_nonexistent_input_file(tmp_path: Path) -> None:
    """--moc-proposal-mode with a path that does not exist → exit 1."""
    bad_path = tmp_path / "does-not-exist.json"
    result = subprocess.run(
        [
            "python3", _SCRIPT,
            "--moc-proposal-mode",
            "--input", str(bad_path),
            "--output-dir", str(tmp_path),
        ],
        capture_output=True,
    )
    assert result.returncode == 1, (
        f"Expected exit 1 for non-existent input, got {result.returncode};\n"
        f"stderr: {result.stderr.decode()}"
    )


def test_cli_malformed_json_input(tmp_path: Path) -> None:
    """--moc-proposal-mode with a file containing invalid JSON → exit 1."""
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{ not valid json !!!", encoding="utf-8")
    result = subprocess.run(
        [
            "python3", _SCRIPT,
            "--moc-proposal-mode",
            "--input", str(bad_json),
            "--output-dir", str(tmp_path),
        ],
        capture_output=True,
    )
    assert result.returncode == 1, (
        f"Expected exit 1 for malformed JSON, got {result.returncode};\n"
        f"stderr: {result.stderr.decode()}"
    )
