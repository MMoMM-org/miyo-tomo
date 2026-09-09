#!/usr/bin/env python3
# version: 1.0.0
"""Record the spec-034 T6.2 flat-inbox instruction-set baseline.

Drives the WHOLE Pass-2 chain — `suggestion-parser.py` then
`instruction-render.py` — as it stood at commit `ee44cb3`, the commit
immediately preceding Phase 1, over the committed fixture in this directory,
and writes the normalised `instructions.md` it produced.

Run from the repo root:
    ./venv/bin/python tests/fixtures/034-t6-2-instructions-golden/record.py

The old code is reached through `git worktree add <scratch> ee44cb3`, never
`git show`. `instruction-render.py` at that commit imports nine `lib/*.py`
modules and shells out to `token-render.py`; extracting files one at a time
risks running the old renderer against a HEAD helper and producing a baseline
that is neither old nor new, silently. A whole-tree checkout removes that
failure mode, and this script asserts afterwards that every loaded `lib.*`
module really came from the scratch worktree. The scratch tree is torn down on
the way out; THIS worktree is never checked out to another commit.

No vault is touched (CON-7): both the recording and the replay read the same
`fake_kado.FakeKado` over `vault.json`.

This is NOT run by the suite. Re-run it only for a deliberate, reviewed change
of baseline — and then the diff of `instructions.md` is the review.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASELINE_COMMIT = "ee44cb3"

FIXTURE_DIR = Path(__file__).resolve().parent
REPO_ROOT = FIXTURE_DIR.parents[2]

# The three wall-clock stamps a Pass-2 run puts in its instruction document.
# Every one is minted at render time and says nothing about the pipeline's
# behaviour; nothing else is normalised, so a real change cannot hide behind a
# placeholder. Kept identical in the replaying test.
NORMALISERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^generated: .*$", re.MULTILINE), "generated: <NORMALISED>"),
    (re.compile(r"^  updated_at: '[^']*'$", re.MULTILINE), "  updated_at: '<NORMALISED>'"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}_\d{4}_"), "<STAMP>_"),
)


def normalise(document: str) -> str:
    for pattern, replacement in NORMALISERS:
        document = pattern.sub(replacement, document)
    return document


def run_pass2(scripts_dir: Path, out_dir: Path) -> str:
    """Parse the approved document, render the instruction set, return the .md.

    `scripts_dir` decides which pipeline runs — the scratch worktree's when
    recording, HEAD's when replaying — so this function is the single place
    that knows the chain's shape.
    """
    if str(FIXTURE_DIR) not in sys.path:
        sys.path.insert(0, str(FIXTURE_DIR))
    from fake_kado import FakeKado, load_notes  # noqa: PLC0415 — path set above

    out_dir.mkdir(parents=True, exist_ok=True)
    parsed_path = out_dir / "parsed-suggestions.json"
    proc = subprocess.run(
        [sys.executable, str(scripts_dir / "suggestion-parser.py"),
         "--file", str(FIXTURE_DIR / "suggestions.md"),
         "--suggestions-doc", str(FIXTURE_DIR / "suggestions-doc.json")],
        capture_output=True, text=True, check=True,
    )
    parsed_path.write_text(proc.stdout, encoding="utf-8")

    import importlib.util  # noqa: PLC0415

    spec = importlib.util.spec_from_file_location(
        "t6_2_instruction_render", scripts_dir / "instruction-render.py"
    )
    ir = importlib.util.module_from_spec(spec)
    sys.modules["t6_2_instruction_render"] = ir
    spec.loader.exec_module(ir)

    fake = FakeKado(load_notes(), ir.KadoError)
    ir.KadoClient = lambda: fake
    argv = sys.argv
    sys.argv = [
        "instruction-render.py",
        "--suggestions", str(parsed_path),
        "--output-dir", str(out_dir),
        "--config", str(FIXTURE_DIR / "vault-config.yaml"),
        "--shared-ctx", str(out_dir / "absent-shared-ctx.json"),
        "--tag-handler-groups-dir", str(out_dir / "absent-tag-handler-groups"),
        "--upstream-type", "suggestions",
        # Deliberately stamp-free, so every `<STAMP>` in the golden is one the
        # renderer minted rather than one the fixture handed it.
        "--upstream-path", "100 Inbox/t6-2-flat-suggestions.md",
        "--run-id", "t6-2-flat-pass2",
    ]
    try:
        rc = ir.main()
    finally:
        sys.argv = argv
    if rc != 0:
        raise SystemExit(f"instruction-render.main() returned {rc}")

    return (out_dir / "instructions.md").read_text(encoding="utf-8")


def _assert_whole_tree_is_the_baseline(scratch: Path) -> None:
    """Every `lib.*` the renderer pulled in must come from the scratch tree.

    This is the check `git show` extraction cannot make: a single helper
    resolved from HEAD would produce a mixed baseline with no visible symptom.
    """
    root = str(scratch.resolve())
    loaded = {
        name: str(Path(mod.__file__).resolve())
        for name, mod in sys.modules.items()
        if name.split(".")[0] == "lib" and getattr(mod, "__file__", None)
    }
    strays = sorted(n for n, f in loaded.items() if not f.startswith(root))
    if strays:
        raise SystemExit(f"modules resolved outside the baseline worktree: {strays}")
    if not loaded:
        raise SystemExit("no lib.* module was loaded at all — the chain did not run")
    print(f"  verified {len(loaded)} lib module(s) loaded from {root}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", default=BASELINE_COMMIT)
    args = ap.parse_args()

    scratch = Path(tempfile.mkdtemp(prefix="t6-2-baseline-"))
    worktree = scratch / "tree"
    subprocess.run(
        ["git", "-C", str(REPO_ROOT), "worktree", "add",
         "--detach", str(worktree), args.commit],
        check=True,
    )
    try:
        document = run_pass2(worktree / "tomo" / "scripts", scratch / "out")
        _assert_whole_tree_is_the_baseline(worktree)
    finally:
        subprocess.run(
            ["git", "-C", str(REPO_ROOT), "worktree", "remove", "--force", str(worktree)],
            check=False,
        )
        subprocess.run(["git", "-C", str(REPO_ROOT), "worktree", "prune"], check=False)
        # The rendered notes, manifest and parsed suggestions live under
        # `scratch/out`. `worktree remove` does not touch them, so a manual
        # re-run would leave a tree behind each time — from a script whose
        # whole job is to leave none.
        shutil.rmtree(scratch, ignore_errors=True)

    golden = FIXTURE_DIR / "instructions.md"
    golden.write_text(normalise(document), encoding="utf-8")
    print(f"recorded {golden} from {args.commit} "
          f"({len(document.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
