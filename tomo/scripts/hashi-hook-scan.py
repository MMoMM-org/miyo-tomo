#!/usr/bin/env python3
# version: 0.1.0
"""hashi-hook-scan.py — Classify the risk tier of a generated Hashi hook.

Hashi runs user-authored `.cjs` hooks with full plugin privilege and NO sandbox
(`Hashi/docs/hooks.md`: "same as Templater") — child_process, node:fs, network,
process.env are all reachable. The hashi-hook-author skill generates such hooks,
so before any generated hook reaches the user's inbox it is classified here and
the skill branches on the result (green: proceed, yellow/mass-change: warn,
red: require explicit confirmation + recommend against).

Classification is a deterministic, regex-based HEURISTIC — a tripwire, not a
security boundary. Obfuscated or novel exfiltration will slip past it; that gap
is owned by the user-facing disclaimer (review + liability rest with the user),
NOT by this script. Keeping the judgment deterministic (rather than asking the
LLM "is this safe?") is the point: the classification cannot drift between runs.

Tiers:
  green  — only Obsidian API (`ctx.app.*`); no node builtins, no vault-wide loop
  yellow — filesystem reads, process.env, or other non-network builtins (os/crypto/…)
  red    — child_process, network, filesystem writes, eval/Function/vm, dynamic require

`mass_change` is an orthogonal flag (can co-occur with a GREEN tier): a mutation
method used together with a vault-wide enumeration can rewrite thousands of notes
even via the blessed Obsidian API.

Usage:
  python3 scripts/hashi-hook-scan.py --file path/to/before-move_note.cjs
  cat hook.cjs | python3 scripts/hashi-hook-scan.py

Output: JSON {tier, mass_change, findings:[{severity,category,line,snippet}]} on stdout.

Exit codes:
  0 — green, scan succeeded
  0 — yellow/red also exit 0 (tier is in the JSON; this is a classifier, not a gate)
  2 — I/O or argument error
"""
from __future__ import annotations

import argparse
import json
import re
import sys


def _strip_comments(source: str) -> str:
    """Blank out `//` line and `/* */` block comments while preserving line count.

    String literals are intentionally NOT stripped: a dangerous token hidden in a
    string is rare, and erring toward a false-positive RED is the safe direction
    for a tripwire.
    """
    # Block comments — replace with same number of newlines to keep line numbers.
    def _blank_block(m: re.Match) -> str:
        return "\n" * m.group(0).count("\n")

    source = re.sub(r"/\*.*?\*/", _blank_block, source, flags=re.DOTALL)
    # Line comments — drop from `//` to end of line.
    source = re.sub(r"//[^\n]*", "", source)
    return source


# Each rule: (severity, category, compiled pattern). First-match-per-category.
_RED_RULES = [
    ("red", "child_process",
     re.compile(r"require\(\s*['\"](?:node:)?child_process['\"]")),
    ("red", "shell-exec",
     re.compile(r"\b(?:execSync|execFileSync|spawnSync)\s*\(")),
    ("red", "network-require",
     re.compile(r"require\(\s*['\"](?:node:)?(?:https?|net|dns|dgram|tls|http2)['\"]")),
    ("red", "network-fetch",
     re.compile(r"\b(?:fetch|requestUrl|request)\s*\(|\bXMLHttpRequest\b|\bWebSocket\b")),
    ("red", "code-eval",
     re.compile(r"\beval\s*\(|\bnew\s+Function\s*\(|require\(\s*['\"](?:node:)?vm['\"]")),
    ("red", "dynamic-require",
     re.compile(r"require\(\s*(?!['\"])")),
]

# Filesystem write methods (any of these + an fs require ⇒ red).
_FS_WRITE = re.compile(
    r"\b(?:writeFile|writeFileSync|appendFile|appendFileSync|unlink|unlinkSync|"
    r"rmSync|rmdir|rmdirSync|mkdir|mkdirSync|truncate|truncateSync|"
    r"createWriteStream|copyFile|copyFileSync|rename|renameSync)\s*\("
)
_FS_REQUIRE = re.compile(r"require\(\s*['\"](?:node:)?fs(?:/promises)?['\"]")

# Yellow built-ins (non-network, non-fs): os, crypto, zlib, stream, etc.
_YELLOW_REQUIRE = re.compile(
    r"require\(\s*['\"](?:node:)?(?:os|crypto|zlib|stream|worker_threads|cluster)['\"]"
)
_PROCESS_ENV = re.compile(r"\bprocess\.env\b")

# Mass-change heuristic: vault-wide enumeration + a mutation method anywhere.
_ENUMERATE = re.compile(
    r"\.(?:getMarkdownFiles|getAllLoadedFiles|getFiles|getAllFolders)\s*\("
)
_MUTATE = re.compile(
    r"\b(?:processFrontMatter|fileManager\.processFrontMatter)\b|"
    r"\.(?:modify|process|rename|delete|trash|create|createFolder)\s*\("
)


def _line_of(source: str, index: int) -> int:
    return source.count("\n", 0, index) + 1


def _snippet(source: str, index: int) -> str:
    start = source.rfind("\n", 0, index) + 1
    end = source.find("\n", index)
    if end == -1:
        end = len(source)
    return source[start:end].strip()[:120]


def scan(source: str) -> dict:
    """Classify a hook's source. Returns {tier, mass_change, findings}."""
    code = _strip_comments(source)
    findings: list[dict] = []

    def _record(severity: str, category: str, m: re.Match) -> None:
        findings.append({
            "severity": severity,
            "category": category,
            "line": _line_of(code, m.start()),
            "snippet": _snippet(code, m.start()),
        })

    for severity, category, pattern in _RED_RULES:
        m = pattern.search(code)
        if m:
            _record(severity, category, m)

    # Filesystem: write ⇒ red, read-only fs require ⇒ yellow.
    fs_required = _FS_REQUIRE.search(code)
    fs_write = _FS_WRITE.search(code)
    if fs_required:
        if fs_write:
            _record("red", "fs-write", fs_write)
        else:
            _record("yellow", "fs-read", fs_required)
    elif fs_write and re.search(r"\bfs\.", code):
        # fs.* write without an explicit require (destructured/aliased elsewhere).
        _record("red", "fs-write", fs_write)

    m = _YELLOW_REQUIRE.search(code)
    if m:
        _record("yellow", "builtin-module", m)

    m = _PROCESS_ENV.search(code)
    if m:
        _record("yellow", "process-env", m)

    severities = {f["severity"] for f in findings}
    if "red" in severities:
        tier = "red"
    elif "yellow" in severities:
        tier = "yellow"
    else:
        tier = "green"

    mass_change = bool(_ENUMERATE.search(code) and _MUTATE.search(code))

    return {"tier": tier, "mass_change": mass_change, "findings": findings}


def main() -> int:
    p = argparse.ArgumentParser(
        description="Classify the risk tier of a generated Hashi hook (.cjs)."
    )
    p.add_argument(
        "--file",
        help="Path to the hook source. If omitted, source is read from stdin.",
    )
    args = p.parse_args()

    try:
        if args.file:
            with open(args.file, "r", encoding="utf-8") as fh:
                source = fh.read()
        else:
            source = sys.stdin.read()
    except OSError as e:
        print(f"hashi-hook-scan: cannot read input: {e}", file=sys.stderr)
        return 2

    print(json.dumps(scan(source), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
