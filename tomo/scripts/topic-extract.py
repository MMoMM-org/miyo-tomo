#!/usr/bin/env python3
# version: 0.1.0
"""
topic-extract.py — Extract topic keywords from note content.

Reads note content (from file, stdin, or --content flag) and extracts topics
using 4 deterministic methods. The 5th LLM method is agent-side, not in this script.

Methods:
  1. Title analysis    — from H1 heading or filename
  2. H2 headings       — structural sub-topics
  3. Linked note titles — from [[wikilinks]]
  4. Tag-based topics  — from YAML frontmatter tags

Output: JSON to stdout
Exit: 0 on success, 1 on error
"""

import argparse
import json
import re
import sys
from collections import Counter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TITLE_SUFFIXES = [
    r"\s*\(MOC\)",
    r"\s*\(Thought\)",
    r"\s*\(Definition\)",
    r"\s+- Notes$",
    r"\s+MOC$",
    r"\s+Index$",
]

TITLE_DELIMITERS = [" — ", " - ", " | ", ": "]

BOILERPLATE_HEADINGS = {
    "overview", "related", "references", "notes", "links", "tags",
    "sources", "quotes", "action items", "recent updates", "tracker",
    "morning", "goal", "tasks", "log", "summary", "key takeaways",
    "key concepts",
}

STOP_WORDS = {"the", "a", "an", "and", "of", "in", "to", "for", "is",
              "are", "was", "were", "be", "been", "by", "at", "on",
              "with", "from", "or", "as", "it", "its", "this", "that"}

STRUCTURAL_TAG_PREFIXES = ("type/", "status/")

MAX_LINKS = 20
MAX_TOPICS = 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    """Lowercase, collapse whitespace, strip leading/trailing."""
    return re.sub(r"\s+", " ", text.lower().strip())


def is_stop_word(word: str) -> bool:
    return word.lower() in STOP_WORDS


def clean_title(title: str) -> str:
    """Strip common suffixes from a title string."""
    for suffix in TITLE_SUFFIXES:
        title = re.sub(suffix, "", title, flags=re.IGNORECASE)
    return title.strip()


def split_on_delimiters(text: str) -> list[str]:
    """Split text on title delimiters, returning non-empty segments."""
    parts = [text]
    for delim in TITLE_DELIMITERS:
        new_parts = []
        for part in parts:
            new_parts.extend(part.split(delim))
        parts = new_parts
    return [p.strip() for p in parts if p.strip()]


def extract_frontmatter(content: str) -> tuple[str, str]:
    """
    Split content into (frontmatter_block, body).
    frontmatter_block is the raw YAML between the --- delimiters (without ---).
    body is everything after the closing ---.
    """
    stripped = content.lstrip()
    if not stripped.startswith("---"):
        return "", content
    lines = stripped.split("\n")
    # find closing ---
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            frontmatter = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1:])
            return frontmatter, body
    return "", content


def parse_tags_from_frontmatter(fm: str) -> list[str]:
    """
    Parse tags from YAML frontmatter.
    Supports:
      tags: [a, b, c]
      tags:
        - a
        - b
    """
    tags: list[str] = []
    in_tags_block = False

    for line in fm.split("\n"):
        inline_match = re.match(r"^tags:\s*\[(.+)\]", line)
        if inline_match:
            raw = inline_match.group(1)
            tags = [t.strip().strip("\"'") for t in raw.split(",")]
            in_tags_block = False
            continue

        if re.match(r"^tags:\s*$", line):
            in_tags_block = True
            continue

        if in_tags_block:
            item_match = re.match(r"^\s+-\s+(.+)", line)
            if item_match:
                tags.append(item_match.group(1).strip().strip("\"'"))
            elif line and not line[0].isspace():
                in_tags_block = False

    return [t for t in tags if t]


# ---------------------------------------------------------------------------
# Method 1: Title analysis
# ---------------------------------------------------------------------------

def extract_from_title(content: str, explicit_title: str | None) -> list[str]:
    """Extract topics from the note title (first H1 or explicit title)."""
    title = explicit_title

    if not title:
        # Try first H1 heading
        h1_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if h1_match:
            title = h1_match.group(1).strip()

    if not title:
        return []

    title = clean_title(title)
    segments = split_on_delimiters(title)

    topics: list[str] = []
    for seg in segments:
        normed = normalize(seg)
        if normed and not is_stop_word(normed):
            topics.append(normed)
        # Also yield individual words from multi-word segments
        words = normed.split()
        if len(words) > 1:
            for word in words:
                if word and not is_stop_word(word) and word not in topics:
                    topics.append(word)

    return topics


# ---------------------------------------------------------------------------
# Method 2: H2 headings
# ---------------------------------------------------------------------------

def extract_from_headings(content: str) -> list[str]:
    """Extract topics from ## H2 headings, skipping boilerplate."""
    topics: list[str] = []
    for match in re.finditer(r"^##\s+(.+)$", content, re.MULTILINE):
        heading = match.group(1).strip()
        # Strip markdown formatting
        heading = re.sub(r"\*+|__?|`+|\[\[|\]\]", "", heading).strip()
        if not heading:
            continue
        normed = normalize(heading)
        if normed in BOILERPLATE_HEADINGS:
            continue
        if normed and normed not in topics:
            topics.append(normed)
    return topics


# ---------------------------------------------------------------------------
# Method 3: Linked note titles (wikilinks)
# ---------------------------------------------------------------------------

def extract_from_links(content: str) -> list[str]:
    """Extract topics from [[wikilink]] targets, up to MAX_LINKS unique links."""
    topics: list[str] = []
    seen: set[str] = set()

    for match in re.finditer(r"\[\[([^\[\]]+)\]\]", content):
        raw = match.group(1)
        # Handle alias: [[note|alias]] — use the note part (task spec says use "note")
        note_part = raw.split("|")[0].strip()
        # Strip path prefix: "Folder/SubFolder/Note Name" → "Note Name"
        note_part = note_part.split("/")[-1].strip()
        if not note_part:
            continue
        normed = normalize(note_part)
        if normed and normed not in seen:
            seen.add(normed)
            topics.append(normed)
        if len(topics) >= MAX_LINKS:
            break

    return topics


# ---------------------------------------------------------------------------
# Method 4: Tag-based topics
# ---------------------------------------------------------------------------

def extract_from_tags(frontmatter: str) -> list[str]:
    """Extract topics from frontmatter tags, skipping structural tags."""
    raw_tags = parse_tags_from_frontmatter(frontmatter)
    topics: list[str] = []

    for tag in raw_tags:
        # Skip structural tags
        if any(tag.startswith(prefix) for prefix in STRUCTURAL_TAG_PREFIXES):
            continue
        segments = tag.split("/")
        if len(segments) >= 1:
            leaf = normalize(segments[-1])
            if leaf and leaf not in topics:
                topics.append(leaf)
        if len(segments) >= 2:
            second_last = normalize(segments[-2])
            if second_last and second_last not in topics:
                topics.append(second_last)

    return topics


# ---------------------------------------------------------------------------
# Deduplication and ranking
# ---------------------------------------------------------------------------

def deduplicate_and_rank(source_methods: dict[str, list[str]]) -> list[str]:
    """
    Combine all topics across methods, rank by frequency (number of methods
    that produced each topic), deduplicate, return top MAX_TOPICS.
    """
    counter: Counter = Counter()
    all_seen: set[str] = set()

    for topics in source_methods.values():
        seen_this_method: set[str] = set()
        for topic in topics:
            if topic not in seen_this_method:
                counter[topic] += 1
                seen_this_method.add(topic)
            all_seen.add(topic)

    # Sort by frequency descending, then alphabetically for stability
    ranked = sorted(all_seen, key=lambda t: (-counter[t], t))
    return ranked[:MAX_TOPICS]


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def extract_topics(content: str, title: str | None = None) -> dict:
    """Run all 4 extraction methods and return the result dict."""
    if not content or not content.strip():
        return {"topics": [], "source_methods": {
            "title": [], "headings": [], "links": [], "tags": []
        }}

    frontmatter, body = extract_frontmatter(content)

    source_methods = {
        "title":    extract_from_title(body if frontmatter else content, title),
        "headings": extract_from_headings(body if frontmatter else content),
        "links":    extract_from_links(body if frontmatter else content),
        "tags":     extract_from_tags(frontmatter),
    }

    topics = deduplicate_and_rank(source_methods)

    return {
        "topics": topics,
        "source_methods": source_methods,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="topic-extract.py",
        description=(
            "Extract topic keywords from note content using deterministic methods.\n"
            "Reads from --file, --content, or stdin. Outputs JSON to stdout."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--file", metavar="PATH",
        help="Path to the note file to read",
    )
    source.add_argument(
        "--content", metavar="TEXT",
        help="Note content passed directly as a string",
    )
    parser.add_argument(
        "--title", metavar="TITLE",
        help="Note title (overrides H1 detection)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Read content
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                content = fh.read()
        except OSError as exc:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            return 1
    elif args.content is not None:
        content = args.content
    else:
        # stdin
        if sys.stdin.isatty():
            # No piped input and no flags — return empty gracefully
            content = ""
        else:
            content = sys.stdin.read()

    try:
        result = extract_topics(content, title=args.title)
    except Exception as exc:  # pylint: disable=broad-except
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
