"""Shared, pure MOC-structure parser — spec 022 / T1.1.

No IO, no Kado imports. Provides heading discovery, footer-boundary
detection, and editable-callout scanning over raw MOC body strings.
Both moc-tree-builder (build-time) and instruction-render (render-time
fallback) import from here so they agree on what counts as a
heading/footer/editable-callout.

Caller is responsible for supplying footer_set and editable_set — this
library never hardcodes either. FOOTER_CALLOUTS stays hardcoded only in
instruction-render.py per spec 022 / #35 / F-55.
"""
# version: 1.0.0

import re as _re

# Regexes lifted verbatim from instruction-render.py lines 1510-1511
# so that build-time and render-time parsing agree exactly.
_CALLOUT_RE = _re.compile(r"^>\s*\[!([A-Za-z][A-Za-z0-9_-]*)\][+-]?.*$")
_HEADING_RE = _re.compile(r"^(#{2,6})\s+(.+?)\s*$")


def _callout_name(line: str) -> str | None:
    """Return the callout type name for a callout-opening line, else None."""
    m = _CALLOUT_RE.match(line)
    return m.group(1) if m else None


def _strip_gt_prefix(line: str) -> str:
    """Strip leading `> ` (blockquote prefix) from a callout line."""
    s = line.lstrip()  # leading whitespace only; callout `>` handled next
    if s.startswith(">"):
        s = s[1:].lstrip()
    return s


def footer_index(lines: list[str], footer_set: set[str]) -> int:
    """Return the index of the first line that is a footer-marker callout.

    A footer-marker callout is any callout whose type name is in
    ``footer_set``. Returns ``len(lines)`` when no footer is found
    (sentinel: all content is before the footer boundary).

    Args:
        lines: The MOC body split into lines (not stripped — rstrip applied
               internally before matching, consistent with instruction-render).
        footer_set: Caller-supplied set of callout names that delimit the
                    footer (e.g. {"video", "calendar", "puzzle", "compass"}).
    """
    for i, raw in enumerate(lines):
        name = _callout_name(raw.rstrip())
        if name and name in footer_set:
            return i
    return len(lines)


def parse_headings(body: str, footer_set: set[str]) -> list[dict]:
    """Return ordered heading dicts for H2–H6 headings before the footer.

    Each dict has keys ``text`` (str) and ``level`` (int, 2–6).  H1 headings
    are excluded.  Only lines before the footer boundary (as determined by
    ``footer_index``) are scanned.

    Args:
        body: Raw MOC body string.
        footer_set: Passed through to ``footer_index`` to locate the footer.

    Returns:
        List of ``{"text": str, "level": int}`` dicts, in document order.
    """
    if not body:
        return []
    lines = body.splitlines()
    cutoff = footer_index(lines, footer_set)
    result: list[dict] = []
    for raw in lines[:cutoff]:
        m = _HEADING_RE.match(raw.rstrip())
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            result.append({"text": text, "level": level})
    return result


def parse_editable_callouts(body: str, editable_set: set[str]) -> list[str]:
    """Return full callout-opening lines (sans `> `) whose type is in editable_set.

    Scans the entire body (not limited to before-footer) so callers can
    use this for template bodies where no footer exists.  Lines are returned
    in document order with the leading ``> `` blockquote prefix stripped.

    Args:
        body: Raw MOC body string.
        editable_set: Caller-supplied set of callout names considered editable
                      (e.g. {"blocks", "other", "connect"}).  An empty set
                      returns an empty list immediately.

    Returns:
        List of callout opening-line strings starting with ``[!<name>]``.
    """
    if not body or not editable_set:
        return []
    result: list[str] = []
    for raw in body.splitlines():
        line = raw.rstrip()
        name = _callout_name(line)
        if name and name in editable_set:
            result.append(_strip_gt_prefix(line))
    return result
