# version: 0.1.0
"""template_syntax.py — the one reading of a note template and a filled note.

/note lists a template's points and later checks the filled note before it is
delivered. Both sides call this module, so a token the outline offers as a point
is the same token the check fails on when it is left over. The hyphenated
scripts (template-outline.py, template-doctor.py, note-*.py) cannot import each
other, which is why the shared parser lives in lib/. Pure functions over text,
no IO. See docs/tomo/scripts/lib/template_syntax.md for the WHY.

Lines are 1-based. A token is ``{{name}}`` matching TOKEN_RE outside fenced code,
outside a Templater span and without a leading backslash. A Templater span is
``<% ... %>`` in any variant (``<%*``, ``<%-``) and is listed, never a point.
"""
from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field

# Copy of token-render.py's _TOKEN_RE; tests/test_template_syntax.py pins parity.
TOKEN_RE = re.compile(r"\\?\{\{([a-z_][a-z0-9_]*)\}\}")
TEMPLATER_RE = re.compile(r"<%.*?%>", re.DOTALL)

GENERATED_TOKENS = frozenset({"uuid", "datestamp", "updated", "date_iso"})
CONFIG_TOKENS = frozenset({"locale", "vault", "vault_version", "profile"})
SOURCE_TOKENS = frozenset({"source_path", "source_link"})

_FENCE_MARKERS = ("```", "~~~")
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
_KEY_RE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_ .-]*?)\s*:(.*)$")
_TOMO_KEY_RE = re.compile(r"^tomo\s*:")


@dataclass(frozen=True)
class LeadingBlock:
    """The leading ``---`` block: status ok | unclosed | missing."""

    status: str
    lines: list = field(default_factory=list)
    start_line: int | None = None
    end_line: int | None = None


@dataclass(frozen=True)
class FilledNoteResult:
    """Verdict of filled_note_check: ok is False when any finding FAILs."""

    ok: bool
    findings: list


# ──────────────────────────────────────────────────────────────────────
# Shared scanning helpers
# ──────────────────────────────────────────────────────────────────────

def _split(text: str) -> list[str]:
    return [ln.rstrip("\r") for ln in text.split("\n")]


def _fence_line_indexes(lines: list[str]) -> set[int]:
    """Return 0-based indexes of fence marker lines and the lines between them."""
    inside: set[int] = set()
    marker = ""
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        opens = stripped[:3] if stripped[:3] in _FENCE_MARKERS else ""
        if marker or opens:
            inside.add(i)
        if marker and stripped.startswith(marker):
            marker = ""
        elif not marker and opens:
            marker = opens
    return inside


def _line_starts(text: str) -> list[int]:
    starts = [0]
    starts.extend(m.end() for m in re.finditer("\n", text))
    return starts


def _line_of(offset: int, starts: list[int]) -> int:
    return bisect.bisect_right(starts, offset)


# ──────────────────────────────────────────────────────────────────────
# Leading block and frontmatter keys
# ──────────────────────────────────────────────────────────────────────

def leading_block(text: str) -> LeadingBlock:
    """Find the leading ``---`` block; line 1 must be a literal fence."""
    lines = _split(text)
    if lines[0].strip() != "---":
        return LeadingBlock(status="missing")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return LeadingBlock("ok", lines[1:i], 1, i + 1)
    return LeadingBlock("unclosed", [], 1, None)


def frontmatter_ok(text: str) -> bool:
    """True when the text opens with a closed ``---`` block."""
    return leading_block(text).status == "ok"


def frontmatter_keys(text: str) -> list[dict]:
    """List top-level frontmatter keys as {key, has_value, line}."""
    block = leading_block(text)
    if block.status != "ok":
        return []
    keys = []
    for i, line in enumerate(block.lines):
        match = _KEY_RE.match(line)
        if not match:
            continue
        has_value = bool(match.group(2).strip()) or _has_nested_value(block.lines, i)
        keys.append({"key": match.group(1), "has_value": has_value, "line": i + 2})
    return keys


def _has_nested_value(block_lines: list[str], index: int) -> bool:
    """True when indented content follows the key before the next top-level line."""
    for line in block_lines[index + 1:]:
        if not line.strip():
            continue
        return line[:1] in (" ", "\t")
    return False


# ──────────────────────────────────────────────────────────────────────
# Tokens and Templater spans
# ──────────────────────────────────────────────────────────────────────

def prefilled_tokens(has_source: bool = False) -> frozenset:
    """Tokens the script resolves itself; source tokens only with an inbox source."""
    prefilled = GENERATED_TOKENS | CONFIG_TOKENS
    return prefilled | SOURCE_TOKENS if has_source else prefilled


def tokens(text: str, has_source: bool = False) -> list[dict]:
    """List tokens as {name, line, prefilled} in document order."""
    fenced = _fence_line_indexes(_split(text))
    starts = _line_starts(text)
    spans = [m.span() for m in TEMPLATER_RE.finditer(text)]
    prefilled = prefilled_tokens(has_source)
    found = []
    for match in TOKEN_RE.finditer(text):
        line = _line_of(match.start(), starts)
        if match.group(0).startswith("\\") or line - 1 in fenced:
            continue
        if any(start <= match.start() < end for start, end in spans):
            continue
        name = match.group(1)
        found.append({"name": name, "line": line, "prefilled": name in prefilled})
    return found


def templater_spans(text: str) -> list[dict]:
    """List every Templater span as {line, text}, fenced or not."""
    starts = _line_starts(text)
    return [
        {"line": _line_of(m.start(), starts), "text": m.group(0)}
        for m in TEMPLATER_RE.finditer(text)
    ]


def _templater_inner_line_indexes(text: str) -> set[int]:
    """0-based indexes of lines that begin inside a multi-line Templater span."""
    inner: set[int] = set()
    for span in templater_spans(text):
        first = span["line"]
        last = first + span["text"].count("\n")
        inner.update(range(first, last))
    return inner


# ──────────────────────────────────────────────────────────────────────
# Headings
# ──────────────────────────────────────────────────────────────────────

def headings(text: str) -> list[dict]:
    """List ATX headings as {level, text, line, has_body} outside frontmatter and code."""
    lines = _split(text)
    skipped = _fence_line_indexes(lines) | _templater_inner_line_indexes(text)
    block = leading_block(text)
    if block.status == "ok":
        skipped.update(range(block.end_line))
    found = []
    for i, line in enumerate(lines):
        match = None if i in skipped else _HEADING_RE.match(line)
        if match:
            found.append({"level": len(match.group(1)), "text": match.group(2), "line": i + 1})
    return [_with_body(h, nxt, lines) for h, nxt in zip(found, found[1:] + [None])]


def _with_body(heading: dict, following: dict | None, lines: list[str]) -> dict:
    """Mark whether any non-blank line sits between a heading and the next one."""
    end = following["line"] - 1 if following else len(lines)
    body = lines[heading["line"]:end]
    return {**heading, "has_body": any(ln.strip() for ln in body)}


# ──────────────────────────────────────────────────────────────────────
# Filled-note checks
# ──────────────────────────────────────────────────────────────────────

def _finding(check: str, status: str, detail: str, fix: str | None = None) -> dict:
    return {"check": check, "status": status, "detail": detail, "fix": fix}


def _fence_findings(block: LeadingBlock) -> list[dict]:
    if block.status == "missing":
        return [_finding(
            "leading_fence", "FAIL", "The note does not open with a `---` fence.",
            "Start the note with a `---` frontmatter block.")]
    findings = [_finding("leading_fence", "PASS", "The note opens with a `---` fence.")]
    if block.status == "unclosed":
        return findings + [_finding(
            "frontmatter_closed", "FAIL", "The opening `---` fence is never closed.",
            "Add a closing `---` line after the frontmatter keys.")]
    return findings + [_finding("frontmatter_closed", "PASS", "The frontmatter block is closed.")]


def _tomo_key_findings(block: LeadingBlock) -> list[dict]:
    if block.status != "ok":
        return []
    if any(_TOMO_KEY_RE.match(line) for line in block.lines):
        return [_finding(
            "no_user_tomo_key", "FAIL", "The frontmatter carries a top-level `tomo:` key.",
            "Remove it; Tomo stamps its own `tomo:` block.")]
    return [_finding("no_user_tomo_key", "PASS", "No user-authored `tomo:` key.")]


def _templater_finding(text: str) -> dict:
    if "<%" in text:
        return _finding(
            "no_templater", "FAIL", "Templater syntax `<%` is left in the note.",
            "Replace each `<% ... %>` with its final text; Tomo never runs Templater.")
    return _finding("no_templater", "PASS", "No Templater syntax is left.")


def _token_finding(text: str) -> dict:
    left = sorted({t["name"] for t in tokens(text)})
    if left:
        names = ", ".join("{{" + name + "}}" for name in left)
        return _finding(
            "no_tokens", "FAIL", f"Token(s) left outside fenced code: {names}.",
            "Fill each token with its value or remove it.")
    return _finding("no_tokens", "PASS", "No `{{token}}` is left outside fenced code.")


def filled_note_check(text: str) -> FilledNoteResult:
    """Check a filled note: closed leading fence, no tomo: key, no <%, no {{token}}."""
    block = leading_block(text)
    findings = _fence_findings(block) + _tomo_key_findings(block)
    findings += [_templater_finding(text), _token_finding(text)]
    ok = all(f["status"] != "FAIL" for f in findings)
    return FilledNoteResult(ok=ok, findings=findings)
