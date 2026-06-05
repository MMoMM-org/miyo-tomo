#!/usr/bin/env python3
# version: 0.4.0
"""moc-tree-builder.py — Build the MOC-structure cache (config/moc-structure-cache.yaml).

Rebuilt for spec 021 (MOC-propose consolidation, Phase 1 T1.4). Orchestrates the
three lib modules instead of the legacy in-file tree logic:

    lib/moc_scan.scan()                 — tag-primary MOC discovery + scope/exclude
    KadoClient.read_note()              — raw note content (one round-trip per note)
    lib/up_parse.parse_up_from_content  — dual-`up` SSoT ({target, source}; caller sets up_state)
    lib/placeholder_detect.detect_placeholders — real-vault-denominator placeholder set

Output: config/moc-structure-cache.yaml (MocStructureCache shape, SDD Application
Data Models). Single list of CacheEntry with a `kind` discriminator ("moc"|"note").
The kind=="moc" projection IS cache-builder's `map_notes` source (loader shim,
later task), so those entries also carry `classification` + `linked_notes` (C2).

Usage:
    python moc-tree-builder.py [--config PATH] [--output PATH]

Output: YAML cache file written atomically; progress + warnings to stderr.
Exit: 0 on success, 1 on error.
"""

import argparse
import importlib.util
import os
import re
import subprocess
import sys

import yaml

# Allow importing from scripts/ (cache-builder primitives) and scripts/lib/.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from lib import moc_scan, placeholder_detect, up_parse  # noqa: E402
from lib.kado_client import KadoClient, KadoNotFoundError  # noqa: E402

# ── Reuse cache-builder TTL/timestamp + atomic-write primitives ─────────────────
# cache-builder.py is hyphenated → load via importlib so we can import its
# utc_now_iso (ISO-8601 UTC) without duplicating it. (T1.4: reuse, do not
# reinvent.)
_cb_spec = importlib.util.spec_from_file_location(
    "cache_builder", os.path.join(_SCRIPT_DIR, "cache-builder.py")
)
_cache_builder = importlib.util.module_from_spec(_cb_spec)
_cb_spec.loader.exec_module(_cache_builder)

utc_now_iso = _cache_builder.utc_now_iso  # reused verbatim

# Schema version for the MOC-structure cache (distinct from cache-builder's
# CACHE_VERSION which versions discovery-cache.yaml).
MOC_CACHE_VERSION = 1

DEFAULT_TTL_DAYS = 1
DEFAULT_MOC_TAG = "type/others/moc"


# ──────────────────────────────────────────────────────────────────────────────
# Regex patterns (note parsing)
# ──────────────────────────────────────────────────────────────────────────────

# Match [[wikilink]] or [[wikilink|alias]]
WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")

# Match H1 heading
H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)

# Frontmatter block
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


# ──────────────────────────────────────────────────────────────────────────────
# Frontmatter / body helpers
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


def basename_no_ext(path: str) -> str:
    """Return filename without .md extension."""
    name = os.path.basename(path)
    if name.endswith(".md"):
        name = name[:-3]
    return name


def extract_wikilinks(text: str) -> list[str]:
    """Return list of wikilink targets (alias stripped) from text."""
    links = []
    for m in WIKILINK_RE.finditer(text):
        target = m.group(1).split("|")[0].strip()
        if target:
            links.append(target)
    return links


def extract_title(frontmatter: dict, body: str, path: str) -> str:
    """Title: frontmatter `title` → first H1 → filename stem."""
    fm_title = frontmatter.get("title")
    if isinstance(fm_title, str) and fm_title.strip():
        return fm_title.strip()
    h1 = H1_RE.search(body)
    if h1:
        return h1.group(1).strip()
    return basename_no_ext(path)


def extract_tags(frontmatter: dict) -> list[str]:
    """Normalise the frontmatter `tags` value to a list of strings."""
    raw = frontmatter.get("tags")
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if t is not None and str(t).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


# ──────────────────────────────────────────────────────────────────────────────
# Topic extraction (subprocess delegate to topic-extract.py)
# ──────────────────────────────────────────────────────────────────────────────

def extract_topics(content: str, title: str, script_dir: str) -> list[str]:
    """Delegate to topic-extract.py via subprocess; falls back to [] on any error."""
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
        import json
        return json.loads(result.stdout).get("topics", [])
    except subprocess.TimeoutExpired:
        print(f"[warn] topic-extract.py timed out for {title!r}", file=sys.stderr)
        return []
    except Exception as exc:  # noqa: BLE001 — best-effort enrichment
        print(f"[warn] topic-extract.py error for {title!r}: {exc}", file=sys.stderr)
        return []


# ──────────────────────────────────────────────────────────────────────────────
# Note reading
# ──────────────────────────────────────────────────────────────────────────────

def read_note_raw(client, path: str) -> "str | None":
    """Read a note's raw content via Kado. Returns None on not-found / error.

    A single read_note() call supplies everything downstream needs: title, tags,
    wikilinks, and the raw text that up_parse splits locally (C1 — no extra
    read_frontmatter round-trip).
    """
    try:
        result = client.read_note(path)
    except KadoNotFoundError:
        print(f"[warn] note not found: {path!r}", file=sys.stderr)
        return None
    except Exception as exc:  # noqa: BLE001 — denial-skip, mirror moc_scan
        print(f"[warn] failed to read {path!r}: {exc}", file=sys.stderr)
        return None

    if isinstance(result, dict):
        content = result.get("content", "")
        return content if isinstance(content, str) else str(content)
    return str(result)


# ──────────────────────────────────────────────────────────────────────────────
# Entry assembly (orchestration core)
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_up_state(target: "str | None", moc_stem_set: set[str]) -> str:
    """M1: caller resolves up_state from the parse target vs the MOC stem set.

    target None             → "absent"
    target in moc_stem_set  → "valid"
    else                    → "broken"
    """
    if target is None:
        return "absent"
    return "valid" if target in moc_stem_set else "broken"


def build_entries(client, scan_result, script_dir: str) -> list[dict]:
    """Assemble CacheEntry dicts from a ScanResult.

    Reads each MOC and in-scope note once, parses title/tags/wikilinks/up, and
    resolves up_state against the MOC stem set (M1). kind=="moc" entries also
    carry classification (None — legacy/live faithful) and linked_notes (the int
    count of non-MOC wikilinks) so cache-builder's build_classifications /
    build_scan_stats consume the projection without collapse (C2).
    """
    moc_paths = set(scan_result.moc_paths)
    note_paths = set(scan_result.in_scope_note_paths) - moc_paths

    # MOC stem set drives both up_state resolution (M1) and the
    # MOC-name resolution inside the linked_notes count below.
    moc_stem_set = {basename_no_ext(p) for p in moc_paths}

    # Read every path once; cache the parsed shape for entry assembly +
    # placeholder detection (which needs linked_notes_raw per MOC).
    raw_by_path: dict[str, str] = {}
    for path in sorted(moc_paths | note_paths):
        content = read_note_raw(client, path)
        if content is None:
            content = ""  # honest empty — no fabricated parent/links
        raw_by_path[path] = content

    # Placeholder detection runs over MOC bodies only, using the real in-scope
    # vault set as the denominator (the 224 fix). Exercised here over the single
    # read pass so the lib API contract is enforced at build time; the resulting
    # placeholder list is consumed downstream by shared-ctx, not stored in the
    # per-entry cache file.
    mocs_for_placeholder = {
        path: {"linked_notes_raw": extract_wikilinks(get_body(raw_by_path[path]))}
        for path in moc_paths
    }
    placeholder_detect.detect_placeholders(
        mocs_for_placeholder,
        known_moc_paths=moc_paths,
        in_scope_vault_paths=set(scan_result.in_scope_note_paths),
    )

    entries: list[dict] = []
    for path in sorted(moc_paths | note_paths):
        content = raw_by_path[path]
        fm = parse_frontmatter(content)
        body = get_body(content)
        kind = "moc" if path in moc_paths else "note"

        up = up_parse.parse_up_from_content(content)
        up_state = _resolve_up_state(up.target, moc_stem_set)

        title = extract_title(fm, body, path)
        entry: dict = {
            "path": path,
            "stem": basename_no_ext(path),
            "kind": kind,
            "title": title,
            "discovered_via": _discovered_via(scan_result, path),
            "topics": extract_topics(content, title, script_dir),
            "up_state": up_state,
            "up_target": up.target,
            "up_source": up.source,
            "tags": extract_tags(fm),
        }

        if kind == "moc":
            # C2 — the kind==moc projection is cache-builder's map_notes. It MUST
            # carry classification + linked_notes or build_classifications /
            # build_scan_stats silently collapse. classification stays None
            # (faithful to legacy + live cache; no Dewey derivation in T1.4).
            # linked_notes is the INT count of wikilinks that are NOT other MOCs
            # — the sole consumer (cache-builder:110) does numeric `+=`.
            wikilinks = extract_wikilinks(body)
            linked_notes_count = sum(
                1 for link in wikilinks
                if link.split("#", 1)[0].strip().split("/")[-1] not in moc_stem_set
            )
            entry["classification"] = None
            entry["linked_notes"] = linked_notes_count

        entries.append(entry)

    return entries


def _discovered_via(scan_result, path: str) -> str:
    """Per-entry discovered_via.

    moc_scan discovers MOCs by tag and the in-scope universe by path. A MOC that
    is also under a scope root is "both"; a tag-only MOC is "tag"; a non-MOC
    in-scope note is "path".
    """
    is_moc = path in scan_result.moc_paths
    in_scope = path in scan_result.in_scope_note_paths
    if is_moc and in_scope:
        return "both"
    if is_moc:
        return "tag"
    return "path"


# ──────────────────────────────────────────────────────────────────────────────
# Cache assembly + atomic write
# ──────────────────────────────────────────────────────────────────────────────

def assemble_cache(config: dict, entries: list[dict]) -> dict:
    """Build the MocStructureCache dict (SDD Application Data Models shape)."""
    msc_cfg = config.get("tomo", {}).get("moc_structure_cache", {})

    scope_paths = msc_cfg.get("scope_paths")
    if scope_paths is None:
        # Fall back to the derived scope (map_note + atomic_note) so a config
        # without an explicit scope_paths still records what was scanned.
        scope_paths = moc_scan.read_scope_paths(config)

    return {
        "moc_cache_version": MOC_CACHE_VERSION,
        "last_scan": utc_now_iso(),
        "ttl_days": msc_cfg.get("ttl_days", DEFAULT_TTL_DAYS),
        "scope_paths": list(scope_paths),
        "exclude_paths": list(msc_cfg.get("exclude_paths", [])),
        "moc_tag": msc_cfg.get("moc_tag", DEFAULT_MOC_TAG),
        "entries": entries,
    }


def write_cache_atomic(cache: dict, output_path: str) -> None:
    """Write the MOC-structure cache atomically (tmp file + os.replace).

    Reuses the same tmp-rename mechanism as cache-builder.write_cache_atomic; the
    only difference is the file header, so this is a thin local writer rather than
    a call into cache-builder's discovery-cache-specific writer.
    """
    import tempfile

    output_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(output_dir, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=output_dir, suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("# moc-structure-cache.yaml — auto-generated by moc-tree-builder.py\n")
            fh.write("# Do not edit manually — re-run /explore-vault to refresh.\n")
            yaml.dump(
                cache,
                fh,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
    except Exception:
        os.unlink(tmp_path)
        raise

    os.replace(tmp_path, output_path)


# ──────────────────────────────────────────────────────────────────────────────
# Build orchestration
# ──────────────────────────────────────────────────────────────────────────────

def run_with_client(client, config: dict) -> dict:
    """Build the MOC-structure cache dict from a (real or fake) Kado client.

    The testable seam: callers inject a client and a parsed config; this returns
    the cache dict without touching disk. `run()` wires the real client + config
    file + output path around it.
    """
    scan_result = moc_scan.scan(client, config)
    entries = build_entries(client, scan_result, _SCRIPT_DIR)
    return assemble_cache(config, entries)


def run(config_path: str, output_path: str) -> dict:
    """Load config, connect to Kado, build the cache, write it atomically."""
    print(f"[moc-tree] Loading config: {config_path!r}", file=sys.stderr)
    try:
        with open(config_path, encoding="utf-8") as fh:
            config = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        print(f"[error] Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as exc:
        print(f"[error] Failed to parse config: {exc}", file=sys.stderr)
        sys.exit(1)

    print("[moc-tree] Connecting to Kado...", file=sys.stderr)
    try:
        client = KadoClient()
    except Exception as exc:  # noqa: BLE001
        print(f"[error] Failed to initialise KadoClient: {exc}", file=sys.stderr)
        sys.exit(1)

    cache = run_with_client(client, config)
    print(f"[moc-tree] Assembled {len(cache['entries'])} entr(y/ies)", file=sys.stderr)

    write_cache_atomic(cache, output_path)
    print(
        f"[moc-tree] MOC-structure cache written: {output_path} "
        f"({os.path.getsize(output_path)} bytes)",
        file=sys.stderr,
    )
    return cache


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="moc-tree-builder.py",
        description=(
            "Build the MOC-structure cache (config/moc-structure-cache.yaml) by "
            "orchestrating tag-primary discovery, dual-up parsing, and real-vault "
            "placeholder detection.\n\nProgress and warnings: stderr."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default="config/vault-config.yaml",
        help="Path to vault-config.yaml (default: config/vault-config.yaml)",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default="config/moc-structure-cache.yaml",
        help="Output path (default: config/moc-structure-cache.yaml)",
    )
    args = parser.parse_args()

    try:
        run(args.config, args.output)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"[error] Unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
