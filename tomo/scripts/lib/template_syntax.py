# version: 0.1.4
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

resolve_tokens() replaces the named tokens tokens() reports, in place;
resolve_prefilled() uses it for every prefilled token except DEFERRED_TOKENS.
generated_values() and config_values() copy token-render.py's value rules
(pinned by parity tests). source_link_value() is the {{source_link}} value
note-instructions.py stage writes into draft.md.
"""
from __future__ import annotations

import bisect
import posixpath
import re
from dataclasses import dataclass, field

# Copy of token-render.py's _TOKEN_RE; tests/test_template_syntax.py pins parity.
TOKEN_RE = re.compile(r"\\?\{\{([a-z_][a-z0-9_]*)\}\}")
TEMPLATER_RE = re.compile(r"<%.*?%>", re.DOTALL)

GENERATED_TOKENS = frozenset({"uuid", "datestamp", "updated", "date_iso"})
CONFIG_TOKENS = frozenset({"locale", "vault", "vault_version", "profile"})
SOURCE_TOKENS = frozenset({"source_path", "source_link"})
# Prefilled, but resolved by note-instructions.py stage (needs keep_source).
DEFERRED_TOKENS = frozenset({"source_link"})

_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
_KEY_RE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_ .-]*?)\s*:(.*)$")
_TOMO_KEY_RE = re.compile(r"^tomo\s*:")
_COLUMN0_ITEM_RE = re.compile(r"^-(?:[ \t]|$)")


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


def _fence_opener(line: str) -> str:
    """Return the opening run (``` or ~~~, 3+) of a fence line, else ""."""
    match = _FENCE_RE.match(line)
    if not match:
        return ""
    run, info = match.groups()
    return "" if run[0] == "`" and "`" in info else run


def _closes(line: str, opener: str) -> bool:
    """A closer repeats the opener's char at least as often, with nothing after."""
    match = _FENCE_RE.match(line)
    if not match or match.group(2).strip():
        return False
    run = match.group(1)
    return run[0] == opener[0] and len(run) >= len(opener)


def _scan_fences(lines: list[str]) -> tuple[set[int], int | None]:
    """Return fenced 0-based line indexes and the 1-based line of a fence left open."""
    inside: set[int] = set()
    opener, opened_at = "", None
    for i, line in enumerate(lines):
        if opener:
            inside.add(i)
            opener = "" if _closes(line, opener) else opener
        elif opens := _fence_opener(line):
            inside.add(i)
            opener, opened_at = opens, i + 1
    return inside, (opened_at if opener else None)


def _fence_line_indexes(lines: list[str]) -> set[int]:
    """Return 0-based indexes of fence marker lines and the lines between them."""
    return _scan_fences(lines)[0]


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
    """True when indented content or a column-0 ``- `` list item follows the key."""
    for line in block_lines[index + 1:]:
        if not line.strip():
            continue
        return line[:1] in (" ", "\t") or _COLUMN0_ITEM_RE.match(line) is not None
    return False


# ──────────────────────────────────────────────────────────────────────
# Tokens and Templater spans
# ──────────────────────────────────────────────────────────────────────

def prefilled_tokens(has_source: bool = False) -> frozenset:
    """Tokens the script resolves itself; source tokens only with an inbox source."""
    prefilled = GENERATED_TOKENS | CONFIG_TOKENS
    return prefilled | SOURCE_TOKENS if has_source else prefilled


def _token_matches(text: str) -> list[tuple[re.Match, int]]:
    """Return (match, line) for each token outside fences, escapes and Templater."""
    fenced = _fence_line_indexes(_split(text))
    starts = _line_starts(text)
    spans = [m.span() for m in TEMPLATER_RE.finditer(text)]
    found = []
    for match in TOKEN_RE.finditer(text):
        line = _line_of(match.start(), starts)
        if match.group(0).startswith("\\") or line - 1 in fenced:
            continue
        if any(start <= match.start() < end for start, end in spans):
            continue
        found.append((match, line))
    return found


def tokens(text: str, has_source: bool = False) -> list[dict]:
    """List tokens as {name, line, prefilled} in document order."""
    prefilled = prefilled_tokens(has_source)
    return [
        {"name": m.group(1), "line": line, "prefilled": m.group(1) in prefilled}
        for m, line in _token_matches(text)
    ]


def resolve_tokens(text: str, values: dict) -> str:
    """Replace each token tokens() reports whose name is a key of values."""
    parts, cursor = [], 0
    for match, _line in _token_matches(text):
        if match.group(1) not in values:
            continue
        value = str(values[match.group(1)]).replace("\r", " ").replace("\n", " ")
        parts += [text[cursor:match.start()], value]
        cursor = match.end()
    return "".join(parts) + text[cursor:]


def resolve_prefilled(text: str, values: dict, has_source: bool = False) -> str:
    """Replace each prefilled token except DEFERRED_TOKENS; a missing value becomes ""."""
    names = prefilled_tokens(has_source) - DEFERRED_TOKENS
    return resolve_tokens(text, {name: values.get(name, "") for name in names})


def generated_values(now) -> dict:
    """Generated token values; copy of token-render.py resolve_generated_tokens."""
    local = now.astimezone()
    return {
        "uuid": local.strftime("%Y%m%d%H%M%S"),
        "datestamp": local.strftime("%Y-%m-%d"),
        "updated": local.strftime("%Y-%m-%d %H:%M"),
        "date_iso": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def config_values(config: dict) -> dict:
    """Config token values; token-render.py resolve_config_tokens, CONFIG_TOKENS only."""
    found = {}
    for entry in _optional_entries(config):
        token = entry.get("token")
        if isinstance(token, str) and token and entry.get("default") is not None:
            found[token] = str(entry["default"])
    if config.get("profile"):
        found.setdefault("profile", config["profile"])
    return {k: v for k, v in found.items() if k in CONFIG_TOKENS}


def _optional_entries(config: dict) -> list[dict]:
    """The dict items of frontmatter.optional; [] when any level has the wrong type."""
    frontmatter = config.get("frontmatter")
    optional = frontmatter.get("optional") if isinstance(frontmatter, dict) else None
    if not isinstance(optional, list):
        return []
    return [entry for entry in optional if isinstance(entry, dict)]


def source_link_value(source_path: str | None, keep_source: bool) -> str:
    """``[[<source stem>]]`` when the source is kept; "" when it is deleted or absent."""
    if not source_path or not keep_source:
        return ""
    name = posixpath.basename(source_path)
    stem = name[:-3] if name.endswith(".md") else name
    return f"[[{stem}]]"


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


def _code_fence_finding(text: str) -> dict:
    opened_at = _scan_fences(_split(text))[1]
    if opened_at is not None:
        return _finding(
            "code_fence_closed", "FAIL",
            f"The code fence opened on line {opened_at} is never closed.",
            "Close it with a line repeating its ``` or ~~~ run, or remove the stray opener.")
    return _finding("code_fence_closed", "PASS", "Every code fence is closed.")


def _token_finding(text: str) -> dict:
    left = sorted({t["name"] for t in tokens(text)})
    if left:
        names = ", ".join("{{" + name + "}}" for name in left)
        return _finding(
            "no_tokens", "FAIL", f"Token(s) left outside fenced code: {names}.",
            "Fill each token with its value or remove it.")
    return _finding("no_tokens", "PASS", "No `{{token}}` is left outside fenced code.")


def filled_note_check(text: str) -> FilledNoteResult:
    """Check a filled note: closed fences, no tomo: key, no <%, no {{token}}."""
    block = leading_block(text)
    findings = _fence_findings(block) + _tomo_key_findings(block)
    findings += [_templater_finding(text), _code_fence_finding(text), _token_finding(text)]
    ok = all(f["status"] != "FAIL" for f in findings)
    return FilledNoteResult(ok=ok, findings=findings)
