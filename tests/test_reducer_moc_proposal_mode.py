#!/usr/bin/env python3
# version: 0.5.0
"""test_reducer_moc_proposal_mode.py — T3.1: suggestions-reducer --moc-proposal-mode

Nine tests cover the `--moc-proposal-mode` branch and `render_moc_proposal_doc`
function in `suggestions-reducer.py`:

  test_single_cluster_render       — 1 cluster → 1 ### MOC01 section with exact shape
  test_multi_cluster_render        — 3 clusters → 3 sections sorted by confidence DESC
  test_overflow_footer             — max_results=5, 7 clusters → 5 sections + footer
  test_filename_top_confidence_slug — filename follows ADR-2 pattern
  test_per_child_existing_up_annotation — all three annotation branches (valid/absent/broken)
  test_template_why_narrative      — Why-section template, parent-present + parent-null branches
  test_cli_missing_input_flag      — --moc-proposal-mode without --input → exit 1
  test_cli_nonexistent_input_file  — --input points at a missing file → exit 1
  test_cli_malformed_json_input    — --input file with invalid JSON → exit 1

The case-(a) orphan link-or-create render tests (spec 021 T2.4) live in
tests/test_suggestions_reducer_orphan_render.py (gate-named), not here.
"""
from __future__ import annotations

import importlib.util
import json
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
        "orphan_suggestions": [],
        "abort_reason": None,
        "abort_message": None,
        "extracted_via_llm_count": 0,
        "cache_miss_batches_used": 0,
    }


# NOTE: orphan link-or-create render tests live in
# tests/test_suggestions_reducer_orphan_render.py (T2.4 gate-named file). The
# `orphan_suggestions: []` field stays in _empty_report() above so this skeleton
# matches the current DiscoveryReport schema.


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

    # Valid: "existing up:: [[...]] → becomes `related::`"
    assert "becomes `related::`" in body, (
        f"Valid annotation not found in:\n{body}"
    )

    # Absent: "no up:: yet"
    assert "no up:: yet" in body, f"Absent annotation not found in:\n{body}"

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
    assert "have up:: to classification" in body1, (
        f"Middle sentence missing from Why section:\n{body1}"
    )
    assert "This MOC would fill the gap" in body1

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
    assert "have up:: to classification" not in body2, (
        f"Middle sentence should NOT appear when parent is null:\n{body2}"
    )
    # First + last sentences still present
    assert "notes with topic overlap" in body2
    assert "This MOC would fill the gap" in body2

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


# ── Link members (spec 042 T2.2, PRD F4) ─────────────────────────────────────

FIXTURE_DIR = TESTS_DIR / "fixtures" / "042-t2-2-no-link-baseline"
LINK_SUFFIX = " — linked with "  # spelled out on purpose: the test pins the contract text


def _link_member(
    stem: str,
    linked_with: list[str],
    *,
    up_state: str = "absent",
    up_target: str | None = None,
) -> dict:
    return {
        "stem": stem,
        "path": f"Atlas/202 Notes/{stem}.md",
        "linked_with": linked_with,
        "up_state": up_state,
        "up_target": up_target,
    }


def _link_report(link_members: list[dict] | None) -> dict:
    report = _empty_report()
    cluster = _cluster(
        "MOC01",
        title="Energy (MOC)",
        confidence=0.8,
        candidate_stems=["Energy Level", "Sleep Debt", "Recovery Days"],
        topic_keywords=["energy"],
        existing_up=[
            {"stem": "Energy Level", "state": "absent", "target": None},
            {"stem": "Sleep Debt", "state": "valid", "target": "Health MOC"},
            {"stem": "Recovery Days", "state": "absent", "target": None},
        ],
    )
    if link_members is not None:
        cluster["link_members"] = link_members
    report["topic_clusters"] = [cluster]
    return report


def _body_after_frontmatter(doc: str) -> str:
    return doc[doc.index("\n---\n", 4) + len("\n---\n"):]


def _link_lines(body: str) -> list[str]:
    return [ln for ln in body.splitlines() if LINK_SUFFIX in ln]


TWO_LINK_MEMBERS = [
    _link_member("Afternoon Slump", ["Energy Level", "Sleep Debt"]),
    _link_member(
        "Caffeine Timing",
        ["Recovery Days", "Sleep Debt"],
        up_state="valid",
        up_target="Habits MOC",
    ),
]


def test_link_members_render_after_topic_members() -> None:
    """F4-AC1: unticked link lines follow the topic members, member wikilink first."""
    _, body = render_moc_proposal_doc(_link_report(TWO_LINK_MEMBERS), _Cfg())

    lines = body.splitlines()
    kids = lines[lines.index("#### Children (5)") + 2:]
    kids = kids[: kids.index("")]
    assert kids[:3] == [
        "- [x] [[Energy Level]] (no up:: yet)",
        "- [x] [[Sleep Debt]] (existing up:: [[Health MOC]] → becomes `related::`)",
        "- [x] [[Recovery Days]] (no up:: yet)",
    ]
    assert kids[3] == (
        "- [ ] [[Afternoon Slump]] (no up:: yet)"
        " — linked with [[Energy Level]], [[Sleep Debt]]"
    )
    assert kids[4].startswith("- [ ] [[Caffeine Timing]] ")
    assert len(kids) == 5


def test_existing_up_annotation_precedes_link_suffix() -> None:
    """F4-AC2: valid and broken existing up:: read as for a topic member, then the suffix."""
    members = [
        _link_member("Caffeine Timing", ["Sleep Debt"], up_state="valid", up_target="Habits MOC"),
        _link_member("Old Note", ["Sleep Debt"], up_state="broken", up_target="Gone"),
    ]
    _, body = render_moc_proposal_doc(_link_report(members), _Cfg())

    assert (
        "- [ ] [[Caffeine Timing]] (existing up:: [[Habits MOC]] → becomes `related::`)"
        " — linked with [[Sleep Debt]]"
    ) in body
    assert (
        "- [ ] [[Old Note]] (existing up:: broken — ignored) — linked with [[Sleep Debt]]"
    ) in body


def test_why_counts_link_members_only_when_present() -> None:
    """F4-AC3: the sentence appears for N > 0 (singular for 1), never for 0 or a missing key."""
    _, two = render_moc_proposal_doc(_link_report(TWO_LINK_MEMBERS), _Cfg())
    _, one = render_moc_proposal_doc(_link_report(TWO_LINK_MEMBERS[:1]), _Cfg())
    _, empty = render_moc_proposal_doc(_link_report([]), _Cfg())
    _, missing = render_moc_proposal_doc(_link_report(None), _Cfg())

    why = two.split("#### Why this proposal")[1]
    assert why.splitlines()[2] == (
        "3 notes with topic overlap energy have no dedicated MOC."
        " 2 more members came through links."
    )
    assert "1 more member came through links." in one
    assert "1 more members" not in one
    assert "came through links" not in empty
    assert "came through links" not in missing


def test_children_count_includes_link_members() -> None:
    """Children heading and Override count both groups; the Cluster header keeps the topic count."""
    _, body = render_moc_proposal_doc(_link_report(TWO_LINK_MEMBERS), _Cfg())

    assert "#### Children (5)" in body
    assert "(applies to all 5 children)" in body
    assert "**Cluster:** 3 Notes — energy" in body
    assert len(_link_lines(body)) == 2


def test_report_without_link_members_is_byte_identical() -> None:
    """A report without link members renders as the pre-042 renderer did (captured fixture)."""
    report = json.loads((FIXTURE_DIR / "report.json").read_text(encoding="utf-8"))
    expected = json.loads((FIXTURE_DIR / "rendered.json").read_text(encoding="utf-8"))

    _, body = render_moc_proposal_doc(report, _Cfg())

    assert _body_after_frontmatter(body) == expected["body_after_frontmatter"]


def test_link_lines_round_trip_through_the_suggestion_parser() -> None:
    """Renderer and parser agree on ADR-7: link lines add children, not candidate stems."""
    spec = importlib.util.spec_from_file_location(
        "suggestion_parser_rt", SCRIPTS_DIR / "suggestion-parser.py"
    )
    parser = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(parser)

    _, plain = render_moc_proposal_doc(_link_report(None), _Cfg())
    _, linked = render_moc_proposal_doc(_link_report(TWO_LINK_MEMBERS), _Cfg())
    plain_sections = parser.enumerate_all_moc_sections(plain)
    linked_sections = parser.enumerate_all_moc_sections(linked)

    assert len(plain_sections) == len(linked_sections) == 1
    # tuple = (moc_id, title, candidate_stems, topic_keywords)
    assert linked_sections[0][2] == plain_sections[0][2]
    assert linked_sections[0][2] == ["Energy Level", "Sleep Debt", "Recovery Days"]


# ── max_results comes from vault-config (spec 042, owner decision O3) ────────


def _render_via_cli(tmp_path: Path, config_text: str | None) -> str:
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
    inp = tmp_path / "report.json"
    inp.write_text(json.dumps(report), encoding="utf-8")
    out = tmp_path / "out"
    argv = [sys.executable, _SCRIPT, "--moc-proposal-mode", "--input", str(inp),
            "--output-dir", str(out)]
    if config_text is not None:
        cfg = tmp_path / "vault-config.yaml"
        cfg.write_text(config_text, encoding="utf-8")
        argv += ["--config", str(cfg)]
    result = subprocess.run(argv, capture_output=True, cwd=tmp_path)
    assert result.returncode == 0, result.stderr.decode()
    return Path(result.stdout.decode().strip()).read_text(encoding="utf-8")


def test_cli_max_results_from_vault_config(tmp_path: Path) -> None:
    body = _render_via_cli(tmp_path, "tomo:\n  moc_proposal:\n    max_results: 3\n")
    assert body.count("### MOC") == 3
    assert "4 additional cluster(s) found" in body


def test_cli_max_results_defaults_to_five_when_key_missing(tmp_path: Path) -> None:
    body = _render_via_cli(tmp_path, "tomo:\n  moc_proposal:\n    min_notes: 2\n")
    assert body.count("### MOC") == 5


def test_cli_max_results_defaults_to_five_without_config_file(tmp_path: Path) -> None:
    body = _render_via_cli(tmp_path, None)
    assert body.count("### MOC") == 5


# ── around: proposal (spec 042 T3.2, PRD F2-AC1) ─────────────────────────────

AROUND_FIXTURE = TESTS_DIR / "fixtures" / "042-t3-2-around-report" / "report.json"


def _around_body(report: dict | None = None) -> str:
    """Render the real `moc-discovery --around knowledge` report (captured, not invented)."""
    report = report or json.loads(AROUND_FIXTURE.read_text(encoding="utf-8"))
    _, body = render_moc_proposal_doc(report, _Cfg())
    return body


def test_around_report_renders_seed_ticked_and_neighbours_linked() -> None:
    """F2-AC1: one MOC01 section, seed ticked, neighbours unticked with the seed as reason."""
    body = _around_body()

    assert body.count("### MOC") == 1
    assert "### MOC01 — knowledge (MOC)" in body
    lines = body.splitlines()
    assert "#### Children (3)" in lines
    kids = lines[lines.index("#### Children (3)") + 2:]
    assert kids[:3] == [
        "- [x] [[knowledge]] (existing up:: [[Gardening (MOC)]] → becomes `related::`)",
        "- [ ] [[argon]] (no up:: yet) — linked with [[knowledge]]",
        "- [ ] [[neon]] (existing up:: [[Gardening (MOC)]] → becomes `related::`)"
        " — linked with [[knowledge]]",
    ]


def test_around_trigger_label() -> None:
    """The Trigger field and the frontmatter carry `around:<argument as typed>`."""
    body = _around_body()

    assert "**Trigger:** around:knowledge" in body
    assert "\ntrigger: around:knowledge\n" in body


def test_around_why_names_the_seed() -> None:
    """Why names the seed and does not use the topic-overlap or link-count sentences."""
    why = _around_body().split("#### Why this proposal")[1].strip()

    assert why == (
        "2 notes link with [[knowledge]] and have no dedicated MOC.\n"
        "This MOC would fill the gap."
    )
    assert "topic overlap" not in why
    assert "came through links" not in why


def test_around_why_is_singular_for_one_neighbour() -> None:
    report = json.loads(AROUND_FIXTURE.read_text(encoding="utf-8"))
    report["topic_clusters"][0]["link_members"] = report["topic_clusters"][0]["link_members"][:1]

    why = _around_body(report).split("#### Why this proposal")[1]

    assert "1 note links with [[knowledge]] and has no dedicated MOC." in why


# ── around: carries no Confidence line (spec 042, owner decision B) ──────────


def test_around_section_has_no_confidence_line() -> None:
    """The seed is a user choice, not a measured score: no **Confidence:** line."""
    body = _around_body()

    assert "**Confidence:**" not in body
    assert "**Trigger:** around:knowledge\n**Cluster:** 3 Notes" in body


def test_around_cluster_line_counts_all_members_and_names_the_seed() -> None:
    """Owner decision W2: total members (seed + links), not the topic count of 1."""
    body = _around_body()

    assert "**Cluster:** 3 Notes — linked around [[knowledge]]\n" in body
    assert "#### Children (3)" in body
