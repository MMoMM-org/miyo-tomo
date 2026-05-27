#!/usr/bin/env python3
# version: 0.2.0
"""moc-proposal-parser.py — Parse an approved MOC proposal into instruction-render input.

Reads a MOC proposal markdown doc (produced by suggestions-reducer --moc-proposal-mode)
and outputs JSON matching the format instruction-render.py expects:
  { confirmed_items, daily_updates, skipped, total_sections, total_approved, total_skipped }

Each accepted MOC section becomes a confirmed_item with action=create_moc.
Each rejected MOC section becomes a skipped entry.

CLI: python3 scripts/moc-proposal-parser.py --file <path> [> output.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RE_MOC_HEADER = re.compile(r"^###\s+(MOC\d+)\s*[—–-]\s*(.*)", re.IGNORECASE)
RE_CHECKED = re.compile(r"^\s*-\s*\[x\]\s*(.*)", re.IGNORECASE)
RE_UNCHECKED = re.compile(r"^\s*-\s*\[\s\]\s*(.*)")
RE_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
RE_FIELD = re.compile(r"\*\*(\w[\w\s]*):\*\*\s*(.*)")
RE_BACKTICK_VALUE = re.compile(r"`([^`]+)`")


def _extract_backtick_or_raw(val: str) -> str:
    m = RE_BACKTICK_VALUE.search(val)
    return m.group(1).strip() if m else val.strip()


def _extract_wikilink(val: str) -> str:
    m = RE_WIKILINK.search(val)
    return m.group(1).strip() if m else ""


def _split_moc_blocks(lines: list[str]) -> list[tuple[str, str, list[str]]]:
    """Split lines into (moc_id, title, block_lines) per ### MOCxx header."""
    blocks: list[tuple[str, str, list[str]]] = []
    current_id: str | None = None
    current_title: str = ""
    current_lines: list[str] = []

    for line in lines:
        m = RE_MOC_HEADER.match(line)
        if m:
            if current_id is not None:
                blocks.append((current_id, current_title, current_lines))
            current_id = m.group(1).strip()
            current_title = m.group(2).strip()
            current_lines = []
        elif line.startswith("## ") or line.startswith("# "):
            if current_id is not None:
                blocks.append((current_id, current_title, current_lines))
                current_id = None
                current_lines = []
        elif current_id is not None:
            current_lines.append(line)

    if current_id is not None:
        blocks.append((current_id, current_title, current_lines))

    return blocks


def _parse_moc_block(
    moc_id: str, title: str, block_lines: list[str],
) -> dict:
    """Parse one MOC block into a confirmed_item or skipped entry."""
    accepted = False
    parsed_title = ""
    location = ""
    template = ""
    parent = ""
    children: list[str] = []
    override_preserve = False

    section = ""  # tracks #### sub-sections

    for line in block_lines:
        stripped = line.strip()

        # Track #### sections
        if stripped.startswith("#### "):
            section_name = stripped[5:].strip().lower()
            if section_name.startswith("parent"):
                section = "parent"
            elif section_name.startswith("children"):
                section = "children"
            elif "handling" in section_name and "override" in section_name:
                section = "override"
            elif section_name.startswith("why"):
                section = "why"
            else:
                section = section_name
            continue

        # Accept/skip checkbox (top of block, before sections)
        cb = RE_CHECKED.match(stripped)
        if cb and section == "":
            text = cb.group(1).strip().lower()
            if "accept" in text:
                accepted = True

        cb_un = RE_UNCHECKED.match(stripped)
        if cb_un and section == "":
            text = cb_un.group(1).strip().lower()
            if "accept" in text:
                accepted = False

        # Fields: **Key:** value
        fm = RE_FIELD.match(stripped)
        if fm and section == "":
            key = fm.group(1).strip().lower()
            val = fm.group(2).strip()
            if key == "title":
                parsed_title = _extract_backtick_or_raw(val)
            elif key == "location":
                location = _extract_backtick_or_raw(val)
            elif key == "template":
                parsed_title_ref = _extract_wikilink(val)
                if parsed_title_ref:
                    template = parsed_title_ref

        # Parent section
        if section == "parent" and RE_CHECKED.match(stripped):
            cb_text = RE_CHECKED.match(stripped).group(1)
            if "up::" in cb_text:
                wl = _extract_wikilink(cb_text)
                if wl:
                    parent = wl
            # "no parent" / "kein parent" is handled by leaving parent empty

        # Children section
        if section == "children":
            if RE_CHECKED.match(stripped):
                wl = RE_WIKILINK.search(stripped)
                if wl:
                    children.append(wl.group(1).strip())

        # Override section
        if section == "override" and RE_CHECKED.match(stripped):
            cb_text = RE_CHECKED.match(stripped).group(1).lower()
            if "behalten" in cb_text or "keep" in cb_text or "preserve" in cb_text or "related" in cb_text:
                override_preserve = True

    use_title = parsed_title or title

    if not accepted:
        return {
            "_disposition": "skipped",
            "id": moc_id,
            "title": use_title,
            "disposition": "rejected",
        }

    return {
        "_disposition": "confirmed",
        "id": moc_id,
        "source_path": None,
        "type": "moc",
        "approved": True,
        "delete_source": False,
        "action": "create_moc",
        "title": use_title,
        "tags": [],
        "parent_moc": parent,
        "parent_mocs": [parent] if parent else [],
        "destination": location or "Atlas/200 Maps/",
        "template": template,
        "summary": None,
        "classification": None,
        "supporting_items": children,
        "override_preserve_existing_up": override_preserve,
    }


def parse_moc_proposal(text: str) -> dict:
    """Parse full MOC proposal markdown into instruction-render input format."""
    lines = text.splitlines()
    blocks = _split_moc_blocks(lines)

    confirmed_items: list[dict] = []
    skipped_items: list[dict] = []

    for moc_id, title, block_lines in blocks:
        result = _parse_moc_block(moc_id, title, block_lines)
        disposition = result.pop("_disposition")
        if disposition == "confirmed":
            confirmed_items.append(result)
        else:
            skipped_items.append(result)

    return {
        "confirmed_items": confirmed_items,
        "daily_updates": [],
        "skipped": skipped_items,
        "total_sections": len(blocks),
        "total_approved": len(confirmed_items),
        "total_skipped": len(skipped_items),
    }


def main() -> int:
    p = argparse.ArgumentParser(
        description="Parse a MOC proposal doc into instruction-render input JSON.",
    )
    p.add_argument(
        "--file", type=str, required=True,
        help="Path to the MOC proposal markdown file",
    )
    args = p.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    output = parse_moc_proposal(text)

    print(
        f"moc-proposal-parser: {output['total_approved']} accepted, "
        f"{output['total_skipped']} skipped out of {output['total_sections']} sections",
        file=sys.stderr,
    )
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
