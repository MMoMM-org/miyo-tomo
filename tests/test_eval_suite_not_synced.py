#!/usr/bin/env python3
# version: 0.1.0
"""test_eval_suite_not_synced.py — install-tomo.sh and update-tomo.sh never
deliver the top-level evals/ tree into an instance (spec 041, CON-2, F1-AC4).

The eval suite lives in <repo>/evals/, outside tomo/, so it must stay
invisible to both delivery scripts. Placement is proven, not assumed:
(a) statically, every copy source in both scripts is rooted under
$TOMO_SOURCE (or a short, named allowlist of non-tomo files); (b)
dynamically, a sentinel file planted in evals/ of a copied repo tree never
reaches an instance after update-tomo.sh runs.

Everything runs in tmp_path with HOME and the registry redirected there;
nothing touches the real repo, tomo-instance/, ~/.tomo or a real install.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

from test_update_tomo_sync_gaps import _make_minimal_instance

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = {
    "install-tomo.sh": REPO_ROOT / "scripts" / "install-tomo.sh",
    "update-tomo.sh": REPO_ROOT / "scripts" / "update-tomo.sh",
}

SENTINEL_REL = "evals/_lib/sentinel.txt"
SENTINEL_CONTENT = "EVAL-SUITE-SENTINEL-041-do-not-deliver"

# Source roots that resolve under tomo/ (REPO_ROOT/tomo).
TOMO_ROOTED = ("$TOMO_SOURCE/", "$PROFILES_DIR/", "$REPO_ROOT/tomo/")
# Named non-tomo sources the scripts legitimately read; evals/ is not one.
ALLOWED_OUTSIDE_TOMO = (
    "$REPO_ROOT/docker/entrypoint.sh",
    "$REPO_ROOT/scripts/lib/",
    "$SCRIPT_DIR/lib/",
    "$HOME/.claude/.credentials.json",
)
# Path variables that are copy destinations, never sources.
DEST_VARS = {"INSTANCE_PATH", "HOME_DIR", "dst", "INSTANCE_ROOT", "BACKUP_DIR"}
# Bare loop/helper variables: their roots are checked on the `for ... in` /
# `add_*` line that binds them, which this scan also covers. Recognised so
# they are not reported as unclassified.
DYNAMIC_VARS = {"f", "d", "src", "file", "name"}
# A `..` path segment can climb out of a tomo-rooted prefix into evals/.
TRAVERSAL = re.compile(r"(^|/)\.\.(/|$)")

COPY_LINE = re.compile(r"^\s*(cp|rsync|ditto|install|sed|for|add_\w+|python3)\b|\|\|\s*cp\b")
PATH_TOKEN = re.compile(r"""["']?(\$\{?[A-Za-z_]+\}?[^\s"'|;)]*)""")


def _logical_lines(text: str) -> list[tuple[int, str]]:
    """Join backslash continuations; skip comments and blank lines."""
    out: list[tuple[int, str]] = []
    buf, start = "", 0
    for no, raw in enumerate(text.splitlines(), 1):
        if not buf:
            start = no
        stripped = raw.rstrip()
        if stripped.endswith("\\"):
            buf += stripped[:-1] + " "
            continue
        buf += stripped
        if buf.strip() and not buf.lstrip().startswith("#"):
            out.append((start, buf))
        buf = ""
    return out


def _normalise(token: str) -> str:
    return re.sub(r"\$\{([A-Za-z_]+)\}", r"$\1", token)


class ScanResult(NamedTuple):
    violations: list[str]
    unclassified: list[str]
    rooted: int


def scan_copy_sources(text: str) -> ScanResult:
    """Classify path tokens on copy/loop/helper lines.

    A violation is a rooted source outside tomo/ and the allowlist, or any
    source with a `..` segment; unclassified is a `$VAR/...` token whose
    variable the scan does not know (so it cannot be silently skipped);
    rooted counts the tomo-rooted sources seen.
    """
    violations: list[str] = []
    unclassified: list[str] = []
    rooted = 0
    for no, line in _logical_lines(text):
        if not COPY_LINE.search(line):
            continue
        for m in PATH_TOKEN.finditer(line):
            tok = _normalise(m.group(1))
            var = re.search(r"[A-Za-z_]+", tok).group(0)
            if re.search(r"[:,]", tok):  # sed address pattern, not a path
                continue
            if "/" not in tok:
                continue
            if var in DEST_VARS:
                continue
            if TRAVERSAL.search(tok):
                violations.append(f"line {no}: {tok}")
                continue
            if tok.startswith(TOMO_ROOTED):
                rooted += 1
                continue
            if tok.startswith(ALLOWED_OUTSIDE_TOMO):
                continue
            if var in {"REPO_ROOT", "SCRIPT_DIR", "TOMO_SOURCE", "PROFILES_DIR", "HOME"}:
                violations.append(f"line {no}: {tok}")
            elif var not in DYNAMIC_VARS:
                unclassified.append(f"line {no}: {tok}")
    return ScanResult(violations, unclassified, rooted)


@pytest.mark.parametrize("script", sorted(SCRIPTS))
def test_copy_sources_are_rooted_under_tomo(script: str) -> None:
    text = SCRIPTS[script].read_text(encoding="utf-8")
    violations, unclassified, rooted = scan_copy_sources(text)
    assert not violations, f"{script}: copy source outside $TOMO_SOURCE: {violations}"
    assert not unclassified, f"{script}: copy path the scan cannot classify: {unclassified}"
    assert re.search(r"\bevals\b", text) is None, f"{script} mentions evals"
    # Guard against the scan matching nothing (a silently empty check).
    assert rooted >= 10, f"{script}: scan saw only {rooted} tomo-rooted sources"


@pytest.mark.parametrize(
    "bad_line",
    [
        'cp "$REPO_ROOT/evals/_lib/"*.py "$INSTANCE_PATH/scripts/"',
        'for f in "$REPO_ROOT/evals/"*.json; do',
        'add_bytewise "$REPO_ROOT/evals/x.json" "$HOME_DIR/x.json" "x" "evals"',
        'cp -R "$SCRIPT_DIR/../evals/." "$INSTANCE_PATH/evals/"',
        'cp -R "$TOMO_SOURCE/../evals/." "$INSTANCE_PATH/evals/"',
        'cp "$REPO_ROOT/tomo/../evals/x" "$INSTANCE_PATH/x"',
    ],
)
def test_scan_is_red_for_a_source_outside_tomo(bad_line: str) -> None:
    real = SCRIPTS["update-tomo.sh"].read_text(encoding="utf-8")
    violations, unclassified, _ = scan_copy_sources(real + "\n" + bad_line + "\n")
    assert violations or unclassified, f"scan accepted: {bad_line}"


def test_update_never_delivers_sentinel_from_evals(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    for sub in ("scripts", "tomo", "docker"):
        shutil.copytree(REPO_ROOT / sub, repo / sub, symlinks=True)
    sentinel = repo / SENTINEL_REL
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text(SENTINEL_CONTENT, encoding="utf-8")

    work = tmp_path / "work"
    instance_path, config_file = _make_minimal_instance(work, "inst")
    inst_root = instance_path.parent

    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["TOMO_REGISTRY_FILE"] = str(tmp_path / "instances.json")
    result = subprocess.run(
        ["bash", str(repo / "scripts" / "update-tomo.sh"), "--keep-voice", "--yes",
         "--config-file", str(config_file)],
        capture_output=True, text=True, env=env, timeout=120,
    )
    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    # The run really delivered something, so an empty tree cannot pass.
    assert (instance_path / ".claude" / "agents").is_dir()

    leaked = []
    for root in (inst_root, home):
        for p in root.rglob("*"):
            if p.is_file() and (
                p.name == sentinel.name
                or SENTINEL_CONTENT.encode() in p.read_bytes()
            ):
                leaked.append(str(p))
            if p.is_dir() and p.name == "evals":
                leaked.append(str(p))
    assert not leaked, f"evals/ content reached the instance: {leaked}"
