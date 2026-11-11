# vault_config_edit.py — text-preserving edits of one nested key in vault-config.yaml.
# version: 0.2.1
"""Insert, replace or remove one nested key in ``vault-config.yaml`` as text.

``set_path(text, path, value)`` finds the key line at each level by indent,
descends into its block, inserts an absent key (creating missing parents and
a missing top-level section on the way), replaces a present key's lines or
removes them when ``value`` is None, and leaves every other byte as it was —
comments, blank lines, quoting and the order of unrelated keys included.
A flow mapping on a parent's key line (``weekly: { enabled: true, ... }``) is
rewritten as a block with the leaf merged in: every other member is copied as
written onto its own line, the key line's comment stays on the key line; a
mapping emptied by the removal is written as ``{}`` so the key stays a
mapping. A scalar where a mapping is expected, or flow syntax the rewrite
cannot scan
(explicit keys, duplicate or typed keys, unbalanced braces), raises
``EditRefused``.

``vault-config-writer.py review`` (spec 045, ADR-5) applies its leaf edits
through this module; ``templates-include`` shares the line helpers.

Rendering: double-quoted strings, lowercase booleans, flow lists on one line,
two-space steps unless the parent's children show another; line endings
follow the file's first line.

Design notes: docs/tomo/scripts/lib/vault_config_edit.md
"""
from __future__ import annotations

import json
import re
from typing import Any, List, Sequence, Tuple

import yaml

DEFAULT_STEP = 2


class EditRefused(ValueError):
    """The text cannot hold the edit (a scalar where a mapping is expected)."""


# --- line helpers (shared with the writer's templates-include path) ------------------

def newline_of(text: str) -> str:
    """The ending of the file's first line: CRLF files get CRLF insertions."""
    first = text.find("\n")
    return "\r\n" if first > 0 and text[first - 1] == "\r" else "\n"


def leading_ws(line: str) -> str:
    return line[: len(line) - len(line.lstrip(" \t"))]


def is_key_line(line: str, indent: str, key: str) -> bool:
    """``<indent>key:`` plain or quoted, followed by end of line, a space or a comment."""
    if leading_ws(line) != indent:
        return False
    rest = line.strip()
    for spelling in (f"{key}:", f'"{key}":', f"'{key}':"):
        if rest.startswith(spelling):
            after = rest[len(spelling):]
            return after == "" or after[0] in " \t#"
    return False


def inline_value(line: str) -> str:
    """The value text on a key line, ``""`` when the value is a block below or only a comment."""
    rest = line.strip()
    after = rest[rest.index(":") + 1:].strip()
    return "" if after.startswith("#") else after


def is_list_continuation(line: str, indent: str) -> bool:
    ws = leading_ws(line)
    return bool(line.strip()) and (
        len(ws) > len(indent) or (ws == indent and line.lstrip().startswith("- "))
    )


def block_extent(lines: Sequence[str], idx: int, indent: str) -> Tuple[int, int, int]:
    """``(body start, end of content, end of block)`` for the key line at ``idx``.

    The block holds blank lines, deeper-indented lines and ``- `` items at the
    key's own indent. ``end of content`` excludes trailing comment lines (they
    stay outside a replaced key, as in ``templates-include``); ``end of block``
    excludes trailing blank lines only.
    """
    end_content = end_block = j = idx + 1
    while j < len(lines) and (lines[j].strip() == "" or is_list_continuation(lines[j], indent)):
        j += 1
        if lines[j - 1].strip():
            end_block = j
            if not lines[j - 1].lstrip().startswith("#"):
                end_content = j
    return idx + 1, end_content, end_block


def child_indent(lines: Sequence[str], lo: int, hi: int, parent_indent: str) -> str:
    """Indent of the block's first key line, else one step deeper than the parent."""
    for ln in lines[lo:hi]:
        if ln.strip() and not ln.lstrip().startswith("#") and not ln.lstrip().startswith("- "):
            return leading_ws(ln)
    return parent_indent + " " * DEFAULT_STEP


# --- rendering ---------------------------------------------------------------------

def render_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return "null"
    raise EditRefused("value must be a string, number, boolean, list or mapping")


def render_leaf(key: str, value: Any, indent: str, nl: str) -> str:
    if isinstance(value, list):
        return f"{indent}{key}: [{', '.join(render_scalar(v) for v in value)}]{nl}"
    return f"{indent}{key}: {render_scalar(value)}{nl}"


def render_tree(key: str, value: Any, indent: str, step: int, nl: str) -> str:
    """``key:`` with its mapping children as a block, or a leaf line."""
    if not isinstance(value, dict):
        return render_leaf(key, value, indent, nl)
    out = f"{indent}{key}:{nl}"
    for k, v in value.items():
        out += render_tree(k, v, indent + " " * step, step, nl)
    return out


def render_chain(path: Sequence[str], value: Any, indent: str, step: int, nl: str) -> str:
    tree: Any = value
    for key in reversed(path[1:]):
        tree = {key: tree}
    return render_tree(path[0], tree, indent, step, nl)


# --- the edit ----------------------------------------------------------------------

def get_path(mapping: Any, path: Sequence[str]) -> Tuple[bool, Any]:
    """``(found, value)`` of a nested key in a parsed config."""
    node = mapping
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return False, None
        node = node[key]
    return True, node


def set_path(text: str, path: Sequence[str], value: Any) -> str:
    """The text with ``path`` set to ``value`` (None removes the key); other bytes unchanged."""
    if not path:
        raise ValueError("path must name at least one key")
    if isinstance(value, dict):
        for key, child in value.items():
            text = set_path(text, (*path, key), child)
        return text
    nl = newline_of(text)
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += nl
    return "".join(_edit(lines, 0, len(lines), "", DEFAULT_STEP, tuple(path), value, nl, top=True))


def _edit(lines: List[str], lo: int, hi: int, indent: str, step: int, path: Tuple[str, ...],
          value: Any, nl: str, *, top: bool = False) -> List[str]:
    key, rest = path[0], path[1:]
    idx = next((i for i in range(lo, hi) if is_key_line(lines[i], indent, key)), None)
    if idx is None:
        if value is None:
            return lines
        rendered = render_chain(path, value, indent, step, nl)
        if top and hi > 0 and lines[hi - 1].strip():
            rendered = nl + rendered
        return lines[:hi] + [rendered] + lines[hi:]
    body_lo, end_content, end_block = block_extent(lines, idx, indent)
    if not rest:
        replacement = [] if value is None else [render_leaf(key, value, indent, nl)]
        return lines[:idx] + replacement + lines[end_content:]
    if inline_value(lines[idx]):
        return _edit_flow_mapping(lines, idx, end_content, indent, step, key, rest, value, nl)
    child = child_indent(lines, body_lo, end_block, indent)
    child_step = len(child) - len(indent) if len(child) > len(indent) else DEFAULT_STEP
    return _edit(lines, body_lo, end_block, child, child_step, rest, value, nl)


def _edit_flow_mapping(lines: List[str], idx: int, end: int, indent: str, step: int, key: str,
                       rest: Tuple[str, ...], value: Any, nl: str) -> List[str]:
    """Rewrite ``key: { ... }`` as a block mapping with the leaf merged in, other members verbatim."""
    stripped = lines[idx].strip()
    spelling = next(s for s in (f"{key}:", f'"{key}":', f"'{key}':") if stripped.startswith(s))
    text = "\n".join([stripped[len(spelling):]] + [ln.strip() for ln in lines[idx + 1:end]])
    block = _flow_block(text, indent + " " * step, step, rest, value, nl)
    if block is None:
        return lines
    body, tail = block
    return lines[:idx] + [f"{indent}{spelling}{tail}{nl}", *body] + lines[end:]


_UNSCANNABLE = "the flow mapping on the key line could not be rewritten as a block"
_NULL_SPELLINGS = ("", "~", "null", "Null", "NULL")


def _flow_block(text: str, indent: str, step: int, rest: Tuple[str, ...], value: Any,
                nl: str) -> Tuple[List[str], str] | None:
    """``(block lines, text after the closing brace)`` for the flow mapping ``text`` opens, with
    ``rest`` set to ``value``; None when nothing changes (a null for an absent key)."""
    text = text.strip()
    if not text.startswith("{"):
        raise EditRefused("a scalar sits where a mapping is expected")
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        parsed = None
    entries, close = _scan_flow_mapping(text)
    if not isinstance(parsed, dict) or [k for k, _, _ in entries] != [str(k) for k in parsed]:
        raise EditRefused(_UNSCANNABLE)
    tail = text[close:].rstrip()
    name, deeper = rest[0], rest[1:]
    pos = next((i for i, (k, _, _) in enumerate(entries) if k == name), None)
    if pos is None and value is None:
        return None
    body: List[str] = []
    for i, (_, raw_key, raw_val) in enumerate(entries):
        if i != pos:
            body.append(f"{indent}{raw_key}: {raw_val}{nl}" if raw_val else f"{indent}{raw_key}:{nl}")
        elif not deeper:
            if value is not None:
                body.append(render_leaf(raw_key, value, indent, nl))
        else:
            if raw_val not in _NULL_SPELLINGS and not raw_val.startswith("{"):
                raise EditRefused("a scalar sits where a mapping is expected")
            inner = "{}" if raw_val in _NULL_SPELLINGS else raw_val
            nested = _flow_block(inner, indent + " " * step, step, deeper, value, nl)
            if nested is None:
                return None
            body.append(f"{indent}{raw_key}:{nested[1]}{nl}")
            body.extend(nested[0])
    if pos is None:
        body.append(render_chain(rest, value, indent, step, nl))
    if not body:
        tail = " {}" + tail    # a key line without a block reads as null, not as the emptied mapping
    return body, tail


def _scan_flow_mapping(text: str) -> Tuple[List[Tuple[str, str, str]], int]:
    """``([(key, key as written, value as written), ...], index after the closing brace)``.

    Quotes, nested ``[]``/``{}`` and ``#`` comments are honoured; comments are dropped.
    """
    entries: List[str] = []
    buf: List[str] = []
    depth, quote, i = 0, "", 1
    while i < len(text):
        ch = text[i]
        if quote:
            buf.append(ch)
            if ch == quote == "'" and text[i + 1:i + 2] == "'":
                buf.append("'")
                i += 1
            elif ch == "\\" and quote == '"':
                buf.append(text[i + 1:i + 2])
                i += 1
            elif ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch == "#" and text[i - 1] in " \t\n":
            newline = text.find("\n", i)
            i = len(text) if newline < 0 else newline
            continue
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}" and depth > 0:
            depth -= 1
            buf.append(ch)
        elif ch == "}":
            entries.append("".join(buf))
            return [_split_entry(e) for e in entries if e.strip()], i + 1
        elif ch == "," and depth == 0:
            entries.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    raise EditRefused(_UNSCANNABLE)


def _split_entry(entry: str) -> Tuple[str, str, str]:
    """``(key, key as written, value as written)`` of one ``key: value`` flow member."""
    depth, quote = 0, ""
    for i, ch in enumerate(entry):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == ":" and depth == 0 and (i + 1 == len(entry) or entry[i + 1] in " \t\n"):
            raw_key, raw_val = entry[:i].strip(), re.sub(r"[ \t]*\n[ \t]*", " ", entry[i + 1:].strip())
            break
    else:
        raw_key, raw_val = entry.strip(), ""
    key = raw_key[1:-1] if len(raw_key) > 1 and raw_key[0] in "\"'" and raw_key[-1] == raw_key[0] else raw_key
    return key, raw_key, raw_val


__all__ = [
    "EditRefused", "block_extent", "child_indent", "get_path", "inline_value", "is_key_line",
    "is_list_continuation", "leading_ws", "newline_of", "render_leaf", "set_path",
]
