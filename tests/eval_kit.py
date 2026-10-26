"""eval_kit.py — shared helpers for the plugin-eval suite tests (spec 041).

Imported by test_eval_suite_shape.py (the stub kit, the leak guard) and
test_eval_conductor_cases.py (the conductor cases and their graders), and by
later phases' case tests. Sources the real kit and runs the real scaffolds in
tmp_path; nothing writes into the repo.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
EVALS = REPO / "evals"
KIT = EVALS / "_lib" / "stubs.sh"
NO_LEAK = EVALS / "_lib" / "no-leak.md"

RELAYS = ("withheld-deletes.md", "withheld-attachments.md")


def stage(
    ws: Path, audit: str = "ok", deletes: int | str = 0, attach: int | str = 0,
    check: bool = True, upload: str | None = None, flip: str | None = None,
) -> subprocess.CompletedProcess:
    """Source the kit the way a case scaffold does, with cwd = the workspace.
    `upload`/`flip` None leaves UPLOAD_RESULT/FLIP_RESULT unset, as the three
    original scaffolds do."""
    ws.mkdir(parents=True, exist_ok=True)
    optional = "".join(
        f"{var}={value}\n"
        for var, value in (("UPLOAD_RESULT", upload), ("FLIP_RESULT", flip))
        if value is not None
    )
    script = (
        f"set -e\nAUDIT_RESULT={audit}\nWITHHELD_DELETES={deletes}\n"
        f"WITHHELD_ATTACH={attach}\n{optional}. '{KIT}'\nstage_instance\n"
    )
    return subprocess.run(
        ["/bin/bash", "-c", script], cwd=ws, check=check,
        capture_output=True, text=True,
    )


def run_stub(ws: Path, name: str, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", f"scripts/{name}.py", *argv],
        cwd=ws, capture_output=True, text=True, check=False,
    )


def render(ws: Path) -> subprocess.CompletedProcess:
    return run_stub(
        ws, "instruction-render", "--output-dir", "tomo-tmp/rendered",
        "--run-id", "x",
    )


def js_unescape(pattern: str) -> str:
    return re.sub(r"\\(.)", r"\1", pattern)


def js_escape(text: str) -> str:
    return re.sub(r"([.*+?^${}()|\[\]\\/])", r"\\\1", text)


def grader(case: str, name: str) -> dict:
    text = (EVALS / case / "graders" / f"{name}.md").read_text(encoding="utf-8")
    m = re.fullmatch(r"---\n(.*?)\n---\n", text, re.S)
    assert m, f"{case}/{name}: not a frontmatter-only grader"
    return yaml.safe_load(m.group(1))


def grader_names(case: str) -> set[str]:
    return {p.stem for p in (EVALS / case / "graders").glob("*.md")}


def case_yaml(case: str) -> dict:
    return yaml.safe_load((EVALS / case / "case.yaml").read_text(encoding="utf-8"))


def run_scaffold(tmp_path: Path, case: str) -> Path:
    """Run the case's real scaffold the way the CLI does: $0 = its path inside
    an evals/ copy, cwd = an empty workspace."""
    tree = tmp_path / "plugin" / "evals"
    shutil.copytree(EVALS / "_lib", tree / "_lib")
    shutil.copytree(EVALS / case, tree / case)
    ws = tmp_path / "ws"
    ws.mkdir()
    subprocess.run(
        ["/bin/bash", str(tree / case / "scaffold.sh")], cwd=ws, check=True,
        capture_output=True, text=True,
    )
    return ws


def kit_lines(tmp_path: Path, case: str) -> dict:
    """What the conductor would see in this case: audit stdout lines and the
    relay lines the render stub writes."""
    ws = run_scaffold(tmp_path, case)
    render(ws)
    relays = {}
    for relay in RELAYS:
        p = ws / "tomo-tmp" / relay
        relays[relay] = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    return {
        "audit": run_stub(ws, "instructions-diff").stdout.splitlines(),
        "deletes": relays["withheld-deletes.md"],
        "attach": relays["withheld-attachments.md"],
    }


def bash_input(command: str, description: str = "Run step") -> str:
    """The tool_used input_match target: the JSON-encoded tool input."""
    return json.dumps({"command": command, "description": description}, ensure_ascii=False)
