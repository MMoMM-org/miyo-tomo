#!/usr/bin/env python3
# version: 0.9.0
"""
suggestion-parser.py — Parse an approved Tomo suggestions document.

Reads a MiYo-Tomo suggestions markdown file (with `[x] Approved` checkbox)
and extracts user-approved items with any modifications they made to fields,
alternatives, and action checkboxes.

Accepts multiple section header formats:
  - Spec format:    ### S01: filename.md    or    ### S01 — Title
  - LLM output:     ### A1. Title    or    ### B1. Title    (A-E groups)

Usage:
    python suggestion-parser.py --file PATH
    cat suggestions.md | python suggestion-parser.py
"""

import argparse
import json
import os
import re
import sys


# ──────────────────────────────────────────────────────────────────────────────
# Patterns
# ──────────────────────────────────────────────────────────────────────────────

# Section header: accept both spec format (S01:) and LLM output format (A1., B1., etc.)
#   ### S01: filename.md    ### S01 — Title
#   ### A1. Title           ### B12. Another
RE_SECTION_HEADER = re.compile(r"^#{2,3}\s+([A-Z]\d+)[.:\s—–-]+", re.IGNORECASE)

# MOC proposal-doc section header: ### MOCxx — Title  (F-43 T4.1)
#   ### MOC01 — Shell & Terminal (MOC)
RE_MOC_SECTION_HEADER = re.compile(r"^###\s+(MOC\d+)\s*[—–-]+\s*(.*)", re.IGNORECASE)

# Checkbox lines
RE_CHECKED = re.compile(r"^\s*-\s+\[x\]\s*(.*)", re.IGNORECASE)
RE_UNCHECKED = re.compile(r"^\s*-\s+\[\s\]\s*(.*)", re.IGNORECASE)

# Bold field: **Name:** value
RE_FIELD = re.compile(r"^\s*\*\*([^*]+)\*\*[:\s]*(.*)")

# Wikilink: [[Note Name]]  or  [[Note Name#anchor]]
RE_WIKILINK = re.compile(r"\[\[([^\]#|]+)(?:[#|][^\]]*)?\]\]")

# Source field value: backtick or plain path
RE_SOURCE = re.compile(r"`([^`]+)`|(\S+\.md)")

# Type field: word_word (confidence: 0.85)  or  word_word (confidence 85%)
RE_TYPE = re.compile(r"([a-z_]+)\s*\(confidence[:\s]*([\d.]+%?)\)")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _is_checked(line: str) -> bool:
    return bool(RE_CHECKED.match(line))


def _checkbox_text(line: str) -> str:
    """Return the text after the checkbox marker."""
    m = RE_CHECKED.match(line) or RE_UNCHECKED.match(line)
    return m.group(1).strip() if m else ""


def _extract_wikilink(text: str) -> str | None:
    """Return the first wikilink target found, or None."""
    m = RE_WIKILINK.search(text)
    return m.group(1).strip() if m else None


def _parse_tags(value: str) -> list[str]:
    """
    Parse tags from a variety of formats:
      - Comma-separated:   topic/knowledge, type/note/normal
      - Hash-prefixed:     #topic/knowledge, #type/note/normal
      - YAML list:         ['topic/knowledge', 'type/note/normal']
      - Space-separated hash tags on one line
    Returns a list of clean tag strings (no leading #).
    """
    # Strip surrounding brackets/quotes that look like YAML inline list
    stripped = value.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        stripped = stripped[1:-1]

    # Split on commas or spaces (if comma-separated, prefer comma)
    if "," in stripped:
        parts = [p.strip().strip("'\"") for p in stripped.split(",")]
    else:
        parts = [p.strip().strip("'\"") for p in stripped.split()]

    # Remove leading # and empty strings
    tags = [p.lstrip("#") for p in parts if p and p != "#"]
    return tags


def _normalise_action(text: str) -> str:
    """
    Convert a human-readable action line to a snake_case action key.
    Examples:
      'Create atomic note "Some Topic" in Atlas/202 Notes/'  → 'create_atomic_note'
      'Link to existing [[Related Note]] instead'            → 'link_to_existing'
      'File as quote under [[Quotes]]'                       → 'file_as_quote'
      'Skip atomic note creation, only update daily note'    → 'skip'
    """
    low = text.lower()
    if "create atomic" in low or "create note" in low:
        return "create_atomic_note"
    if "create" in low and "moc" in low:
        return "create_moc"
    if "link to existing" in low:
        return "link_to_existing"
    if "file as quote" in low or "file as" in low:
        return "file_as_quote"
    if "skip" in low:
        return "skip"
    if "update daily" in low:
        return "update_daily_note"
    if "use classification" in low:
        return "use_classification_moc"
    if "bestehende up::" in low and "behalten" in low:
        return "override_preserve_existing_up"
    # Fallback: snake_case the first few words
    words = re.split(r"\s+", re.sub(r"[^a-z0-9\s]", "", low))
    return "_".join(w for w in words[:4] if w)


# ──────────────────────────────────────────────────────────────────────────────
# Section parser
# ──────────────────────────────────────────────────────────────────────────────

def parse_section(section_id: str, lines: list[str]) -> dict | None:
    """
    Parse one section and return a structured dict, or None on fatal error.

    Flat format (LLM output from suggestion-builder v0.6.0+):

        ### A1. Ausdaueraufbau (Endurance Training)
        - **Source:** `202301031251.md`
        - **Suggested name:** Ausdaueraufbau
        - **Type:** #type/note/normal
        - **Destination:** Atlas/202 Notes/
        - **Link to MOC:** [[2200 - Mind-Body Connection]]
        - **Template:** t_note_tomo
        - **Tags:** #topic/exercise
        - **Summary:** ...
        - **Why:** reasoning here
        - [x] Accept
        - [ ] Skip (keep in inbox)
        - [ ] Delete source

    Field aliases handled:
      - "Suggested name" / "Title"       → title
      - "Link to MOC" / "Parent MOC"     → parent_moc
      - "Destination"                    → destination
      - "Template"                       → template
      - "Summary"                        → summary
      - "Type"                           → type (strips leading # and backticks)
      - "Tags" / "Tag"                   → tags list

    Approval checkboxes:
      - "Accept" or "Approve" checked    → approved = true
      - "Delete source" checked          → delete_source = true
      - "Skip" checked (and not Accept)  → approved = false
    """
    result: dict = {
        "id": section_id,
        "source_path": None,
        "type": None,
        "approved": False,
        "delete_source": False,
        "keep_origin": False,
        "action": None,
        "title": None,
        "tags": [],
        "parent_moc": None,
        "parent_mocs": [],  # all checked MOCs from Link to MOC checkboxes
        "destination": None,
        "template": None,
        "summary": None,
        "classification": None,
    }

    # State: when we see "Link to MOC:" header, subsequent checkboxes are
    # MOC selections (not approve/skip). Reset when we hit a Decision header
    # or another field.
    in_moc_list = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # ── Checkbox lines ────────────────────────────────────────
        cb_checked = RE_CHECKED.match(stripped)
        cb_unchecked = RE_UNCHECKED.match(stripped)
        if cb_checked or cb_unchecked:
            text = _checkbox_text(stripped)

            # MOC selection checkboxes (under "Link to MOC:" header)
            if in_moc_list:
                wl = _extract_wikilink(text)
                if wl and cb_checked:
                    result["parent_mocs"].append(wl)
                continue

            # Decision checkboxes (approve/skip/delete/keep-origin)
            text_lower = text.lower()
            if "accept" in text_lower or "approve" in text_lower:
                result["approved"] = bool(cb_checked)
            elif "keep origin" in text_lower:
                result["keep_origin"] = bool(cb_checked)
            elif "delete source" in text_lower or text_lower.startswith("delete"):
                result["delete_source"] = bool(cb_checked)
            # "Skip" is the implicit inverse of Accept — no extra handling needed
            continue

        # ── Field lines: - **Field:** value  OR  **Field:** value ─
        # Strip leading "- " if present so RE_FIELD matches both forms.
        field_line = stripped
        if field_line.startswith("- "):
            field_line = field_line[2:].strip()

        m = RE_FIELD.match(field_line)
        if not m:
            continue

        # Key may include trailing colon when written as **Field:** (colon inside
        # bold markers). Strip it and any whitespace before comparing.
        key = m.group(1).strip().rstrip(":").strip().lower()
        val = m.group(2).strip()

        # Any new field header ends the MOC checkbox region
        in_moc_list = False

        if key == "source":
            src = RE_SOURCE.search(val)
            if src:
                result["source_path"] = src.group(1) or src.group(2)
            else:
                wl = _extract_wikilink(val)
                result["source_path"] = wl or val

        elif key == "type":
            # "#type/note/normal" or "fleeting_note (confidence: 0.85)"
            tm = RE_TYPE.match(val)
            if tm:
                result["type"] = tm.group(1)
            else:
                # Strip backticks, leading #, take first token
                cleaned = val.strip("`").lstrip("#").strip()
                result["type"] = cleaned.split()[0] if cleaned else None

        elif key in ("title", "suggested name", "suggested title", "name"):
            # Strip trailing edit hints like "← change if you want..."
            clean_val = val.split("←")[0].strip() if "←" in val else val
            result["title"] = clean_val

        elif key in ("tags", "tag", "new tags to add", "new tags"):
            result["tags"] = _parse_tags(val)

        elif key in ("parent moc", "parent_moc", "parentmoc", "link to moc", "moc"):
            in_moc_list = True  # subsequent checkboxes are MOC selections
            wl = _extract_wikilink(val)
            if wl:
                result["parent_moc"] = wl

        elif key in ("destination", "location", "move to"):
            # Strip wrapping backticks/brackets/wikilinks and edit hints
            cleaned = val.split("←")[0].strip().strip("`").strip()
            wl = _extract_wikilink(cleaned)
            result["destination"] = wl or cleaned

        elif key == "template":
            cleaned = val.split("←")[0].strip().strip("`").strip()
            wl = _extract_wikilink(cleaned)
            result["template"] = wl or cleaned

        elif key == "summary":
            result["summary"] = val

        elif key == "classification":
            result["classification"] = val

    # ── MOC consolidation ──────────────────────────────────────
    # If parent_moc was not set directly but parent_mocs has checked items,
    # use the first checked MOC as the primary parent_moc.
    if not result["parent_moc"] and result["parent_mocs"]:
        result["parent_moc"] = result["parent_mocs"][0]

    # ── Delete semantics ─────────────────────────────────────────
    # If Accept is checked, Delete is irrelevant — we keep the source.
    if result["approved"]:
        result["delete_source"] = False

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Document splitter
# ──────────────────────────────────────────────────────────────────────────────

def split_into_sections(text: str) -> list[tuple[str, list[str]]]:
    """
    Split the document into (section_id, lines) tuples for each S## section.
    Lines before the first S## header are ignored (document header/preamble).
    """
    sections: list[tuple[str, list[str]]] = []
    current_id: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        m = RE_SECTION_HEADER.match(line)
        if m:
            if current_id is not None:
                sections.append((current_id, current_lines))
            current_id = m.group(1).upper()
            current_lines = []
        elif current_id is not None:
            # A level-2 header that isn't an S## section ends the current section.
            # This prevents "## Proposed MOCs", "## Needs Attention", etc. from
            # bleeding into the last S## item.
            if line.startswith("## ") and not RE_SECTION_HEADER.match(line):
                sections.append((current_id, current_lines))
                current_id = None
                current_lines = []
            else:
                current_lines.append(line)

    if current_id is not None:
        sections.append((current_id, current_lines))

    return sections


# ──────────────────────────────────────────────────────────────────────────────
# Proposed MOCs parser
# ──────────────────────────────────────────────────────────────────────────────

RE_PROPOSED_MOC_HEADER = re.compile(r"^###\s+Proposed MOC:\s*(.*)", re.IGNORECASE)


def parse_proposed_mocs(text: str, config_template: str = "") -> list[dict]:
    """Parse the ## Proposed MOCs section and return approved MOC items.

    Each approved Proposed MOC becomes a confirmed_item with action=create_moc.
    """
    mocs: list[dict] = []

    # Find the ## Proposed MOCs section
    lines = text.splitlines()
    in_section = False
    moc_blocks: list[list[str]] = []
    current_block: list[str] = []

    for line in lines:
        if line.startswith("## Proposed MOCs"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            # Next top-level section ends Proposed MOCs
            break
        if not in_section:
            continue

        m = RE_PROPOSED_MOC_HEADER.match(line)
        if m:
            if current_block:
                moc_blocks.append(current_block)
            current_block = [line]
        elif current_block:
            current_block.append(line)

    if current_block:
        moc_blocks.append(current_block)

    for idx, block in enumerate(moc_blocks, start=1):
        name = ""
        parent = ""
        items_str = ""
        approved = False
        tags: list[str] = []

        for line in block:
            stripped = line.strip()

            # Check for approve/skip checkboxes — only the checked one matters
            cb_checked = RE_CHECKED.match(stripped)
            cb_unchecked = RE_UNCHECKED.match(stripped)
            if cb_checked:
                cb_text = cb_checked.group(1).lower()
                if "approve" in cb_text:
                    approved = True
            elif cb_unchecked:
                # Only unchecked approve line can revoke approval
                cb_text = cb_unchecked.group(1).lower()
                if "approve" in cb_text:
                    approved = False

            # Parse fields
            field_line = stripped
            if field_line.startswith("- "):
                field_line = field_line[2:].strip()
            m = RE_FIELD.match(field_line)
            if m:
                key = m.group(1).strip().rstrip(":").strip().lower()
                val = m.group(2).strip()
                # Strip edit hints
                if "←" in val:
                    val = val[:val.index("←")].strip()
                if key == "name":
                    name = val
                elif key == "parent":
                    wl = _extract_wikilink(val)
                    parent = wl or val
                elif key in ("supporting items", "items"):
                    items_str = val
                elif key in ("tags", "tag", "new tags", "suggested tags"):
                    tags = _parse_tags(val)

        if not approved or not name:
            continue

        # Derive MOC destination from parent path or default to Maps folder
        parent_stem = parent.rsplit("/", 1)[-1] if parent else ""
        if parent_stem.endswith(".md"):
            parent_stem = parent_stem[:-3]

        moc_id = f"MOC{idx:02d}"
        mocs.append({
            "id": moc_id,
            "source_path": None,
            "type": "moc",
            "approved": True,
            "delete_source": False,
            "action": "create_moc",
            "title": name,
            "tags": tags,
            "parent_moc": parent,
            "parent_mocs": [parent] if parent else [],
            "destination": "Atlas/200 Maps/",
            "template": config_template,
            "summary": None,
            "classification": None,
            "supporting_items": items_str,
        })

    return mocs


# ──────────────────────────────────────────────────────────────────────────────
# MOC proposal-doc parser  (F-43 T4.1)
# ──────────────────────────────────────────────────────────────────────────────

# Frontmatter YAML block extractor
RE_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _extract_frontmatter(text: str) -> dict[str, str]:
    """Extract key→value pairs from a YAML frontmatter block.

    Returns a flat dict of string values.  No full YAML parse — just
    simple `key: value` lines (sufficient for frontmatter dispatch).
    """
    m = RE_FRONTMATTER.match(text)
    if not m:
        return {}
    result: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip()
    return result


def _parse_children_list(section_text: str) -> list[str]:
    """Return all `[x]`-ticked wikilink stems from a Children section.

    Handles lines like:
        - [x] `[[note-stem]]` (annotation text)
        - [x] [[note-stem]]

    Only checked items are extracted; unchecked `[ ]` lines are ignored.
    """
    stems: list[str] = []
    for line in section_text.splitlines():
        if not RE_CHECKED.match(line.strip()):
            continue
        wl = RE_WIKILINK.search(line)
        if wl:
            stems.append(wl.group(1).strip())
    return stems


def _extract_tomo_doc_type(text: str) -> str | None:
    """Return the value of ``tomo.doc_type`` from a nested YAML frontmatter block.

    The ``tomo:`` key introduces an indented sub-block; standard flat-key
    parsing misses nested values.  This helper scans within the frontmatter
    for a ``tomo:`` section and reads the first ``doc_type:`` line indented
    under it.
    """
    m = RE_FRONTMATTER.match(text)
    if not m:
        return None
    in_tomo = False
    for line in m.group(1).splitlines():
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if not in_tomo:
            if stripped.startswith("tomo:"):
                in_tomo = True
            continue
        # Inside the tomo: sub-block — exit when a non-indented key appears
        if indent == 0 and stripped and not stripped.startswith("#"):
            break
        if stripped.startswith("doc_type:"):
            _, _, v = stripped.partition(":")
            return v.strip()
    return None


def _is_moc_proposal_doc(text: str, filename: str = "") -> bool:
    """Return True when the document is a MOC proposal-doc.

    Dispatch criteria (first match wins, in priority order):
    1. (PRIMARY) frontmatter ``tomo.doc_type: moc-proposal``
    2. (FALLBACK) filename matches either of the two known patterns:
       - new: ``<YYYY-MM-DD>_<HHMM>_moc-proposal-<slug>.md``
       - old: ``tomo-moc-proposal-<YYYYMMDD>-<HHMM>-<slug>.md``
       Both are accepted so that files produced before the convention
       alignment (suggestions-reducer.py L558-561) still match.
    3. (FALLBACK) frontmatter ``type: tomo-proposal``
    """
    if _extract_tomo_doc_type(text) == "moc-proposal":
        return True
    basename = os.path.basename(filename)
    if basename.startswith("tomo-moc-proposal-"):  # old pattern
        return True
    if "_moc-proposal-" in basename and basename.endswith(".md"):  # new pattern
        return True
    fm = _extract_frontmatter(text)
    return fm.get("type") == "tomo-proposal"


# RE for the Cluster field:  **Cluster:** N Notes — kw1, kw2, kw3
RE_CLUSTER_LINE = re.compile(
    r"\*\*Cluster:\*\*\s*\d+\s+Notes\s*[—–-]+\s*(.*)", re.IGNORECASE
)

# RE for children wikilinks: - [x] `[[stem]]` or - [ ] `[[stem]]`
RE_CHILD_WIKILINK = re.compile(r"`?\[\[([^\]]+)\]\]`?")


def _split_moc_blocks(lines: list[str]) -> list[tuple[str, str, list[str]]]:
    """Split document lines into ``### MOCxx`` blocks.

    Returns a list of ``(moc_id, title, block_lines)`` tuples — one per
    ``### MOCxx — Title`` header found.  A block ends when the next MOC header
    or an h1/h2 section boundary is encountered.
    """
    moc_blocks: list[tuple[str, str, list[str]]] = []
    current_moc_id: str | None = None
    current_moc_title: str = ""
    current_moc_lines: list[str] = []

    for line in lines:
        m = RE_MOC_SECTION_HEADER.match(line)
        if m:
            if current_moc_id is not None:
                moc_blocks.append((current_moc_id, current_moc_title, current_moc_lines))
            current_moc_id = m.group(1).upper()
            current_moc_title = m.group(2).strip()
            current_moc_lines = []
        elif current_moc_id is not None:
            if line.startswith("## ") or line.startswith("# "):
                moc_blocks.append((current_moc_id, current_moc_title, current_moc_lines))
                current_moc_id = None
                current_moc_lines = []
            else:
                current_moc_lines.append(line)

    if current_moc_id is not None:
        moc_blocks.append((current_moc_id, current_moc_title, current_moc_lines))

    return moc_blocks


def enumerate_all_moc_sections(
    content: str,
) -> list[tuple[str, str, list[str], list[str]]]:
    """Return ALL ``### MOCxx`` sections from a proposal-doc, accepted or not.

    Each tuple is ``(moc_id, title, candidate_stems, topic_keywords)`` extracted
    from the rendered body.  Used by the squelch-persist helper (T5.2) to identify
    rejected clusters (enumerate_all − accepted).

    Extraction strategy:
    - ``candidate_stems``  — wikilinks from ``#### Children`` items
    - ``topic_keywords``   — comma-separated list from ``**Cluster:** N Notes — kw1, kw2``
    """
    lines = content.splitlines()
    results: list[tuple[str, str, list[str], list[str]]] = []

    moc_blocks = _split_moc_blocks(lines)

    # ── Extract stems + keywords from each block ─────────────────────────────
    for moc_id, title, block_lines in moc_blocks:
        topic_keywords: list[str] = []
        candidate_stems: list[str] = []
        in_children_section = False

        for bl in block_lines:
            stripped = bl.strip()

            # **Cluster:** N Notes — kw1, kw2, kw3
            cm = RE_CLUSTER_LINE.search(stripped)
            if cm:
                raw_kws = cm.group(1).strip()
                topic_keywords = [k.strip() for k in raw_kws.split(",") if k.strip()]
                continue

            # #### Children section
            if re.match(r"^####\s+Children", stripped, re.IGNORECASE):
                in_children_section = True
                continue
            if in_children_section and stripped.startswith("####"):
                in_children_section = False
                continue
            if in_children_section:
                wl = RE_CHILD_WIKILINK.search(bl)
                if wl:
                    candidate_stems.append(wl.group(1).strip())

        results.append((moc_id, title, candidate_stems, topic_keywords))

    return results


def enumerate_moc_sections_split(
    content: str,
) -> tuple[list[dict], list[dict]]:
    """Split a proposal-doc's MOC sections into ticked and unticked clusters.

    Each returned cluster dict contains:
        moc_id          — e.g. "MOC01"
        title           — heading title string
        children        — list of wikilink stem strings from #### Children
        candidate_stems — same list (alias for topic_signature computation)
        topic_keywords  — list from **Cluster:** N Notes — kw1, kw2 line
        topic_signature — 16-char hex from topic_signature.compute_topic_signature

    Returns ``(ticked, unticked)`` where each element is a list of such dicts.
    A cluster is ticked when its block contains ``- [x] Accept`` (case-insensitive).

    Used by the F-47 MOC-consumption branch to dispatch instruction-builder
    and persist unticked clusters to squelch (AC-5.2).
    """
    # Lazy-import to avoid mandatory dependency for callers that don't need it.
    try:
        from lib.topic_signature import compute_topic_signature
    except ImportError:
        # Fallback for direct-module-load outside the scripts/ sys.path context.
        import sys as _sys
        import os as _os
        _lib_path = _os.path.join(_os.path.dirname(__file__), "lib")
        _sys.path.insert(0, _lib_path)
        from topic_signature import compute_topic_signature  # type: ignore[no-redef]

    lines = content.splitlines()
    moc_blocks = _split_moc_blocks(lines)

    ticked: list[dict] = []
    unticked: list[dict] = []

    for moc_id, title, block_lines in moc_blocks:
        # ── Accept check ─────────────────────────────────────────────────────
        is_ticked = any(
            RE_CHECKED.match(bl.strip()) and
            RE_CHECKED.match(bl.strip()).group(1).strip().lower() == "accept"
            for bl in block_lines
        )

        # ── Extract topic_keywords ────────────────────────────────────────────
        topic_keywords: list[str] = []
        for bl in block_lines:
            cm = RE_CLUSTER_LINE.search(bl.strip())
            if cm:
                raw_kws = cm.group(1).strip()
                topic_keywords = [k.strip() for k in raw_kws.split(",") if k.strip()]
                break

        # ── Extract children from #### Children section ───────────────────────
        children: list[str] = []
        in_children = False
        for bl in block_lines:
            stripped = bl.strip()
            if re.match(r"^####\s+Children", stripped, re.IGNORECASE):
                in_children = True
                continue
            if in_children and stripped.startswith("####"):
                break
            if in_children:
                wl = RE_CHILD_WIKILINK.search(bl)
                if wl:
                    children.append(wl.group(1).strip())

        # ── Build cluster dict ────────────────────────────────────────────────
        cluster: dict = {
            "moc_id": moc_id,
            "title": title,
            "children": children,
            "candidate_stems": children,  # children ARE the candidate stems here
            "topic_keywords": topic_keywords,
        }
        cluster["topic_signature"] = compute_topic_signature(cluster)

        if is_ticked:
            ticked.append(cluster)
        else:
            unticked.append(cluster)

    return ticked, unticked


def parse_moc_proposal_doc(content: str, filename: str = "") -> list[dict]:
    """Parse a MOC proposal-doc and return a list of ConfirmedMOCProposal dicts.

    Each accepted cluster (``- [x] Accept``) produces one entry:
    {
        "moc_id":                       str,   # e.g. "MOC01"
        "title":                        str,
        "location":                     str,
        "template":                     str,
        "parent":                       str | None,
        "children":                     list[str],
        "override_preserve_existing_up": bool,
    }

    Skips clusters whose ``- [ ] Accept`` is unchecked.
    Returns [] when no clusters are accepted.
    """
    lines = content.splitlines()
    proposals: list[dict] = []

    # ── Split into ### MOCxx sections ────────────────────────────────────────
    moc_blocks = _split_moc_blocks(lines)

    # ── Parse each block ────────────────────────────────────────────────────
    for moc_id, heading_title, block_lines in moc_blocks:
        # ── Accept gate ──────────────────────────────────────────────────────
        accepted = False
        for bl in block_lines:
            cb = RE_CHECKED.match(bl.strip())
            if cb and cb.group(1).strip().lower() == "accept":
                accepted = True
                break
        if not accepted:
            continue

        # ── Title field (may be edited inline) ───────────────────────────────
        title = heading_title  # fallback
        for bl in block_lines:
            stripped = bl.strip()
            field_line = stripped[2:].strip() if stripped.startswith("- ") else stripped
            fm = RE_FIELD.match(field_line)
            if fm:
                key = fm.group(1).strip().rstrip(":").strip().lower()
                val = fm.group(2).strip()
                if key == "title":
                    # Strip backticks
                    title = val.strip("`")
                    break

        # ── Location field ────────────────────────────────────────────────────
        location: str = "Atlas/200 Maps/"
        for bl in block_lines:
            stripped = bl.strip()
            field_line = stripped[2:].strip() if stripped.startswith("- ") else stripped
            fm = RE_FIELD.match(field_line)
            if fm:
                key = fm.group(1).strip().rstrip(":").strip().lower()
                val = fm.group(2).strip()
                if key in ("location", "destination"):
                    location = val.strip("`")
                    break

        # ── Template field ────────────────────────────────────────────────────
        template: str = ""
        for bl in block_lines:
            stripped = bl.strip()
            field_line = stripped[2:].strip() if stripped.startswith("- ") else stripped
            fm = RE_FIELD.match(field_line)
            if fm:
                key = fm.group(1).strip().rstrip(":").strip().lower()
                val = fm.group(2).strip()
                if key == "template":
                    # Strip wikilink brackets and backticks
                    wl = _extract_wikilink(val)
                    template = (wl or val).strip("`").strip()
                    break

        # ── Parent section (#### Parent) — first [x] wins ────────────────────
        parent: str | None = None
        in_parent_section = False
        for bl in block_lines:
            stripped = bl.strip()
            if stripped.startswith("#### Parent"):
                in_parent_section = True
                continue
            if in_parent_section and stripped.startswith("####"):
                # Next sub-section ends Parent block
                in_parent_section = False
                continue
            if in_parent_section:
                cb = RE_CHECKED.match(stripped)
                if cb:
                    cb_text = cb.group(1).strip()
                    # Skip "kein parent" option
                    if "kein parent" not in cb_text.lower():
                        wl = RE_WIKILINK.search(cb_text)
                        if wl:
                            parent = wl.group(1).strip()
                        else:
                            # up:: `[[stem]]` pattern: extract from backtick wikilink
                            bk = re.search(r"`\[\[([^\]]+)\]\]`", cb_text)
                            if bk:
                                parent = bk.group(1).strip()
                        if parent:
                            break  # first checked wins

        # ── Children section (#### Children) — all [x] ───────────────────────
        children: list[str] = []
        in_children_section = False
        children_lines: list[str] = []
        for bl in block_lines:
            stripped = bl.strip()
            if re.match(r"^####\s+Children", stripped, re.IGNORECASE):
                in_children_section = True
                continue
            if in_children_section and stripped.startswith("####"):
                in_children_section = False
                continue
            if in_children_section:
                children_lines.append(bl)
        children = _parse_children_list("\n".join(children_lines))

        # ── Override toggle (#### up::-Handling Override) ─────────────────────
        override_preserve = False
        in_override_section = False
        for bl in block_lines:
            stripped = bl.strip()
            if re.match(r"^####\s+up::.*Override", stripped, re.IGNORECASE):
                in_override_section = True
                continue
            if in_override_section and stripped.startswith("####"):
                in_override_section = False
                continue
            if in_override_section:
                cb = RE_CHECKED.match(stripped)
                if cb:
                    cb_text = cb.group(1).lower()
                    if ("behalten" in cb_text or "keep" in cb_text
                            or "preserve" in cb_text or "related" in cb_text):
                        override_preserve = True
                        break

        proposals.append({
            "moc_id": moc_id,
            "title": title,
            "location": location,
            "template": template,
            "parent": parent,
            "children": children,
            "override_preserve_existing_up": override_preserve,
        })

    return proposals


# ──────────────────────────────────────────────────────────────────────────────
# Daily Notes Updates parser
# ──────────────────────────────────────────────────────────────────────────────

RE_DAILY_DATE_HEADER = re.compile(r"^###\s+\[\[([^\]]+)\]\]")
RE_DAILY_TRACKER_LINE = re.compile(r"^\s*-\s+\*\*([^*]+)\*\*\s*→\s*`?([^`\n]+)`?")
RE_DAILY_LOG_LINE = re.compile(r"^\s*-\s+(.+?)\s+—\s+(.*)")
RE_TIME_HH_MM = re.compile(r"^\d{1,2}:\d{2}$")

POSITION_TOKENS = {"after_last_line", "before_first_line"}


def _parse_time_position(raw: str) -> tuple[str | None, str]:
    """Parse a time/position string into (time, position).

    Returns:
        (time, position) where:
        - "10:00" → ("10:00", "at_time")
        - "after_last_line" → (None, "after_last_line")
        - "before_first_line" → (None, "before_first_line")
        - "end of day" (legacy) → (None, "after_last_line")
        - anything else → (None, "after_last_line")
    """
    if RE_TIME_HH_MM.match(raw):
        return raw, "at_time"
    if raw in POSITION_TOKENS:
        return None, raw
    # Legacy fallback: "end of day" or any unrecognized string
    return None, "after_last_line"


def parse_daily_updates(text: str) -> list[dict]:
    """Parse the ## Daily Notes Updates section.

    Returns a list of daily update entries:
    [{date, trackers: [{field, value, reason, source_stem, accepted}],
      log_entries: [{time, content, reason, source_stem, accepted}]}]
    """
    lines = text.splitlines()
    in_section = False
    entries: list[dict] = []
    current_date: str | None = None
    current_entry: dict | None = None
    block_type: str | None = None  # "trackers", "log_entries", "log_links"
    pending_item: dict | None = None

    def _flush_pending():
        nonlocal pending_item
        if pending_item and current_entry:
            if block_type and block_type in current_entry:
                current_entry[block_type].append(pending_item)
        pending_item = None

    for line in lines:
        stripped = line.strip()

        if stripped == "## Daily Notes Updates":
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            _flush_pending()
            break
        if not in_section:
            continue

        # Date header: ### [[2026-03-26]]
        dm = RE_DAILY_DATE_HEADER.match(stripped)
        if dm:
            _flush_pending()
            current_date = dm.group(1)
            # Reuse existing entry for this date (same date can appear
            # with trackers first, then log entries in a later block)
            existing = next((e for e in entries if e["date"] == current_date), None)
            if existing:
                current_entry = existing
            else:
                current_entry = {
                    "date": current_date,
                    "trackers": [],
                    "log_entries": [],
                    "log_links": [],
                }
                entries.append(current_entry)
            block_type = None
            continue

        if not current_entry:
            continue

        # Block type headers
        if stripped.startswith("**Possible Trackers:**"):
            _flush_pending()
            block_type = "trackers"
            continue
        if stripped.startswith("**Possible Log Entries"):
            _flush_pending()
            block_type = "log_entries"
            continue
        if stripped.startswith("**Possible Log Links"):
            _flush_pending()
            block_type = "log_links"
            continue

        # Accept checkbox for the current pending item
        cb = RE_CHECKED.match(stripped)
        if cb and "accept" in cb.group(1).lower():
            if pending_item:
                pending_item["accepted"] = True
            continue
        cb_un = RE_UNCHECKED.match(stripped)
        if cb_un and "accept" in cb_un.group(1).lower():
            if pending_item:
                pending_item["accepted"] = False
            continue

        # Force Atomic Note checkbox — log_entry only. When checked, the
        # source note gets promoted to a confirmed create_atomic_note even
        # if the per-item section's own Approve box is empty. Captured
        # here as a hint; the main() function reconciles against the
        # per-item sections at the end.
        if cb and "force atomic note" in cb.group(1).lower():
            if pending_item and block_type == "log_entries":
                pending_item["force_atomic_note"] = True
            continue
        if cb_un and "force atomic note" in cb_un.group(1).lower():
            if pending_item and block_type == "log_entries":
                pending_item["force_atomic_note"] = False
            continue

        # Sub-fields: Reason, Source, Time
        if stripped.startswith("- Reason:") and pending_item:
            pending_item["reason"] = stripped.split(":", 1)[1].strip()
            continue
        if stripped.startswith("- Source:") and pending_item:
            wl = _extract_wikilink(stripped)
            if wl:
                pending_item["source_stem"] = wl
            continue
        if stripped.startswith("- Time:") and pending_item:
            pending_item["time"] = stripped.split(":", 1)[1].strip()
            continue

        # Tracker line: - **Sport** → `true`
        if block_type == "trackers":
            tm = RE_DAILY_TRACKER_LINE.match(stripped)
            if tm:
                _flush_pending()
                pending_item = {
                    "field": tm.group(1).strip(),
                    "value": tm.group(2).strip(),
                    "reason": "",
                    "source_stem": "",
                    "accepted": False,
                }
                continue

        # Log entry line: - after_last_line — content  OR  - 10:00 — content
        if block_type in ("log_entries", "log_links"):
            lm = RE_DAILY_LOG_LINE.match(stripped)
            if lm:
                _flush_pending()
                raw_time = lm.group(1).strip()
                time_val, position_val = _parse_time_position(raw_time)
                if block_type == "log_entries":
                    pending_item = {
                        "time": time_val,
                        "position": position_val,
                        "content": lm.group(2).strip(),
                        "reason": "",
                        "source_stem": "",
                        "accepted": False,
                        # Populated when the user ticks the per-entry
                        # "Force Atomic Note" checkbox — default off.
                        "force_atomic_note": False,
                    }
                elif block_type == "log_links":
                    wl = _extract_wikilink(stripped)
                    pending_item = {
                        "target_stem": wl or raw_time,
                        "time": time_val,
                        "position": position_val,
                        "reason": "",
                        "accepted": False,
                    }
                continue

    _flush_pending()
    return entries


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Parse a confirmed Tomo suggestions document and output approved "
            "items as JSON."
        )
    )
    parser.add_argument(
        "--file",
        metavar="PATH",
        help="Path to the suggestions markdown file (defaults to stdin)",
    )
    parser.add_argument(
        "--fan-resolve-file",
        metavar="PATH",
        help=(
            "Optional companion fan-resolve suggestions doc. When provided, "
            "its approved per-item atomic sections are merged into the "
            "primary doc's FAN log_entries by stem (XDD 012)."
        ),
    )
    args = parser.parse_args()

    # ── Read input ────────────────────────────────────────────────
    try:
        if args.file:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read()
        else:
            text = sys.stdin.read()
    except OSError as exc:
        print(f"error: cannot read input: {exc}", file=sys.stderr)
        return 1

    if not text.strip():
        print("error: input is empty", file=sys.stderr)
        return 1

    # ── Pre-parse dispatch: MOC proposal-doc (F-43 T4.1) ─────────
    filename = args.file or ""
    if _is_moc_proposal_doc(text, filename=filename):
        proposals = parse_moc_proposal_doc(text, filename=filename)
        print(json.dumps(proposals, ensure_ascii=False, indent=2))
        return 0

    # ── Split and parse ───────────────────────────────────────────
    raw_sections = split_into_sections(text)

    if not raw_sections:
        print("warning: no S## sections found in document", file=sys.stderr)

    confirmed_items: list[dict] = []
    skipped_items: list[dict] = []
    total_sections = len(raw_sections)

    def _stem_of(src: str | None) -> str:
        """Lowercase stem for source_path/source_stem matching — handles
        paths with folders, .md suffixes, and wikilink aliases."""
        if not src:
            return ""
        bare = src.rsplit("/", 1)[-1]
        if bare.endswith(".md"):
            bare = bare[:-3]
        return bare.strip().lower()

    # Keep parsed sections by stem so the Force-Atomic reconciliation pass
    # can promote unapproved items later.
    parsed_sections: list[dict] = []
    sections_by_stem: dict[str, dict] = {}

    for section_id, lines in raw_sections:
        try:
            item = parse_section(section_id, lines)
        except Exception as exc:  # noqa: BLE001
            print(
                f"warning: skipping {section_id} — parse error: {exc}",
                file=sys.stderr,
            )
            skipped_items.append({"id": section_id, "disposition": "error"})
            continue

        if item is None:
            print(
                f"warning: skipping {section_id} — returned None",
                file=sys.stderr,
            )
            skipped_items.append({"id": section_id, "disposition": "error"})
            continue

        parsed_sections.append(item)
        stem_key = _stem_of(item.get("source_path"))
        if stem_key:
            sections_by_stem[stem_key] = item

        if item["approved"]:
            confirmed_items.append({
                "id": item["id"],
                "source_path": item["source_path"],
                "type": item["type"],
                "approved": item["approved"],
                "delete_source": item["delete_source"],
                "keep_origin": item["keep_origin"],
                "action": item["action"],
                "title": item["title"],
                "tags": item["tags"],
                "parent_moc": item["parent_moc"],
                "parent_mocs": item["parent_mocs"],
                "destination": item["destination"],
                "template": item["template"],
                "summary": item["summary"],
                "classification": item["classification"],
            })
        else:
            disposition = "delete_source" if item["delete_source"] else "skip"
            skipped_items.append({
                "id": section_id,
                "source_path": item["source_path"],
                "disposition": disposition,
            })

    # ── Parse Proposed MOCs ────────────────────────────────────
    # Load MOC template path from vault-config if available
    moc_template = ""
    try:
        import os
        config_path = os.path.join(os.getcwd(), "config", "vault-config.yaml")
        if os.path.isfile(config_path):
            try:
                import yaml
                with open(config_path, encoding="utf-8") as cf:
                    cfg = yaml.safe_load(cf) or {}
                moc_template = (cfg.get("templates", {}).get("mapping", {})
                                .get("map_note", ""))
            except Exception:
                pass
    except Exception:
        pass

    proposed_mocs = parse_proposed_mocs(text, config_template=moc_template)
    if proposed_mocs:
        confirmed_items.extend(proposed_mocs)
        print(
            f"proposed_mocs: {len(proposed_mocs)} approved",
            file=sys.stderr,
        )

    # ── Parse Daily Notes Updates ─────────────────────────────
    daily_updates = parse_daily_updates(text)
    if daily_updates:
        accepted_count = sum(
            1 for d in daily_updates
            for lst in (d.get("trackers", []), d.get("log_entries", []), d.get("log_links", []))
            for item in lst if item.get("accepted")
        )
        print(
            f"daily_updates: {len(daily_updates)} dates, {accepted_count} accepted items",
            file=sys.stderr,
        )

    # ── Parse companion FAN-resolve doc (XDD 012) ───────────────
    # When the user approved a <date>_suggestions-fan.md in addition to
    # the primary doc, its approved atomic sections carry the proposals
    # generated by the force_atomic=true Pass-2 subflow. Parse them into
    # a {stem → section} map so the reconciliation pass below can pick
    # them up for FAN log_entries that had no primary-doc section.
    resolve_sections_by_stem: dict[str, dict] = {}
    if args.fan_resolve_file:
        try:
            with open(args.fan_resolve_file, encoding="utf-8") as fh:
                resolve_text = fh.read()
        except OSError as exc:
            print(
                f"warning: cannot read --fan-resolve-file "
                f"{args.fan_resolve_file}: {exc}",
                file=sys.stderr,
            )
            resolve_text = ""
        if resolve_text.strip():
            for section_id, lines in split_into_sections(resolve_text):
                try:
                    item = parse_section(section_id, lines)
                except Exception as exc:  # noqa: BLE001
                    print(
                        f"warning: resolve-doc {section_id} parse error: {exc}",
                        file=sys.stderr,
                    )
                    continue
                if item is None:
                    continue
                # Only approved atomic sections count. Unchecked = user
                # hasn't accepted the proposal yet.
                if not item.get("approved"):
                    continue
                stem_key = _stem_of(item.get("source_path"))
                if stem_key:
                    resolve_sections_by_stem[stem_key] = item

    # ── Reconcile Force Atomic Note promotions ─────────────────
    # When the user ticks [x] Force Atomic Note on a log_entry, they're
    # saying "also create a standalone note for this source," even if
    # the per-item section's own Approve box is empty. Three-way lookup:
    #   (a) primary-doc per-item section (legacy promote path, commit 2665f81)
    #   (b) resolve-doc atomic section (XDD 012 new path)
    #   (c) neither → pending_fan_resolutions[] (Pass 2 will trigger the
    #       resolve subflow to generate (b) for next run)
    force_atomic_stems: list[tuple[str, dict]] = []  # preserve order + log_entry ref
    for d in daily_updates:
        for le in d.get("log_entries", []):
            if le.get("force_atomic_note"):
                stem = _stem_of(le.get("source_stem"))
                if stem:
                    force_atomic_stems.append((stem, le))

    promoted = 0
    from_resolve = 0
    pending_fan_resolutions: list[dict] = []
    already_in = {_stem_of(c.get("source_path")) for c in confirmed_items}
    seen_pending: set[str] = set()
    for stem, log_entry in force_atomic_stems:
        if stem in already_in:
            continue  # user already checked per-item Approve — Force is a no-op

        # Branch (a): primary-doc per-item section
        sec = sections_by_stem.get(stem)
        from_resolve_flag = False
        if sec is None:
            # Branch (b): resolve-doc atomic section
            sec = resolve_sections_by_stem.get(stem)
            from_resolve_flag = sec is not None

        if sec is not None:
            # Promote: mark approved, clear delete_source.
            sec["approved"] = True
            sec["delete_source"] = False
            entry = {
                "id": sec["id"],
                "source_path": sec["source_path"],
                "type": sec["type"],
                "approved": True,
                "delete_source": False,
                "keep_origin": bool(sec.get("keep_origin", False)),
                "action": sec.get("action"),
                "title": sec["title"],
                "tags": sec["tags"],
                "parent_moc": sec["parent_moc"],
                "parent_mocs": sec["parent_mocs"],
                "destination": sec["destination"],
                "template": sec["template"],
                "summary": sec["summary"],
                "classification": sec["classification"],
                "force_atomic": True,  # trace marker for instruction-render logs
            }
            if from_resolve_flag:
                entry["from_resolve"] = True
                from_resolve += 1
            else:
                promoted += 1
            confirmed_items.append(entry)
            already_in.add(stem)
            # Drop the matching skipped entry (if any) so counts stay clean.
            skipped_items[:] = [
                s for s in skipped_items
                if _stem_of(s.get("source_path")) != stem
            ]
        else:
            # Branch (c): no matching section anywhere. Record the item so
            # Pass 2 can trigger the resolve subflow next.
            if stem in seen_pending:
                continue
            seen_pending.add(stem)
            # Pull a short summary from the log entry content (first 140
            # chars) for the resolve-doc writer to display.
            summary = (log_entry.get("content") or "").strip()
            if len(summary) > 140:
                summary = summary[:137] + "…"
            pending_fan_resolutions.append({
                "stem": stem,
                # Reconstruct a best-effort source_path; log_entry may only
                # carry source_stem. Pass 2 will verify via kado-search.
                "source_path": log_entry.get("source_path") or f"{stem}.md",
                "log_entry_summary": summary,
            })

    if promoted:
        print(
            f"force_atomic: promoted {promoted} per-item section(s) to confirmed",
            file=sys.stderr,
        )
    if from_resolve:
        print(
            f"force_atomic: merged {from_resolve} atomic(s) from resolve doc",
            file=sys.stderr,
        )
    if pending_fan_resolutions:
        print(
            f"force_atomic: {len(pending_fan_resolutions)} log entries have "
            "Force Atomic Note but no atomic proposal — resolve subflow will "
            "be triggered by Pass 2.",
            file=sys.stderr,
        )

    output = {
        "confirmed_items": confirmed_items,
        "daily_updates": daily_updates,
        "skipped": skipped_items,
        # XDD 012: items with FAN-without-section that Pass 2 must
        # resolve via a follow-up subflow. Empty list when nothing pending.
        "pending_fan_resolutions": pending_fan_resolutions,
        "total_sections": total_sections,
        "total_approved": len(confirmed_items),
        "total_skipped": len(skipped_items),
    }

    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
