r"""grader_patterns.py — offline evaluator for `claude plugin eval` graders (spec 043).

Exists so every grader pattern can be checked against recorded traces before a paid
run (SDD ADR-5). Loads grader frontmatter from `evals/` (or any grader file), evaluates
`regex`, `tool_used` and `tool_order` graders against a JSONL trace, and checks that a regex stays
inside the subset Python `re` and the harness's JS RegExp share.
Shared by test_043_grader_patterns.py and the later 043 case tasks.

What it reproduces (semantics read from the `claude plugin eval` source in claude 2.1.314,
the Bun bundle's grader functions; the plugin-evals docs do not state them):
- `regex`: `new RegExp(pattern, flags)` (no flags here); `target: trace` is the whole JSONL
  text; `target: last_message` is the CLI's `lastAssistantText`: the text blocks of the LAST
  assistant event that has any, joined with "\n" ("" when there is none). Result frames are
  NOT read, and subagent events (parent_tool_use_id set) count like the main session's.
  `match: contains` passes on a match, `not_contains` on none, `count:N` on exactly N.
- `tool_used`: counts tool_use events named `tool` whose JSON-encoded input matches
  `input_match` (`RegExp.test`); passes when min <= count <= max (min defaults to 1).
- `tool_order`: the index of the FIRST tool_use matching `before` must be lower than the
  index of the FIRST tool_use matching `after` (`findIndex` on both); either side never
  called fails. Subagent calls are in the list in trace order. `before`/`after` is a tool
  name or `{tool, input_match}`. Outcome.count is 1 when both sides were found, else 0.

Assumptions to confirm at the first paid run (not settled by the source above):
- regexes run with JS semantics; JS `$` (end of input only, never before a trailing
  newline) is emulated by rewriting it to `\Z`; JS `.` is not emulated;
- tool input is JSON-encoded compactly (`separators=(",", ":")`) with `ensure_ascii=False`
  (the CLI stringifies the input object; key order is the model's emission order);
- the CLI's `trace` target joins the events with "\n" and no trailing newline; the
  fixtures end with one, which only matters to a `$` on `target: trace` (none uses one);
- `count:N` means exactly N non-overlapping matches (`count: N` with a space is accepted).

Known limits — differences between the engines `js_subset_violations` does not catch:
- character classes starting with `]`: `[]abc]` and `[^]]` are a literal `]` in Python
  but an empty / any-char class followed by `]` in JS;
- `\d`, `\w`, `\s`, `\b` are Unicode-aware in Python `re` (str), ASCII in JS without `u`
  (JS `\s` is Unicode in both);
- `.` excludes only `\n` in Python, but also `\r`, U+2028 and U+2029 in JS.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from eval_kit import EVALS, REPO

SPEC_DIR = REPO / "docs" / "XDD" / "specs" / "043-pass1-conductor-eval-gate"
FIXTURES_DIR = SPEC_DIR / "fixtures"

GRADER_TYPES = {"regex", "tool_used", "tool_order"}

# Lookbehinds the 041 graders already ship (all fixed-width, valid in both engines).
ALLOWED_LOOKBEHINDS = (r"(?<=\\n)", r"(?<![\w-])", r"(?<!\\)")


@dataclass(frozen=True)
class Grader:
    type: str
    target: str | None = None
    pattern: str | None = None
    match: str = "contains"
    tool: str | None = None
    input_match: str | None = None
    min: int | None = None
    max: int | None = None
    before: dict | None = None
    after: dict | None = None
    source: Path | None = None
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Expect:
    passed: bool
    count: int
    why: str = ""


@dataclass(frozen=True)
class Outcome:
    passed: bool
    count: int


@dataclass(frozen=True)
class ToolUse:
    line: int  # trace line index
    name: str
    input_json: str
    parent: str | None


def parse_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError("unterminated frontmatter")
    data = yaml.safe_load(text[4:end]) or {}
    if not isinstance(data, dict):
        raise ValueError("frontmatter is not a mapping")
    return data


def _grader(data: dict[str, Any], source: Path | None) -> Grader:
    known = set(Grader.__dataclass_fields__) - {"source", "extra"}
    kwargs = {k: v for k, v in data.items() if k in known}
    extra = {k: v for k, v in data.items() if k not in known}
    if "match" in kwargs and kwargs["match"] is None:
        del kwargs["match"]
    return Grader(source=source, extra=extra, **kwargs)


def load_grader(path: Path) -> Grader:
    data = parse_frontmatter(Path(path).read_text(encoding="utf-8"))
    if data.get("type") not in GRADER_TYPES:
        raise ValueError(f"{path}: not a grader (type={data.get('type')!r})")
    return _grader(data, Path(path))


def from_file(path: Path | str) -> Grader:
    """A table entry backed by a grader file (relative paths resolve from the repo root)."""
    path = Path(path)
    return load_grader(path if path.is_absolute() else REPO / path)


def inline(**frontmatter: Any) -> Grader:
    """A table entry for a pattern whose grader file does not exist yet."""
    return _grader(frontmatter, None)


def grader_files() -> list[Path]:
    """Every grader file in evals/: case graders plus the shared ones in evals/_lib/."""
    candidates = sorted(EVALS.glob("*/graders/*.md")) + sorted(
        (EVALS / "_lib").glob("*.md")
    )
    return [
        p
        for p in candidates
        if parse_frontmatter(p.read_text(encoding="utf-8")).get("type") in GRADER_TYPES
    ]


def grader_regexes(grader: Grader) -> list[str]:
    found = [grader.pattern, grader.input_match]
    for side in (grader.before, grader.after):
        if isinstance(side, dict):
            found.append(side.get("input_match"))
    return [r for r in found if r is not None]


def load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def tool_uses(trace: str) -> list[ToolUse]:
    uses = []
    for number, line in enumerate(trace.splitlines()):
        event = json.loads(line)
        content = (event.get("message") or {}).get("content")
        if event.get("type") != "assistant" or not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "tool_use":
                encoded = json.dumps(
                    block.get("input"), ensure_ascii=False, separators=(",", ":")
                )
                uses.append(
                    ToolUse(
                        number, block["name"], encoded, event.get("parent_tool_use_id")
                    )
                )
    return uses


def last_message(trace: str) -> str:
    """The CLI's `lastAssistantText`: the last assistant event with text blocks."""
    last = ""
    for line in trace.splitlines():
        event = json.loads(line)
        content = (event.get("message") or {}).get("content")
        if event.get("type") != "assistant" or not isinstance(content, list):
            continue
        texts = [str(b.get("text") or "") for b in content if b.get("type") == "text"]
        if texts:
            last = "\n".join(texts)
    return last


def js_anchors(pattern: str) -> str:
    """Rewrite each unescaped `$` outside a character class to `\\Z` (JS `$`, no flags).

    Classes are delimited the Python way (a leading `]` is a literal), see Known limits."""
    out, i, n, in_class = [], 0, len(pattern), False
    while i < n:
        c = pattern[i]
        if c == "\\":
            out.append(pattern[i : i + 2])
            i += 2
            continue
        if in_class:
            if c == "]":
                in_class = False
        elif c == "[":
            in_class = True
            out.append(c)
            i += 1
            if pattern[i : i + 1] == "^":
                out.append("^")
                i += 1
            if pattern[i : i + 1] == "]":
                out.append("]")
                i += 1
            continue
        elif c == "$":
            out.append(r"\Z")
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _count_matches(pattern: str, text: str) -> int:
    return sum(1 for _ in re.finditer(js_anchors(pattern), text))


def _apply_match(mode: str, count: int) -> bool:
    if mode == "contains":
        return count > 0
    if mode == "not_contains":
        return count == 0
    wanted = re.fullmatch(r"count:\s*(\d+)", mode)
    if wanted:
        return count == int(wanted.group(1))
    raise ValueError(f"unknown match mode {mode!r}")


def _side(side: str | dict) -> dict:
    return {"tool": side, "input_match": None} if isinstance(side, str) else side


def _matches(use: ToolUse, side: dict) -> bool:
    if use.name != side["tool"]:
        return False
    pattern = side.get("input_match")
    return not pattern or re.search(js_anchors(pattern), use.input_json) is not None


def _first_index(uses: list[ToolUse], side: dict) -> int:
    return next((i for i, use in enumerate(uses) if _matches(use, side)), -1)


def evaluate(grader: Grader, trace: str) -> Outcome:
    if grader.type == "regex":
        target = grader.target or "last_message"
        if target == "trace":
            text = trace
        elif target == "last_message":
            text = last_message(trace)
        else:
            raise ValueError(f"unknown target {target!r}")
        count = _count_matches(grader.pattern, text)
        return Outcome(_apply_match(grader.match, count), count)
    if grader.type == "tool_used":
        side = {"tool": grader.tool, "input_match": grader.input_match}
        count = sum(1 for use in tool_uses(trace) if _matches(use, side))
        low = 1 if grader.min is None else grader.min
        high = grader.max
        return Outcome(count >= low and (high is None or count <= high), count)
    if grader.type == "tool_order":
        uses = tool_uses(trace)
        before = _first_index(uses, _side(grader.before))
        after = _first_index(uses, _side(grader.after))
        if before < 0 or after < 0:
            return Outcome(False, 0)
        return Outcome(before < after, 1)
    raise ValueError(f"unknown grader type {grader.type!r}")


def js_subset_violations(pattern: str) -> list[str]:
    """Constructs outside the subset Python `re` and JS RegExp (no flags) share."""
    violations = []
    i, n, in_class = 0, len(pattern), False
    while i < n:
        c = pattern[i]
        if c == "\\":
            escaped = pattern[i + 1 : i + 2]
            if not in_class and escaped in ("A", "Z", "z"):
                violations.append(f"\\{escaped} (Python-only anchor)")
            i += 2
            continue
        if in_class:
            if c == "]":
                in_class = False
            i += 1
            continue
        if c == "[":
            in_class = True
            i += 1
            continue
        if pattern.startswith("(?", i):
            rest = pattern[i:]
            if rest.startswith(("(?<=", "(?<!")):
                if not rest.startswith(ALLOWED_LOOKBEHINDS):
                    violations.append(f"lookbehind beyond 041's set at {i}")
            elif rest.startswith("(?>"):
                violations.append(f"atomic group at {i}")
            elif rest.startswith("(?P"):
                violations.append(f"Python named-group syntax at {i}")
            elif re.match(r"\(\?[aiLmsux-]+[:)]", rest):
                violations.append(f"inline flags at {i}")
            i += 2
            continue
        quantifier_end = None
        if c in "*+?":
            quantifier_end = i
        elif c == "{":
            brace = re.match(r"\{\d+(?:,\d*)?\}", pattern[i:])
            if brace:
                quantifier_end = i + brace.end() - 1
        if quantifier_end is not None:
            following = pattern[quantifier_end + 1 : quantifier_end + 2]
            if following == "+":
                violations.append(f"possessive quantifier at {i}")
            i = quantifier_end + 1
            if following == "?":
                i += 1
            continue
        i += 1
    return violations
