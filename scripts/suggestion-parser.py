#!/usr/bin/env python3
# version: 0.3.0
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
import re
import sys


# ──────────────────────────────────────────────────────────────────────────────
# Patterns
# ──────────────────────────────────────────────────────────────────────────────

# Section header: accept both spec format (S01:) and LLM output format (A1., B1., etc.)
#   ### S01: filename.md    ### S01 — Title
#   ### A1. Title           ### B12. Another
RE_SECTION_HEADER = re.compile(r"^#{2,3}\s+([A-Z]\d+)[.:\s—–-]+", re.IGNORECASE)

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

            # Decision checkboxes (approve/skip/delete)
            text_lower = text.lower()
            if "accept" in text_lower or "approve" in text_lower:
                result["approved"] = bool(cb_checked)
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
            current_lines.append(line)

    if current_id is not None:
        sections.append((current_id, current_lines))

    return sections


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

    # ── Split and parse ───────────────────────────────────────────
    raw_sections = split_into_sections(text)

    if not raw_sections:
        print("warning: no S## sections found in document", file=sys.stderr)

    confirmed_items: list[dict] = []
    skipped_ids: list[str] = []
    total_sections = len(raw_sections)

    for section_id, lines in raw_sections:
        try:
            item = parse_section(section_id, lines)
        except Exception as exc:  # noqa: BLE001
            print(
                f"warning: skipping {section_id} — parse error: {exc}",
                file=sys.stderr,
            )
            skipped_ids.append(section_id)
            continue

        if item is None:
            print(
                f"warning: skipping {section_id} — returned None",
                file=sys.stderr,
            )
            skipped_ids.append(section_id)
            continue

        if item["approved"]:
            confirmed_items.append({
                "id": item["id"],
                "source_path": item["source_path"],
                "type": item["type"],
                "approved": item["approved"],
                "delete_source": item["delete_source"],
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
            skipped_ids.append(section_id)

    output = {
        "confirmed_items": confirmed_items,
        "skipped": skipped_ids,
        "total_sections": total_sections,
        "total_approved": len(confirmed_items),
        "total_skipped": len(skipped_ids),
    }

    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
