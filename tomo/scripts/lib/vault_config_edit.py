# vault_config_edit.py — text-preserving edits of one nested key in vault-config.yaml.
# version: 0.1.0
"""Insert, replace or remove one nested key in ``vault-config.yaml`` as text.

``set_path(text, path, value)`` finds the key line at each level by indent,
descends into its block, inserts an absent key (creating missing parents and
a missing top-level section on the way), replaces a present key's lines or
removes them when ``value`` is None, and leaves every other byte as it was —
comments, blank lines, quoting and the order of unrelated keys included.
A flow mapping on a parent's key line (``weekly: { enabled: true, ... }``) is
rewritten as a block with the leaf merged in; a scalar where a mapping is
expected raises ``EditRefused``.

``vault-config-writer.py review`` (spec 045, ADR-5) applies its leaf edits
through this module; ``templates-include`` shares the line helpers.

Rendering: double-quoted strings, lowercase booleans, flow lists on one line,
two-space steps unless the parent's children show another; line endings
follow the file's first line.

Design notes: docs/tomo/scripts/lib/vault_config_edit.md
"""
from __future__ import annotations

import json
from typing import Any, List, Optional, Sequence, Tuple

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
        if v is not None:
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
    inline = inline_value(lines[idx])
    if inline:
        return _edit_flow_mapping(lines, idx, end_content, indent, step, inline, rest, value, nl)
    child = child_indent(lines, body_lo, end_block, indent)
    child_step = len(child) - len(indent) if len(child) > len(indent) else DEFAULT_STEP
    return _edit(lines, body_lo, end_block, child, child_step, rest, value, nl)


def _edit_flow_mapping(lines: List[str], idx: int, end: int, indent: str, step: int, inline: str,
                       rest: Tuple[str, ...], value: Any, nl: str) -> List[str]:
    """Rewrite ``key: { ... }`` as a block mapping with the leaf merged in."""
    key = lines[idx].strip().split(":", 1)[0].strip("\"'")
    try:
        parsed = yaml.safe_load(" ".join(ln.strip() for ln in lines[idx:end]).split(":", 1)[1])
    except yaml.YAMLError:
        parsed = None
    if not isinstance(parsed, dict):
        raise EditRefused("a scalar sits where a mapping is expected")
    node = parsed
    for name in rest[:-1]:
        if not isinstance(node.get(name), dict):
            if node.get(name) is not None:
                raise EditRefused("a scalar sits where a mapping is expected")
            node[name] = {}
        node = node[name]
    if value is None:
        node.pop(rest[-1], None)
    else:
        node[rest[-1]] = value
    return lines[:idx] + [render_tree(key, parsed, indent, step, nl)] + lines[end:]


__all__: Optional[List[str]] = [
    "EditRefused", "block_extent", "child_indent", "get_path", "inline_value", "is_key_line",
    "is_list_continuation", "leading_ws", "newline_of", "render_leaf", "set_path",
]
