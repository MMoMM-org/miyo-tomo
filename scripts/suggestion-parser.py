#!/usr/bin/env python3
# version: 0.1.0
"""
suggestion-parser.py — Parse a confirmed Tomo suggestions document.

Reads a MiYo-Tomo suggestions markdown file (tagged #MiYo-Tomo/confirmed) and
extracts user-approved items with any modifications they made to fields,
alternatives, and action checkboxes.

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

# Section header: ### S01: some-note.md  OR  ## S01 — some-note.md
RE_SECTION_HEADER = re.compile(r"^#{2,3}\s+(S\d+)[:\s—–-]+", re.IGNORECASE)

# Checkbox lines
RE_CHECKED = re.compile(r"^\s*-\s+\[x\]\s*(.*)", re.IGNORECASE)
RE_UNCHECKED = re.compile(r"^\s*-\s+\[\s\]\s*(.*)", re.IGNORECASE)

# Bold field: **Name:** value
RE_FIELD = re.compile(r"^\s*\*\*([^*]+)\*\*[:\s]+(.+)")

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
    Parse one S## section and return a structured dict, or None on fatal error.

    The section format (from spec) is:

        ### S01: some-note.md

        **Source:** `+/some-note.md`
        **Type:** fleeting_note (confidence: 0.85)

        **Primary Suggestion:**
        - [x] Create atomic note "Some Topic" in Atlas/202 Notes/
        - **Title:** Some Topic
        - **Tags:** topic/knowledge, type/note/normal
        - **Parent MOC:** [[Knowledge Management]]
        - **Classification:** 2600 Applied Sciences

        **Alternatives:**
        - [ ] Link to existing [[Related Note]] instead
        - [ ] File as quote under [[Quotes]]

        **Actions:**
        - [x] Approve
        - [ ] Skip
        - [ ] Delete source after processing
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
        "classification": None,
        "alternative_selected": None,
    }

    # ── Zone tracking ──────────────────────────────────────────────
    # Zones: top / primary / alternatives / actions
    zone = "top"
    primary_action_checked = False
    primary_fields: dict = {}
    alternatives: list[dict] = []  # [{"checked": bool, "text": str}]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # ── Zone transitions ───────────────────────────────────────
        lower = stripped.lower()

        if re.match(r"\*\*primary", lower) or re.match(r"###\s+primary", lower):
            zone = "primary"
            continue
        if re.match(r"\*\*alternative", lower) or re.match(r"###\s+alternative", lower):
            zone = "alternatives"
            continue
        if re.match(r"\*\*action", lower) or re.match(r"###\s+action", lower):
            zone = "actions"
            continue
        # "Why these suggestions" — ignore the rest
        if re.match(r"\*\*why|###\s+why", lower):
            break

        # ── Parse by zone ──────────────────────────────────────────

        if zone == "top":
            # **Source:** `+/path.md`
            m = RE_FIELD.match(stripped)
            if m:
                key = m.group(1).strip().lower()
                val = m.group(2).strip()
                if key == "source":
                    src = RE_SOURCE.search(val)
                    if src:
                        result["source_path"] = src.group(1) or src.group(2)
                    else:
                        # Try wikilink
                        wl = _extract_wikilink(val)
                        result["source_path"] = wl or val
                elif key == "type":
                    tm = RE_TYPE.match(val)
                    result["type"] = tm.group(1) if tm else val.split()[0]
            continue

        if zone == "primary":
            # First checkbox line in primary zone = the primary action
            cb_match_checked = RE_CHECKED.match(stripped)
            cb_match_any = RE_UNCHECKED.match(stripped) or cb_match_checked

            if cb_match_any and result["action"] is None:
                # This is the primary action checkbox
                text = _checkbox_text(stripped)
                primary_action_checked = bool(cb_match_checked)
                result["action"] = _normalise_action(text)
                # Title hint may be in the same line: 'Create atomic note "Some Topic"'
                title_m = re.search(r'"([^"]+)"', text)
                if title_m:
                    primary_fields["title"] = title_m.group(1)
                continue

            # Field lines inside primary: - **Title:** Some Topic
            m = RE_FIELD.match(stripped)
            if m:
                key = m.group(1).strip().lower()
                val = m.group(2).strip()
                if key in ("title",):
                    primary_fields["title"] = val
                elif key in ("tags", "tag"):
                    primary_fields["tags"] = _parse_tags(val)
                elif key in ("parent moc", "parent_moc", "parentmoc"):
                    wl = _extract_wikilink(val)
                    primary_fields["parent_moc"] = wl or val
                elif key in ("classification",):
                    primary_fields["classification"] = val
            continue

        if zone == "alternatives":
            cb_checked = RE_CHECKED.match(stripped)
            cb_unchecked = RE_UNCHECKED.match(stripped)
            if cb_checked or cb_unchecked:
                text = _checkbox_text(stripped)
                alternatives.append({
                    "checked": bool(cb_checked),
                    "text": text,
                })
            continue

        if zone == "actions":
            cb_checked = RE_CHECKED.match(stripped)
            cb_unchecked = RE_UNCHECKED.match(stripped)
            if cb_checked or cb_unchecked:
                text = _checkbox_text(stripped).lower()
                if "approve" in text:
                    result["approved"] = bool(cb_checked)
                elif "delete source" in text or "delete" in text:
                    result["delete_source"] = bool(cb_checked)
            continue

    # ── Resolve primary vs alternative ────────────────────────────

    # Check if any alternative was selected
    selected_alt = next((a for a in alternatives if a["checked"]), None)

    if selected_alt:
        # User picked an alternative — override primary action
        result["alternative_selected"] = selected_alt["text"]
        result["action"] = _normalise_action(selected_alt["text"])
        # Don't carry over primary fields; alternative text may contain a wikilink
        wl = _extract_wikilink(selected_alt["text"])
        if wl:
            result["title"] = wl
    else:
        # Use primary fields if primary was checked (or action was already set)
        if primary_action_checked or result["action"]:
            result["title"] = primary_fields.get("title")
            result["tags"] = primary_fields.get("tags", [])
            result["parent_moc"] = primary_fields.get("parent_moc")
            result["classification"] = primary_fields.get("classification")

    # ── Delete semantics (spec §6) ─────────────────────────────────
    # Delete only meaningful when Approve is unchecked. If both checked, Approve wins.
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
            # Only include fields relevant to the output; strip internal keys
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
