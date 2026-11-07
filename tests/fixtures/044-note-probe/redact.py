"""Redact a `claude plugin eval` trace into the 044-note-probe fixture.

Why this exists: `trace.jsonl` next to this file is the recorded probe run of the
/note eval case with every machine path replaced by a placeholder. This script is
the recipe, so a re-recorded probe is redacted the same way and the checked-in
fixture can be re-derived from its source.

Usage: python3 tests/fixtures/044-note-probe/redact.py <source-trace.jsonl> > trace.jsonl

The source is read as UTF-8 and written to stdout unchanged except for the
replacements in REPLACEMENTS, applied in order (more specific prefixes first).
Exit 1 when a LEAK_PATTERNS match survives the replacements, so a new kind of
path is noticed instead of being checked in.
"""

from __future__ import annotations

import re
import sys

EVAL_ROOT = r"/private/tmp/e-[A-Za-z0-9]+"
REPLACEMENTS: tuple[tuple[str, str], ...] = (
    # The eval workspace (the session's cwd).
    (EVAL_ROOT + r"/home/cwd", "<WS>"),
    # The eval's own temp dir (socket paths).
    (EVAL_ROOT + r"/tmp", "<EVAL-TMP>"),
    # The eval root as Claude Code slugs it into a project directory name.
    (r"-private-tmp-e-[A-Za-z0-9]+", "-EVAL"),
    # The eval root itself (config, memory paths).
    (EVAL_ROOT, "<EVAL>"),
    # The assembled plugin copy run-evals.sh builds under $TMPDIR.
    (r"/private/var/folders/[^/]+/[^/]+/T/tomo-evals\.[A-Za-z0-9]+/tomo", "<PLUGIN>"),
    # The Homebrew Python interpreter named in tracebacks.
    (r"/opt/homebrew/Cellar/python@[^/]+/[^/]+/Frameworks/Python\.framework/Versions/[^/]+"
     r"/Resources/Python\.app/Contents/MacOS/Python", "<PYTHON>"),
)
LEAK_PATTERNS = r"/private/|/var/folders/|/opt/|/Users/|/Volumes/|/tmp/e-|tomo-evals\."


def redact(text: str) -> str:
    for pattern, placeholder in REPLACEMENTS:
        text = re.sub(pattern, placeholder, text)
    return text


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: redact.py <source-trace.jsonl>", file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8", newline="") as fh:
        out = redact(fh.read())
    sys.stdout.write(out)
    leaks = sorted(set(re.findall(LEAK_PATTERNS, out)))
    if leaks:
        print(f"redact.py: unredacted path prefixes remain: {leaks}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
