# version: 0.1.0
"""up_parse.py — SSoT for "does this note declare a parent?"

Parses both inline `up::` (Dataview-style) and frontmatter `up:` values
from a raw note string, returning a single UpParseResult.  No extra
Kado round-trips are needed — the caller supplies the full raw content
from a single read_note() call.

Resolution priority (ADR-2):
  1. inline `up:: [[X]]`  → wins unconditionally
  2. frontmatter `up:` non-empty list/scalar with a resolvable stem
  3. absent/empty         → target=None, source=None

Note: parse_up_from_content does NOT emit `up_state`.  The caller derives
it: target is None → "absent"; target in moc_stem_set → "valid"; else →
"broken". (M1, SDD spec 021 Phase 1 T1.1)

Supersedes the two inline-only regex sites:
  - tomo/scripts/moc-tree-builder.py  (UP_RE, around line 49)
  - tomo/scripts/moc-discovery.py     (_UP_MARKER_RE, around line 1271)
Those sites will be retrofitted to import this module in later tasks.

Spec: docs/XDD/specs/021-moc-propose-consolidation/plan/phase-1.md T1.1
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import yaml


# ──────────────────────────────────────────────────────────────────────────────
# Types
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class UpParseResult:
    """Result of parsing the `up` relationship from a raw note."""

    target: Optional[str]  # parent stem, anchor-stripped; None when absent
    source: Optional[str]  # "inline" | "frontmatter" | None


# ──────────────────────────────────────────────────────────────────────────────
# Internal regex
# ──────────────────────────────────────────────────────────────────────────────

# Match `up:: [[Target]]` lines; allows leading whitespace or callout prefix.
# Replicates the pattern from moc-discovery.py _UP_MARKER_RE but scoped to
# wikilink-only matches (bare text after up:: is intentionally NOT matched —
# a bare `up::` without [[...]] is treated as absent per SDD Rule).
_INLINE_UP = re.compile(r"^[\s>\-]*up::\s*\[\[(.+?)\]\]", re.MULTILINE)

# Frontmatter delimiter (replicates moc-tree-builder.py FRONTMATTER_RE).
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)

# Wikilink: [[target]] or [[target|alias]] or [[target#anchor]] etc.
_WIKILINK_RE = re.compile(r"^\[\[(.+?)\]\]$")


# ──────────────────────────────────────────────────────────────────────────────
# Private helpers  (reuse parse_frontmatter / get_body pattern from
# moc-tree-builder.py — same logic, local copy keeps this module dependency-free)
# ──────────────────────────────────────────────────────────────────────────────


def _split_frontmatter(raw_content: str) -> tuple[dict, str]:
    """Split raw note into (frontmatter_dict, body_text).

    Returns ({}, raw_content) when no YAML frontmatter block is found.
    Malformed YAML yields ({}, raw_content) with no exception raised.
    """
    match = _FRONTMATTER_RE.match(raw_content.lstrip())
    if not match:
        return {}, raw_content
    try:
        fm = yaml.safe_load(match.group(1))
        fm_dict = fm if isinstance(fm, dict) else {}
    except yaml.YAMLError:
        fm_dict = {}
    body = raw_content[match.end():]
    return fm_dict, body


def _strip_anchor(wikilink_target: str) -> str:
    """Remove `#anchor` or `#^block-id` from a wikilink target stem."""
    return wikilink_target.split("#")[0].strip()


def _strip_alias(wikilink_target: str) -> str:
    """Remove `|Alias` from a wikilink target, keeping the stem portion."""
    return wikilink_target.split("|")[0].strip()


def _clean_target(raw: str) -> str:
    """Strip anchor then alias from a raw wikilink target string."""
    return _strip_alias(_strip_anchor(raw))


def _first_wikilink(up_value: object) -> Optional[str]:
    """Extract a clean stem from a frontmatter `up:` value.

    Accepts:
      - list → first non-empty element
      - str  → used directly
      - None / empty / other → returns None

    Each candidate is unwrapped from [[...]] if present, then anchor- and
    alias-stripped.  An empty string after stripping → None.
    """
    if up_value is None:
        return None

    if isinstance(up_value, list):
        candidates = [str(v) for v in up_value if v is not None and str(v).strip()]
        if not candidates:
            return None
        raw = candidates[0].strip()
    elif isinstance(up_value, str):
        raw = up_value.strip()
    else:
        # Unexpected type (int, bool, …) — treat as absent
        return None

    if not raw:
        return None

    # Unwrap [[...]] if present
    m = _WIKILINK_RE.match(raw)
    if m:
        inner = m.group(1)
    else:
        # Plain stem (no wikilink brackets) — accepted directly
        inner = raw

    stem = _clean_target(inner)
    return stem if stem else None


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def parse_up_from_content(raw_content: str) -> UpParseResult:
    """Parse the `up` parent relationship from raw note content.

    Takes the RAW note content from a single read_note() call and splits the
    frontmatter block locally — no extra Kado round-trip needed (C1, SDD).

    Resolution order (ADR-2):
      1. inline `up:: [[X]]` in body → target=X, source="inline"
      2. frontmatter `up:` non-empty list/scalar → target=first, source="frontmatter"
      3. missing / [] / null / `up::` without wikilink → target=None, source=None
    """
    frontmatter, body = _split_frontmatter(raw_content or "")

    # 1. Inline wins
    m = _INLINE_UP.search(body)
    if m:
        raw_target = m.group(1).strip()
        if raw_target:
            return UpParseResult(target=_clean_target(raw_target), source="inline")

    # 2. Frontmatter fallback
    target = _first_wikilink(frontmatter.get("up"))
    if target:
        return UpParseResult(target=target, source="frontmatter")

    # 3. Absent
    return UpParseResult(target=None, source=None)
