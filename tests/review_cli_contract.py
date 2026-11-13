#!/usr/bin/env python3
# version: 0.1.0
"""review_cli_contract.py — the CLI contract of the /review scripts, read from their own argparse parsers.

Spec 045 T5.1 / T5.2. Shared by tests/test_review_why_docs.py (the WHY documents under
docs/tomo/dot_claude/) and tests/test_review_skill.py (the runtime skill and every other
SKILL.md that names a review script), so the two sweeps read one contract and cannot drift
apart. Lives in tests/, not tomo/scripts/lib/: never a production code path. Not named
`test_*`, so pytest does not collect it.

The contract is never typed by hand: `build_parsers()` imports every review script and
`vault-config-writer.py` under a unique module name and calls their `build_parser()`. The
scripts insert their own directory into sys.path (they import `lib.*`), so this module
does not.

Two ways a document names the contract:
- a contract mention — a backtick span without values, as the WHY documents write it:
  `review-doc.py write --stem --proposals`, `review-read.py --period --kind`;
- a call — `python3 scripts/review-doc.py write --stem <stem> …`, as the runtime skill
  writes it, parsed with the called script's own parser after placeholders are filled.

`stray_review_names()` is the sanity net under both: every occurrence of a review script
name must be one of the two forms, so a wrapped or odd mention cannot slip past the sweep.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import shlex
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO / "tomo" / "scripts"
SKILLS_DIR = REPO / "tomo" / "dot_claude" / "skills"

REVIEW_SCRIPTS = ("review-session.py", "review-doc.py", "review-instructions.py", "review-read.py")
WRITER_SCRIPT = "vault-config-writer.py"
PARSER_SCRIPTS = REVIEW_SCRIPTS + (WRITER_SCRIPT,)

SCRIPT_NAME = re.compile(r"review-(?:session|doc|instructions|read)\.py")
# `review-doc.py write --stem --proposals`: the script name is part of the mention so a bare `write`
# in prose is never read as a CLI reference.
SUB_MENTION = re.compile(r"`(review-(?:session|doc|instructions)\.py) ([a-z][a-z-]*)((?: --[a-z][a-z-]*)*)`")
# `review-read.py --period --kind`: no subcommand, flags only.
READ_MENTION = re.compile(r"`(review-read\.py)((?: --[a-z][a-z-]*)*)`")
WRITER_MENTION = re.compile(r"`(vault-config-writer\.py) (review)((?: --[a-z][a-z-]*)*)`")
# `python3 scripts/review-doc.py write --stem <stem> …` up to the end of the line or the closing backtick.
CALL = re.compile(r"python3 scripts/([\w-]+\.py)([^`\n]*)")
BACKTICK_SPAN = re.compile(r"`[^`\n]+`")


def load_script(script: str):
    """Import one tomo/scripts/<script> under a unique module name (`review_cli_contract_<name>`)."""
    name = "review_cli_contract_" + script.removesuffix(".py").replace("-", "_")
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / script)
    assert spec is not None and spec.loader is not None, script
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def build_parsers() -> dict[str, argparse.ArgumentParser]:
    return {script: load_script(script).build_parser() for script in PARSER_SCRIPTS}


def subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def flags(parser: argparse.ArgumentParser) -> set[str]:
    return {opt for action in parser._actions for opt in action.option_strings}


def required_flags(parser: argparse.ArgumentParser) -> set[str]:
    return {opt for action in parser._actions if action.required for opt in action.option_strings}


def review_subcommands(parsers: dict[str, argparse.ArgumentParser]) -> dict[str, dict[str, argparse.ArgumentParser]]:
    """script -> {subcommand -> its parser}, for the review scripts that have subcommands."""
    found = {script: subparsers(parsers[script]) for script in REVIEW_SCRIPTS}
    return {script: subs for script, subs in found.items() if subs}


# ── contract mentions (WHY documents) ───────────────────────────────────────


def sub_mentions(doc: str) -> list[tuple[str, str, list[str]]]:
    """Every `<script> <sub> [--flags]` mention: (script, subcommand, flags)."""
    return [(script, sub, rest.split()) for script, sub, rest in SUB_MENTION.findall(doc)]


def read_mentions(doc: str) -> list[list[str]]:
    """The flags of every `review-read.py [--flags]` mention, one list per mention."""
    return [rest.split() for _script, rest in READ_MENTION.findall(doc)]


def writer_mentions(doc: str) -> list[list[str]]:
    """The flags of every `vault-config-writer.py review [--flags]` mention."""
    return [rest.split() for _script, _sub, rest in WRITER_MENTION.findall(doc)]


def unmatched_review_spans(doc: str) -> list[str]:
    """Backtick spans that name a review script but are neither a contract mention nor a call."""
    return [
        span for span in BACKTICK_SPAN.findall(doc)
        if SCRIPT_NAME.search(span)
        and not SUB_MENTION.fullmatch(span)
        and not READ_MENTION.fullmatch(span)
        and not span.startswith("`python3 scripts/")
    ]


# ── calls (runtime skills) ──────────────────────────────────────────────────


def skill_files() -> list[Path]:
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def calls(text: str) -> list[tuple[str, str]]:
    """Every `python3 scripts/<script> <rest>` call in the text: (script, rest)."""
    return [(m.group(1), m.group(2).strip()) for m in CALL.finditer(text)]


def review_calls(text: str) -> list[tuple[str, str]]:
    return [(script, rest) for script, rest in calls(text) if script in PARSER_SCRIPTS]


def stray_review_names(text: str) -> list[str]:
    """Lines where a review script name is neither a call nor a contract mention (after both are removed)."""
    stripped = CALL.sub("", text)
    stripped = SUB_MENTION.sub("", stripped)
    stripped = READ_MENTION.sub("", stripped)
    return [line.strip() for line in stripped.splitlines() if SCRIPT_NAME.search(line)]


def placeholder(match: re.Match) -> str:
    """A value that the parser accepts for one `<…>` placeholder of a call."""
    name = match.group(0).strip("<>").lower()
    if "stem" in name:
        return "2026-W13_review"
    if "period" in name:
        return "2026-W13"
    if "kind" in name:
        return "week"
    if "day" in name:
        return "monday"
    if name in ("n", "min", "min_days", "min-days"):
        return "4"
    if "path" in name or "file" in name:
        return "tomo-tmp/review/x.json"
    if "request" in name or "args" in name:
        return "W13"
    return "X"


def parse_call(script: str, rest: str) -> None:
    """Parse one call with the script's own parser; prefix abbreviations refused. Raises SystemExit on refusal."""
    argv = shlex.split(re.sub(r"<[^>]+>", placeholder, rest))
    parser = load_script(script).build_parser()
    original = argparse.ArgumentParser._get_option_tuples
    argparse.ArgumentParser._get_option_tuples = lambda self, option: []  # type: ignore[method-assign]
    try:
        parser.parse_args(argv)
    finally:
        argparse.ArgumentParser._get_option_tuples = original  # type: ignore[method-assign]
