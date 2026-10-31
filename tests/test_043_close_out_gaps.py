"""test_043_close_out_gaps.py — criteria parts of spec 043 that no test could fail.

The spec 043 close-out trace (docs/XDD/specs/043-pass1-conductor-eval-gate/close-out.md)
found three PRD criteria parts that were documented but asserted by nothing:

- F5-AC4: every RED proof is recorded with its mutation, its expected graders, the 3
  verdicts and the results path. The mutation table in evals/_mutations/README.md was
  checked against the patch files, but nothing read red-proofs.md.
- F7-AC1: evals/README.md names the three spike limits (background dispatch and several
  result frames, the trace format with the claude version, the analyst not covered).
- F3-AC1: the analyst stand-in "costs no Kado access". The runner tests pin the stand-in's
  bytes to its source file, not what that file grants, and nothing checked that the stub
  kit's scripts stay off the network.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVALS = REPO / "evals"
MUTATIONS_README = EVALS / "_mutations" / "README.md"
RED_PROOFS = REPO / "docs" / "XDD" / "specs" / "043-pass1-conductor-eval-gate" / "red-proofs.md"
EVAL_README = EVALS / "README.md"
STAND_IN = EVALS / "_lib" / "inbox-analyst.stub.md"
PASS1_KIT = EVALS / "_lib" / "pass1-stubs.sh"

# The spec 041 patches; their proofs are recorded in spec 041's red-proofs.md.
SPEC_041_PATCHES = {
    "drop-audit-line", "always-notice", "summarise-mismatch", "write-into-scripts",
    "copy-into-config", "paraphrase-relay", "files-used-after", "attachments-first",
    "report-run-id", "failed-step-path", "flip-after-failed-upload", "explain-failure",
}
# The spec 041 patches that spec 043 rebased and re-proved (red-proofs.md Blocks C and S).
REPROVEN_041 = {"summarise-mismatch", "files-used-after", "paraphrase-relay",
                "explain-failure", "report-run-id"}
GRADER_REF = re.compile(r"`([a-z0-9-]+)/(\d+[a-z]?-[a-z0-9-]+)`")
VERDICT = re.compile(
    r"^RED \(PARTIAL SUITE[^\n]*· mutation (?P<name>[a-z0-9-]+) · "
    r"tomo-tmp/evals/\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$",
    re.M,
)


def _section(text: str, title: str) -> str:
    m = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert m, f"no '## {title}' section"
    return m.group(1)


def _proof_rows() -> dict[str, set[tuple[str, str]]]:
    """`--mutation <name>` → its expected (case, grader) pairs, from the recorded table."""
    rows: dict[str, set[tuple[str, str]]] = {}
    for line in _section(MUTATIONS_README.read_text(encoding="utf-8"), "Proofs").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        m = re.fullmatch(r"`--mutation ([^`]+)`", cells[0])
        if m:
            rows[m.group(1)] = set(GRADER_REF.findall(cells[2]))
    return rows


def _proofs_this_spec_recorded() -> dict[str, set[tuple[str, str]]]:
    rows = _proof_rows()
    wanted = (set(rows) - SPEC_041_PATCHES) | REPROVEN_041
    return {name: rows[name] for name in sorted(wanted)}


def test_every_spec_043_proof_is_recorded_red_in_3_of_3_with_its_results_path():
    """F5-AC4. Falsifies: a proof row whose verdicts were never recorded, a record that
    lost a run, or a verdict line without the mutation name or the results path."""
    proofs = _proofs_this_spec_recorded()
    assert len(proofs) == 21, sorted(proofs)  # 16 spec 043 rows + 5 re-proven 041 rows
    verdicts: dict[str, list[str]] = {}
    for m in VERDICT.finditer(RED_PROOFS.read_text(encoding="utf-8")):
        verdicts.setdefault(m.group("name"), []).append(m.group(0))
    problems = []
    for name, expected in proofs.items():
        assert expected, name
        lines = verdicts.get(name, [])
        if not lines:
            problems.append(f"{name}: no RED verdict line with its results path")
            continue
        for case, grader in sorted(expected):
            if not any(all(f"{case}: {grader} (run {r})" in ln for r in range(3)) for ln in lines):
                problems.append(f"{name}: {case}/{grader} is not red in runs 0, 1 and 2 of one verdict")
    assert not problems, problems


def test_known_limits_name_the_three_spike_limits():
    """F7-AC1. Falsifies: deleting or gutting any of the three limits the PRD names."""
    limits = _section(EVAL_README.read_text(encoding="utf-8"), "Known limits")
    bullets = [b for b in limits.splitlines() if b.startswith("- ")]
    background = [b for b in bullets if "run in the background" in b]
    assert background and "several result frames" in background[0], "background dispatch limit"
    trace = [b for b in bullets if "trace format is a dependency" in b]
    assert trace, "trace-format limit"
    assert "hand-back frame" in trace[0] and re.search(r"`claude` 2\.1\.\d+", trace[0]), trace[0]
    assert any("analyst's own behaviour is not covered" in b for b in bullets), "analyst limit"


def test_the_analyst_stand_in_and_the_stub_kit_cannot_reach_kado():
    """F3-AC1 "costs no Kado access". Falsifies: a stand-in granted any tool beyond Bash
    (an MCP Kado tool in particular), and a stub that opens a network connection."""
    head = STAND_IN.read_text(encoding="utf-8").split("\n---\n", 1)[0]
    tools = re.search(r"^tools:\s*(.+)$", head, re.M)
    assert tools and tools.group(1).strip() == "Bash", head
    kit = PASS1_KIT.read_text(encoding="utf-8")
    for marker in ("urllib", "http.client", "requests", "socket", "kado_client",
                   "curl ", "wget ", "127.0.0.1", "localhost", "23026", "mcp__"):
        assert marker not in kit, f"pass1-stubs.sh contains {marker!r}"
