#!/usr/bin/env python3
# version: 0.2.0
"""
moc-tree-builder.py — Discover all MOCs in the vault, read their content,
build a parent/child/sibling tree, and output JSON.

Discovery uses two parallel strategies (configured in vault-config.yaml):
  1. Path-based: list_dir on concepts.map_note.paths[]
  2. Tag-based: search_by_tag on concepts.map_note.tags[]

Results are deduplicated by path. MOC relationships are extracted via up:: and
related:: markers. Topics are extracted by delegating to topic-extract.py.

Usage:
    python moc-tree-builder.py [--config PATH]

Output: JSON to stdout, progress to stderr.
Exit: 0 on success, 1 on error.
"""

import argparse
import json
import os
import re
import subprocess
import sys

import yaml

# Allow importing from scripts/lib/
sys.path.insert(0, os.path.dirname(__file__))
from lib.kado_client import KadoClient, KadoNotFoundError  # noqa: E402


# ──────────────────────────────────────────────────────────────────────────────
# Regex patterns
# ──────────────────────────────────────────────────────────────────────────────

# Match [[wikilink]] or [[wikilink|alias]]
WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")

# Match H1 heading
H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)

# Match H2 headings
H2_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)

# Match up:: [[...]] lines (parent relationship)
UP_RE = re.compile(r"(?:^|\n)\s*up::\s*(.+)")

# Match related:: [[...]] lines (sibling relationship)
RELATED_RE = re.compile(r"(?:^|\n)\s*related::\s*(.+)")

# Frontmatter block
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


# ──────────────────────────────────────────────────────────────────────────────
# Frontmatter parsing
# ──────────────────────────────────────────────────────────────────────────────

def parse_frontmatter(content: str) -> dict:
    """Extract and parse YAML frontmatter. Returns empty dict if none found."""
    match = FRONTMATTER_RE.match(content.lstrip())
    if not match:
        return {}
    try:
        fm = yaml.safe_load(match.group(1))
        return fm if isinstance(fm, dict) else {}
    except yaml.YAMLError:
        return {}


def get_body(content: str) -> str:
    """Return content with frontmatter stripped."""
    match = FRONTMATTER_RE.match(content.lstrip())
    if match:
        return content[match.end():]
    return content


# ──────────────────────────────────────────────────────────────────────────────
# Wikilink extraction helpers
# ──────────────────────────────────────────────────────────────────────────────

def extract_wikilinks(text: str) -> list[str]:
    """Return list of wikilink targets (without alias) from text."""
    links = []
    for m in WIKILINK_RE.finditer(text):
        raw = m.group(1)
        target = raw.split("|")[0].strip()
        if target:
            links.append(target)
    return links


def extract_relationship_links(line_content: str) -> list[str]:
    """Extract wikilink targets from a relationship line (e.g. up:: [[A]], [[B]])."""
    return extract_wikilinks(line_content)


# ──────────────────────────────────────────────────────────────────────────────
# Path normalisation / resolution
# ──────────────────────────────────────────────────────────────────────────────

def basename_no_ext(path: str) -> str:
    """Return filename without .md extension."""
    name = os.path.basename(path)
    if name.endswith(".md"):
        name = name[:-3]
    return name


def resolve_link_to_path(link_target: str, moc_paths: list[str]) -> str | None:
    """
    Attempt to resolve a wikilink target to a known MOC path.

    Matching strategy (in order):
    1. Exact full path match (e.g. "Atlas/200 Maps/Home.md")
    2. Exact full path match after adding ".md"
    3. Filename (without .md) case-insensitive match
    """
    # Normalise: strip trailing .md from link_target for comparison
    link_bare = link_target
    if link_bare.endswith(".md"):
        link_bare = link_bare[:-3]

    # 1 & 2: exact path
    for moc_path in moc_paths:
        moc_bare = moc_path[:-3] if moc_path.endswith(".md") else moc_path
        if moc_bare == link_bare or moc_path == link_target:
            return moc_path

    # 3: filename match (case-insensitive)
    link_name_lower = link_bare.split("/")[-1].lower()
    for moc_path in moc_paths:
        moc_name = basename_no_ext(moc_path).lower()
        if moc_name == link_name_lower:
            return moc_path

    return None


# ──────────────────────────────────────────────────────────────────────────────
# MOC discovery
# ──────────────────────────────────────────────────────────────────────────────

def discover_via_paths(client: KadoClient, paths: list[str]) -> dict[str, str]:
    """
    List each configured map_note path recursively and collect .md files.

    Returns:
        dict mapping vault-relative path → "path"
    """
    found: dict[str, str] = {}
    for folder_path in paths:
        print(f"[discover] path-based scan: {folder_path!r}", file=sys.stderr)
        try:
            items = client.list_dir(folder_path)
        except Exception as exc:
            print(f"[warn] Could not list {folder_path!r}: {exc}", file=sys.stderr)
            continue

        # Kado's listDir returns a flat recursive file listing — every item
        # is already a file, so drop the type filter and keep only the .md
        # extension check. See _outbox/for-kado/2026-04-11_tomo-to-kado_listdir-api-gaps.md.
        for item in items:
            name = item.get("name", "")
            item_path = item.get("path", "")
            if name.endswith(".md") or item_path.endswith(".md"):
                key = item_path or (folder_path.rstrip("/") + "/" + name)
                found[key] = "path"

    return found


def discover_via_tags(client: KadoClient, tags: list[str]) -> dict[str, str]:
    """
    Search for notes tagged with each configured map_note tag.

    Returns:
        dict mapping vault-relative path → "tag"
    """
    found: dict[str, str] = {}
    for tag in tags:
        # Normalise: search_by_tag may or may not require leading #
        query = tag if tag.startswith("#") else f"#{tag}"
        print(f"[discover] tag-based scan: {query!r}", file=sys.stderr)
        try:
            results = client.search_by_tag(query)
        except Exception as exc:
            print(f"[warn] Could not search by tag {query!r}: {exc}", file=sys.stderr)
            continue

        for item in results:
            item_path = item.get("path", "")
            if item_path and item_path.endswith(".md"):
                found[item_path] = "tag"

    return found


def deduplicate_discoveries(
    path_found: dict[str, str],
    tag_found: dict[str, str],
) -> dict[str, str]:
    """
    Merge path and tag discoveries. Notes found by both get discovered_via="both".

    Returns:
        dict mapping path → discovered_via ("path" | "tag" | "both")
    """
    merged: dict[str, str] = {}

    for p, via in path_found.items():
        merged[p] = via  # "path"

    for p, via in tag_found.items():
        if p in merged:
            merged[p] = "both"
        else:
            merged[p] = via  # "tag"

    return merged


# ──────────────────────────────────────────────────────────────────────────────
# MOC reading
# ──────────────────────────────────────────────────────────────────────────────

def read_moc(client: KadoClient, path: str) -> dict:
    """
    Read a MOC note via Kado and extract structured fields.

    Returns:
        {
            "content": full raw content,
            "title": str,
            "sections": list of H2 headings,
            "linked_notes_raw": all wikilink targets in body,
            "parent_links": wikilink targets from up:: lines,
            "sibling_links": wikilink targets from related:: lines,
            "map_state": str | None,
        }
    """
    try:
        result = client.read_note(path)
    except KadoNotFoundError:
        print(f"[warn] MOC not found: {path!r}", file=sys.stderr)
        return {}
    except Exception as exc:
        print(f"[warn] Failed to read {path!r}: {exc}", file=sys.stderr)
        return {}

    # read_note may return {content: str} or a plain string
    if isinstance(result, dict):
        content = result.get("content", "")
        if not isinstance(content, str):
            content = str(content)
    else:
        content = str(result)

    frontmatter = parse_frontmatter(content)
    body = get_body(content)

    # Title: frontmatter title field → first H1 → filename
    title = None
    if isinstance(frontmatter.get("title"), str):
        title = frontmatter["title"].strip()
    if not title:
        h1_match = H1_RE.search(body)
        if h1_match:
            title = h1_match.group(1).strip()
    if not title:
        title = basename_no_ext(path)

    # H2 section headings
    sections = []
    for m in H2_RE.finditer(body):
        heading = re.sub(r"\*+|__?|`+|\[\[|\]\]", "", m.group(1)).strip()
        if heading:
            sections.append(heading)

    # mapState from frontmatter
    map_state = frontmatter.get("mapState", None)
    if map_state is not None:
        map_state = str(map_state).strip() or None

    # All wikilinks in body (for linked_notes count and child detection)
    linked_notes_raw = extract_wikilinks(body)

    # Parent relationships: up:: lines
    parent_links: list[str] = []
    for m in UP_RE.finditer(body):
        parent_links.extend(extract_relationship_links(m.group(1)))

    # Sibling relationships: related:: lines
    sibling_links: list[str] = []
    for m in RELATED_RE.finditer(body):
        sibling_links.extend(extract_relationship_links(m.group(1)))

    return {
        "content": content,
        "title": title,
        "sections": sections,
        "linked_notes_raw": linked_notes_raw,
        "parent_links": parent_links,
        "sibling_links": sibling_links,
        "map_state": map_state,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Topic extraction (subprocess)
# ──────────────────────────────────────────────────────────────────────────────

def extract_topics(content: str, title: str, script_dir: str) -> list[str]:
    """
    Delegate to topic-extract.py via subprocess and return the topics list.

    Falls back to [] on any error.
    """
    topic_script = os.path.join(script_dir, "topic-extract.py")
    try:
        result = subprocess.run(
            ["python3", topic_script, "--content", content, "--title", title],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(
                f"[warn] topic-extract.py failed for {title!r}: {result.stderr.strip()}",
                file=sys.stderr,
            )
            return []
        parsed = json.loads(result.stdout)
        return parsed.get("topics", [])
    except subprocess.TimeoutExpired:
        print(f"[warn] topic-extract.py timed out for {title!r}", file=sys.stderr)
        return []
    except (json.JSONDecodeError, Exception) as exc:
        print(f"[warn] topic-extract.py error for {title!r}: {exc}", file=sys.stderr)
        return []


# ──────────────────────────────────────────────────────────────────────────────
# Tree building
# ──────────────────────────────────────────────────────────────────────────────

def build_tree(mocs: dict[str, dict]) -> tuple[dict[str, dict], int]:
    """
    Assign parent_moc, child_mocs, sibling_mocs, and level to each MOC.

    Returns:
        (enriched mocs dict, cycles_broken count)

    Algorithm:
        - parent_moc: first resolved up:: link that points to another MOC
        - multi-parent: level = min(parent_levels) + 1
        - cycle detection: BFS/DFS up the parent chain; break if revisiting
        - sibling_mocs: resolved related:: links that point to other MOCs
        - child_mocs: derived (all MOCs whose parent_moc == this path)
    """
    moc_paths = list(mocs.keys())
    cycles_broken = 0

    # --- Step 1: resolve parent and sibling links ---
    for path, moc in mocs.items():
        # Resolve parent links
        parent_paths: list[str] = []
        for link in moc.get("parent_links", []):
            resolved = resolve_link_to_path(link, moc_paths)
            if resolved and resolved != path:  # no self-reference
                parent_paths.append(resolved)
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_parents: list[str] = []
        for p in parent_paths:
            if p not in seen:
                seen.add(p)
                unique_parents.append(p)
        moc["parent_moc_candidates"] = unique_parents

        # Resolve sibling links
        sibling_paths: list[str] = []
        for link in moc.get("sibling_links", []):
            resolved = resolve_link_to_path(link, moc_paths)
            if resolved and resolved != path:
                sibling_paths.append(resolved)
        seen_sib: set[str] = set()
        unique_siblings: list[str] = []
        for p in sibling_paths:
            if p not in seen_sib:
                seen_sib.add(p)
                unique_siblings.append(p)
        moc["sibling_mocs"] = unique_siblings

    # --- Step 2: assign levels with cycle detection ---
    levels: dict[str, int] = {}  # path → computed level

    def compute_level(path: str, visiting: set[str]) -> int:
        """Recursively compute level; returns 0 on cycle."""
        if path in levels:
            return levels[path]
        if path in visiting:
            # Cycle detected — break here
            return 0
        visiting = visiting | {path}
        moc = mocs.get(path, {})
        parents = moc.get("parent_moc_candidates", [])
        if not parents:
            levels[path] = 0
            return 0
        parent_levels = []
        for p in parents:
            if p in visiting:
                # Cycle — skip this parent
                nonlocal cycles_broken
                cycles_broken += 1
                print(
                    f"[warn] Cycle detected: {path!r} → {p!r} — breaking",
                    file=sys.stderr,
                )
                continue
            parent_levels.append(compute_level(p, visiting))
        if not parent_levels:
            # All parents were cycle-causing
            levels[path] = 0
        else:
            levels[path] = min(parent_levels) + 1
        return levels[path]

    for path in moc_paths:
        compute_level(path, set())

    # --- Step 3: assign level, parent_moc (primary = lowest level parent) ---
    for path, moc in mocs.items():
        moc["level"] = levels.get(path, 0)
        parents = moc.get("parent_moc_candidates", [])
        if parents:
            # Primary parent = candidate with the lowest level (most root-like)
            primary = min(parents, key=lambda p: levels.get(p, 0))
            moc["parent_moc"] = primary
        else:
            moc["parent_moc"] = None

    # --- Step 4: derive child_mocs ---
    children: dict[str, list[str]] = {p: [] for p in moc_paths}
    for path, moc in mocs.items():
        parent = moc.get("parent_moc")
        if parent and parent in children:
            children[parent].append(path)

    for path, moc in mocs.items():
        moc["child_mocs"] = children[path]

    return mocs, cycles_broken


# ──────────────────────────────────────────────────────────────────────────────
# Placeholder detection
# ──────────────────────────────────────────────────────────────────────────────

def detect_placeholders(
    mocs: dict[str, dict],
    all_vault_paths: set[str],
) -> list[dict]:
    """
    Find wikilink targets in MOC bodies that don't resolve to any known note.

    A placeholder is a link target that:
    - Does not resolve to a discovered MOC path
    - Does not match any vault note (checked by filename)

    Returns:
        list of {"target": str, "referenced_by": str}
    """
    moc_paths = list(mocs.keys())
    # Build a lookup of all known vault names (lowercase, no .md)
    known_names: set[str] = set()
    for p in all_vault_paths:
        known_names.add(basename_no_ext(p).lower())

    placeholders: list[dict] = []
    seen_placeholders: set[tuple[str, str]] = set()

    for path, moc in mocs.items():
        for link in moc.get("linked_notes_raw", []):
            # Does it resolve to a known MOC?
            if resolve_link_to_path(link, moc_paths):
                continue
            # Does it resolve to any known vault note by name?
            link_name = link.split("/")[-1].lower()
            if link_name.endswith(".md"):
                link_name = link_name[:-3]
            if link_name in known_names:
                continue
            # It's a placeholder
            key = (link, path)
            if key not in seen_placeholders:
                seen_placeholders.add(key)
                placeholders.append({"target": link, "referenced_by": path})

    return placeholders


# ──────────────────────────────────────────────────────────────────────────────
# Main build logic
# ──────────────────────────────────────────────────────────────────────────────

def run(config_path: str) -> dict:
    """Execute the full MOC discovery, reading, and tree-building pipeline."""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Load config
    print(f"[moc-tree] Loading config: {config_path!r}", file=sys.stderr)
    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"[error] Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as exc:
        print(f"[error] Failed to parse config: {exc}", file=sys.stderr)
        sys.exit(1)

    # Extract map_note config
    concepts = config.get("concepts", {})
    map_note_cfg = concepts.get("map_note", {})

    if isinstance(map_note_cfg, str):
        # Simple string path — treat as single path entry
        moc_paths_cfg: list[str] = [map_note_cfg]
        moc_tags_cfg: list[str] = []
    elif isinstance(map_note_cfg, dict):
        moc_paths_cfg = map_note_cfg.get("paths", []) or []
        moc_tags_cfg = map_note_cfg.get("tags", []) or []
    else:
        moc_paths_cfg = []
        moc_tags_cfg = []

    # Initialise Kado client
    print("[moc-tree] Connecting to Kado...", file=sys.stderr)
    try:
        client = KadoClient()
    except Exception as exc:
        print(f"[error] Failed to initialise KadoClient: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── Discovery ─────────────────────────────────────────────────────────────

    path_found: dict[str, str] = {}
    tag_found: dict[str, str] = {}

    if moc_paths_cfg:
        path_found = discover_via_paths(client, moc_paths_cfg)
        print(
            f"[moc-tree] Path-based: {len(path_found)} MOC(s) found",
            file=sys.stderr,
        )
    else:
        print("[moc-tree] No map_note.paths configured — skipping path discovery",
              file=sys.stderr)

    if moc_tags_cfg:
        tag_found = discover_via_tags(client, moc_tags_cfg)
        print(
            f"[moc-tree] Tag-based: {len(tag_found)} MOC(s) found",
            file=sys.stderr,
        )
    else:
        print("[moc-tree] No map_note.tags configured — skipping tag discovery",
              file=sys.stderr)

    discovered: dict[str, str] = deduplicate_discoveries(path_found, tag_found)
    print(f"[moc-tree] Total after dedup: {len(discovered)} MOC(s)", file=sys.stderr)

    if not discovered:
        # Empty vault / no MOCs — return zeroed output
        return {
            "map_notes": [],
            "placeholder_mocs": [],
            "tree_stats": {
                "total_mocs": 0,
                "root_mocs": 0,
                "max_depth": 0,
                "cycles_broken": 0,
            },
        }

    # ── Read each MOC ─────────────────────────────────────────────────────────

    # Collect all vault paths for placeholder detection (best effort)
    all_vault_paths: set[str] = set()

    mocs: dict[str, dict] = {}
    for path, via in discovered.items():
        print(f"[moc-tree] Reading: {path!r}", file=sys.stderr)
        moc_data = read_moc(client, path)
        if not moc_data:
            # Failed read — include with minimal data
            moc_data = {
                "content": "",
                "title": basename_no_ext(path),
                "sections": [],
                "linked_notes_raw": [],
                "parent_links": [],
                "sibling_links": [],
                "map_state": None,
            }
        moc_data["discovered_via"] = via
        moc_data["path"] = path
        mocs[path] = moc_data
        # Track path in vault set
        all_vault_paths.add(path)

    # ── Topic extraction ──────────────────────────────────────────────────────

    for path, moc in mocs.items():
        title = moc["title"]
        content = moc.get("content", "")
        print(f"[moc-tree] Extracting topics: {title!r}", file=sys.stderr)
        moc["topics"] = extract_topics(content, title, script_dir)

    # ── Tree building ──────────────────────────────────────────────────────────

    print("[moc-tree] Building tree...", file=sys.stderr)
    mocs, cycles_broken = build_tree(mocs)

    # ── Placeholder detection ──────────────────────────────────────────────────

    print("[moc-tree] Detecting placeholders...", file=sys.stderr)
    placeholder_mocs = detect_placeholders(mocs, all_vault_paths)

    # ── Assemble output ────────────────────────────────────────────────────────

    map_notes = []
    for path, moc in mocs.items():
        linked_moc_paths = set(moc.get("child_mocs", []))
        parent = moc.get("parent_moc")
        if parent:
            linked_moc_paths.add(parent)
        linked_moc_paths.update(moc.get("sibling_mocs", []))

        # linked_notes: wikilinks that do NOT resolve to other MOCs
        moc_paths_list = list(mocs.keys())
        linked_notes_count = sum(
            1 for link in moc.get("linked_notes_raw", [])
            if not resolve_link_to_path(link, moc_paths_list)
        )

        map_notes.append({
            "path": path,
            "title": moc["title"],
            "discovered_via": moc["discovered_via"],
            "level": moc["level"],
            "parent_moc": moc.get("parent_moc"),
            "child_mocs": moc.get("child_mocs", []),
            "sibling_mocs": moc.get("sibling_mocs", []),
            "state": moc.get("map_state"),
            "topics": moc.get("topics", []),
            "sections": moc.get("sections", []),
            "linked_notes": linked_notes_count,
            "classification": None,
        })

    # Sort: roots first, then by level, then by path
    map_notes.sort(key=lambda m: (m["level"], m["path"]))

    # Tree stats
    root_mocs = sum(1 for m in map_notes if m["level"] == 0)
    max_depth = max((m["level"] for m in map_notes), default=0)

    return {
        "map_notes": map_notes,
        "placeholder_mocs": placeholder_mocs,
        "tree_stats": {
            "total_mocs": len(map_notes),
            "root_mocs": root_mocs,
            "max_depth": max_depth,
            "cycles_broken": cycles_broken,
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="moc-tree-builder.py",
        description=(
            "Discover all MOCs in the vault, read their content, build a "
            "parent/child/sibling tree, and output JSON.\n\n"
            "Output: JSON to stdout. Progress and warnings: stderr."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default="config/vault-config.yaml",
        help="Path to vault-config.yaml (default: config/vault-config.yaml)",
    )
    args = parser.parse_args()

    try:
        result = run(args.config)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[error] Unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
