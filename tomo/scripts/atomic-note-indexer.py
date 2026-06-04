#!/usr/bin/env python3
# version: 0.2.0
"""
atomic-note-indexer.py — Build the accumulation-cluster index for F-34 MSP Condition B.

Scans the atomic-note base path via Kado listNotes (ADR-1, ADR-2), extracts
per-note topics via extract_topics_from_fields (ADR-3, links kind=='link' only per
ADR-4), groups notes by normalised topic, and emits a JSON dict of the form:

    { "<topic>": ["<stem>", ...], ... }

Only clusters with >= min_cluster_size UNCLASSIFIED members are emitted.
Classification is determined by a per-candidate kado-read dataview-inline-field
call to test for the presence of an "up" key (ADR-5). Reads are deduped across
overlapping groups — each stem is read at most once.

STDERR-ONLY logging: stdout is reserved for the JSON result so callers can
safely pipe it (memory feedback_never_redirect_stderr_into_json).

ADR-1: Lives here, not in moc-tree-builder.py (722 LOC, near Constitution L2 cap).
ADR-5: up:: classification via per-candidate dataview-inline-field (not bulk).

Usage:
    python3 atomic-note-indexer.py --config <vault-config.yaml>
    python3 atomic-note-indexer.py --config <vault-config.yaml> --max-notes 50

Output: JSON to stdout
Exit: 0 on success or legitimately-empty vault (A6)
       1 on Kado/listNotes error (stdout still emits {} for cache-builder degradation)
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys

# Allow importing from scripts/lib/ (same pattern as moc-tree-builder.py)
sys.path.insert(0, os.path.dirname(__file__))
from lib.kado_client import KadoClient  # noqa: E402

# Load topic-extract.py in-process (hyphen in filename → importlib)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_te_spec = importlib.util.spec_from_file_location(
    "topic_extract", os.path.join(_SCRIPT_DIR, "topic-extract.py")
)
_te_mod = importlib.util.module_from_spec(_te_spec)
_te_spec.loader.exec_module(_te_mod)
extract_topics_from_fields = _te_mod.extract_topics_from_fields


# ---------------------------------------------------------------------------
# Core algorithm (SDD §Complex Logic — verbatim implementation)
# ---------------------------------------------------------------------------

def _stem(path: str) -> str:
    """Return the filename without .md extension (basename_no_ext pattern)."""
    name = os.path.basename(path)
    return name[:-3] if name.endswith(".md") else name


def build_accumulation_clusters(
    client,
    base_path: str,
    *,
    min_cluster_size: int = 3,
    max_notes: int | None = None,
    parent_marker: str = "up",
) -> dict:
    """Build the accumulation-cluster index.

    Args:
        client:           KadoClient instance (or compatible fake for testing).
        base_path:        Vault-relative path of the atomic-note folder.
        min_cluster_size: Minimum unclassified-member count to emit a cluster (default 3).
        max_notes:        Optional cap on notes fetched (for test bounds / performance).
        parent_marker:    Inline-field key used as the parent/classification marker
                          (vault-config relationships.parent.marker, default "up").

    Returns:
        {topic: sorted([unclassified_stem, ...])} for clusters >= min_cluster_size,
        or {} for a legitimately empty vault (A6).

    Raises:
        Exception: re-raised when list_notes fails, so main() can distinguish
                   a Kado error (exit 1) from an empty vault (exit 0).
    """
    # Step 1: fetch all atomic notes with topic signals.
    # Let list_notes exceptions propagate — callers that care about the exit
    # contract (main) catch them; unit tests that test the algorithm pass
    # a well-behaved fake client.
    notes = client.list_notes(
        base_path,
        fields=["links", "headings", "tags"],
        limit=500,
    )

    if max_notes is not None:
        notes = notes[:max_notes]

    if not notes:
        print("[atomic-note-indexer] No atomic notes found — emitting empty index.",
              file=sys.stderr)
        return {}

    print(f"[atomic-note-indexer] {len(notes)} notes fetched from {base_path!r}",
          file=sys.stderr)

    # Step 2: build groups: topic -> set(stem)
    groups: dict[str, set[str]] = {}
    for note in notes:
        try:
            result = extract_topics_from_fields(
                title=None,
                headings=note.get("headings", []),
                links=note.get("links", []),
                tags=note.get("tags", []),
            )
            topics = result.get("topics", [])
        except Exception as exc:
            print(f"[atomic-note-indexer] WARN topic extraction failed for "
                  f"{note.get('path')!r}: {exc}", file=sys.stderr)
            topics = []

        stem = _stem(note["path"])
        for topic in topics:
            groups.setdefault(topic, set()).add(stem)

    # Step 3: candidate gate — raw group size >= min_cluster_size
    candidates: dict[str, set[str]] = {
        t: stems for t, stems in groups.items() if len(stems) >= min_cluster_size
    }

    print(f"[atomic-note-indexer] {len(candidates)} candidate topic group(s) "
          f"(raw size >= {min_cluster_size})", file=sys.stderr)

    if not candidates:
        return {}

    # Step 4: classify stems via up:: read, deduped across overlapping groups
    # Only stems that appear in at least one candidate group are read.
    candidate_stems: set[str] = set()
    for stems in candidates.values():
        candidate_stems.update(stems)

    # Build a stem → full path lookup from the notes list
    stem_to_path: dict[str, str] = {_stem(n["path"]): n["path"] for n in notes}

    unclassified: dict[str, bool] = {}  # stem -> True if no up:: found
    for stem in candidate_stems:
        path = stem_to_path.get(stem)
        if path is None:
            # Stem not resolvable — treat as classified (conservative)
            unclassified[stem] = False
            continue
        try:
            fields = client.read_inline_fields(path)
            unclassified[stem] = parent_marker not in fields
        except Exception as exc:
            # Error on read → treat as classified (ADR-5 conservative)
            print(f"[atomic-note-indexer] WARN up:: read failed for {path!r}: {exc} "
                  f"— treating as classified", file=sys.stderr)
            unclassified[stem] = False

    # Step 5: filter to unclassified members; keep groups >= min_cluster_size
    result: dict[str, list[str]] = {}
    for topic, stems in candidates.items():
        keep = [s for s in stems if unclassified.get(s, False)]
        if len(keep) >= min_cluster_size:
            result[topic] = sorted(keep)

    print(f"[atomic-note-indexer] {len(result)} cluster(s) emitted after "
          f"classification filter", file=sys.stderr)

    return result


# ---------------------------------------------------------------------------
# Config reading
# ---------------------------------------------------------------------------

def _read_config_field(config_path: str, field: str, default: str | None = None) -> str | None:
    """Read a single dotted field from vault-config.yaml via read-config-field.py."""
    script = os.path.join(_SCRIPT_DIR, "read-config-field.py")
    cmd = ["python3", script, "--config", config_path, "--field", field]
    if default is not None:
        cmd += ["--default", str(default)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return default
        return r.stdout.strip() or default
    except Exception:
        return default


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atomic-note-indexer.py",
        description=(
            "Scan atomic notes via Kado, build accumulation-cluster index.\n"
            "Outputs {topic: [stems]} JSON to stdout; logs to stderr."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", metavar="PATH", required=True,
        help="Path to vault-config.yaml",
    )
    parser.add_argument(
        "--max-notes", metavar="N", type=int, default=None,
        help="Cap on notes fetched (for testing / performance bounds)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Read config fields
    base_path = _read_config_field(
        args.config, "concepts.atomic_note.base_path", default="Atoms"
    )
    min_cluster_str = _read_config_field(
        args.config, "tomo.accumulation.min_cluster_size", default="3"
    )
    try:
        min_cluster_size = int(min_cluster_str or "3")
    except ValueError:
        min_cluster_size = 3
    parent_marker = _read_config_field(
        args.config, "relationships.parent.marker", default="up"
    ) or "up"

    print(f"[atomic-note-indexer] base_path={base_path!r} "
          f"min_cluster_size={min_cluster_size} "
          f"parent_marker={parent_marker!r}", file=sys.stderr)

    try:
        client = KadoClient()
    except Exception as exc:
        print(f"[atomic-note-indexer] ERROR creating KadoClient: {exc}", file=sys.stderr)
        print("{}")
        return 1

    try:
        result = build_accumulation_clusters(
            client,
            base_path,
            min_cluster_size=min_cluster_size,
            max_notes=args.max_notes,
            parent_marker=parent_marker,
        )
    except Exception as exc:
        # Kado/listNotes failure: emit {} (so cache-builder degrades gracefully)
        # and exit nonzero (so /explore-vault logs the failure).
        print(f"[atomic-note-indexer] ERROR scanning notes: {exc}", file=sys.stderr)
        print("{}")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
