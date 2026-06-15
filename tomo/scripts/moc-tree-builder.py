#!/usr/bin/env python3
# version: 0.6.0
"""moc-tree-builder.py — Build the MOC-structure cache (config/moc-structure-cache.yaml).

Rebuilt for spec 021 (MOC-propose consolidation, Phase 1 T1.4). Orchestrates the
three lib modules instead of the legacy in-file tree logic:

    lib/moc_scan.scan()                 — tag-primary MOC discovery + scope/exclude
    KadoClient.read_note()              — raw note content (one round-trip per note)
    lib/up_parse.parse_up_from_content  — dual-`up` SSoT ({target, source}; caller sets up_state)
    lib/placeholder_detect.detect_placeholders — real-vault-denominator placeholder set

TWO outputs (the legacy cache-builder contract is preserved — SDD line 183):
    1. stdout JSON  — {"map_notes": [<kind==moc entries>], "placeholder_links": [...]}
       This is the cache-builder feed: `moc-tree-builder.py > moc-output.json`
       then `cache-builder.py --mocs moc-output.json` (vault-explorer Step 9).
       map_notes entries carry classification + linked_notes(int) so
       cache-builder.build_classifications / build_scan_stats keep working (C2).
    2. config/moc-structure-cache.yaml  — the MocStructureCache (SDD Application
       Data Models): a single CacheEntry list with a `kind` discriminator
       ("moc"|"note"), plus a top-level placeholder_links field.

STRICT: stdout carries the JSON feed ONLY. All progress/warnings go to stderr —
mixing them into stdout corrupts the downstream json.load
(feedback_never_redirect_stderr_into_json).

Usage:
    python moc-tree-builder.py [--config PATH] [--output PATH]

Exit: 0 on success, 1 on error.
"""

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time

import yaml

# Allow importing from scripts/ (cache-builder primitives) and scripts/lib/.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from lib import moc_scan, moc_structure, placeholder_detect, up_parse  # noqa: E402
from lib.kado_client import KadoClient, KadoNotFoundError  # noqa: E402

# Footer-marker callouts: content sections live BEFORE the first of these.
# Mirrors instruction-render.py:FOOTER_CALLOUTS exactly (spec 022 / #35 / F-55 —
# stays hardcoded, NOT a config knob; F-55 tracks making it profile-configurable).
# WHY local duplicate: moc-tree-builder must not import instruction-render (runtime
# boundary) and moc_structure must not hardcode either (library contract).
FOOTER_CALLOUTS: frozenset[str] = frozenset({"video", "calendar", "puzzle", "compass"})

# Default editable callout names when vault-config has no callouts.editable block.
# Matches the CONFIG_DEFAULTS in instruction-render.py so build-time and render-time
# agree on what "editable" means before /explore-vault has written the config.
_DEFAULT_EDITABLE: frozenset[str] = frozenset({"connect", "blocks", "anchor"})

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


def _editable_set_from_config(config: dict) -> frozenset[str]:
    """Return the editable callout names from vault-config `callouts.editable`.

    Falls back to _DEFAULT_EDITABLE when the key is absent or empty, matching
    the same default instruction-render.py uses (CONFIG_DEFAULTS).

    The vault-config shape is:
        callouts:
          editable:
            - blocks
            - connect
    or (dict form from vault-config-writer):
        callouts:
          editable:
            blocks: ...
            connect: ...
    """
    callouts_cfg = config.get("callouts") or {}
    editable = callouts_cfg.get("editable")
    if isinstance(editable, dict):
        names = list(editable.keys())
    elif isinstance(editable, list):
        names = [str(x) for x in editable if x]
    else:
        names = []
    return frozenset(names) if names else _DEFAULT_EDITABLE


def _count_linked_notes(body: str, moc_stem_set: set[str]) -> int:
    """Count wikilinks in a MOC body that point to non-MOC notes.

    The int the sole consumer (cache-builder:110) sums numerically. Same-note
    anchors (`[[#^id]]`, `[[#Heading]]`) reduce to an empty stem after anchor
    strip and are NOT links to another note — they are skipped so they do not
    inflate the count (W2). Mirrors lib/placeholder_detect's `if not
    note_target: continue` guard.
    """
    count = 0
    for link in extract_wikilinks(body):
        note_stem = link.split("#", 1)[0].strip().split("/")[-1]
        if not note_stem:
            continue  # same-note anchor — not a link to another note
        if note_stem not in moc_stem_set:
            count += 1
    return count


def build_entries(
    client, scan_result, script_dir: str, config: dict | None = None
) -> tuple[list[dict], list[dict], dict]:
    """Assemble CacheEntry dicts + the placeholder list from a ScanResult.

    Reads each MOC and in-scope note once, parses title/tags/wikilinks/up, and
    resolves up_state against the MOC stem set (M1). kind=="moc" entries also
    carry classification (None — legacy/live faithful) and linked_notes (the int
    count of non-MOC wikilinks) so cache-builder's build_classifications /
    build_scan_stats consume the projection without collapse (C2).

    T3.1 (spec 022): MOC entries additionally carry headings + editable_callouts
    parsed from the body bytes already in raw_by_path — no new Kado call.

    Returns
    -------
    (entries, placeholder_links, placeholder_stats):
        entries           — list[CacheEntry] (moc + note, kind-discriminated)
        placeholder_links  — list[{target, referenced_by}] from the real-vault-
                            denominator detector (the 224 fix). Surfaced (W1) so
                            cache-builder's placeholder_links lift + Condition C
                            keep working, and persisted into both outputs.
        placeholder_stats  — raw/kept/dropped breakdown for the placeholder.build
                            observability event (M2/M4).
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
    # vault set as the denominator (the 224 fix). The result is RETURNED (W1) so
    # it feeds cache-builder (--mocs JSON) and is persisted into the YAML cache.
    mocs_for_placeholder = {
        path: {"linked_notes_raw": extract_wikilinks(get_body(raw_by_path[path]))}
        for path in moc_paths
    }
    placeholder_links, placeholder_stats = placeholder_detect.detect_placeholders_with_stats(
        mocs_for_placeholder,
        known_moc_paths=moc_paths,
        in_scope_vault_paths=set(scan_result.in_scope_note_paths),
    )

    # T3.1 (spec 022): editable_set from vault-config callouts.editable;
    # footer_set is hardcoded to match instruction-render.py (F-55 boundary).
    editable_set = _editable_set_from_config(config or {})

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
            # linked_notes is the INT count of wikilinks that are NOT other MOCs.
            entry["classification"] = None
            entry["linked_notes"] = _count_linked_notes(body, moc_stem_set)

            # T3.1 (spec 022): inventory — parse headings and editable callouts
            # from body bytes already in raw_by_path (no new Kado call).
            entry["headings"] = moc_structure.parse_headings(body, FOOTER_CALLOUTS)
            entry["editable_callouts"] = moc_structure.parse_editable_callouts(
                body, editable_set
            )

        entries.append(entry)

    return entries, placeholder_links, placeholder_stats


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

def assemble_cache(
    config: dict, entries: list[dict], placeholder_links: list[dict]
) -> dict:
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
        # Persisted into the cache file too — solution.md integration points
        # (304/307) list moc-structure-cache.yaml as a placeholder destination
        # for the future shared-ctx wiring.
        "placeholder_links": list(placeholder_links),
    }


def build_cache_builder_feed(entries: list[dict], placeholder_links: list[dict]) -> dict:
    """Build the legacy cache-builder JSON feed (stdout).

    cache-builder.build_map_notes reads `map_notes` and build_placeholder_links
    reads `placeholder_links`. The kind==moc projection IS map_notes; each entry
    already carries classification + linked_notes(int) + path/stem/title/topics/
    tags (C2), so cache-builder's build_classifications / build_scan_stats keep
    working unchanged. This preserves the vault-explorer Step 9 contract:
        moc-tree-builder.py > moc-output.json ; cache-builder.py --mocs moc-output.json
    (SDD line 183 — "still emits the cache-builder-shaped map_notes superset").
    """
    return {
        "map_notes": [e for e in entries if e["kind"] == "moc"],
        "placeholder_links": list(placeholder_links),
    }


def write_cache_atomic(cache: dict, output_path: str) -> None:
    """Write the MOC-structure cache atomically (tmp file + os.replace).

    Reuses the same tmp-rename mechanism as cache-builder.write_cache_atomic; the
    only difference is the file header, so this is a thin local writer rather than
    a call into cache-builder's discovery-cache-specific writer.
    """
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

def _count_excluded_leaks(entries: list[dict], exclude_paths: list[str]) -> int:
    """Count entries whose path lives under an excluded prefix (M7 leak guard).

    A non-zero count means the scan let an excluded path into the cache — the
    exclusion is the security/scope boundary, so this is asserted to be 0.
    """
    prefixes = tuple(p.rstrip("/") + "/" for p in exclude_paths if p)
    if not prefixes:
        return 0
    return sum(1 for e in entries if e["path"].startswith(prefixes))


def _emit_build_telemetry(cache: dict, placeholder_stats: dict, duration_ms: int) -> None:
    """Emit the PRD observability events to stderr (stdout is the JSON feed only).

    Two greppable, JSON-tailed lines — `placeholder.build` validates M2/M4
    (placeholder false-positive drop), `moc-cache.build` validates M7 (no
    excluded-path leakage) + TTL/build-cost. Parsers split on the event name.
    """
    entries = cache["entries"]
    moc_cache_stats = {
        "built_at": cache["last_scan"],
        "mocs_count": sum(1 for e in entries if e["kind"] == "moc"),
        "notes_count": sum(1 for e in entries if e["kind"] == "note"),
        "scope_paths": len(cache["scope_paths"]),
        "excluded_leak_count": _count_excluded_leaks(entries, cache["exclude_paths"]),
        "duration_ms": duration_ms,
        "kado_reads": len(entries),
    }
    print(f"[moc-tree] placeholder.build {json.dumps(placeholder_stats)}", file=sys.stderr)
    print(f"[moc-tree] moc-cache.build {json.dumps(moc_cache_stats)}", file=sys.stderr)


def run_with_client(client, config: dict) -> tuple[dict, dict]:
    """Build both outputs from a (real or fake) Kado client.

    The testable seam: callers inject a client and a parsed config; this returns
    `(cache, feed)` without touching disk —
        cache — the MocStructureCache dict (written to moc-structure-cache.yaml)
        feed  — the cache-builder JSON feed (map_notes + placeholder_links, stdout)
    `run()` wires the real client + config file + output path around it.

    Emits the placeholder.build / moc-cache.build observability events to stderr
    (M2/M4/M7); stdout stays JSON-feed-only.
    """
    started = time.monotonic()
    scan_result = moc_scan.scan(client, config)
    entries, placeholder_links, placeholder_stats = build_entries(
        client, scan_result, _SCRIPT_DIR, config=config
    )
    cache = assemble_cache(config, entries, placeholder_links)
    feed = build_cache_builder_feed(entries, placeholder_links)
    duration_ms = int((time.monotonic() - started) * 1000)
    _emit_build_telemetry(cache, placeholder_stats, duration_ms)
    return cache, feed


def run(config_path: str, output_path: str) -> dict:
    """Load config, connect to Kado, build both outputs.

    Writes the MOC-structure-cache YAML to `output_path` (atomic) and prints the
    cache-builder JSON feed to stdout so `moc-tree-builder.py > moc-output.json`
    keeps working (vault-explorer Step 9). ALL progress/warnings go to stderr —
    stdout carries the JSON feed only, or it would corrupt the downstream
    json.load (feedback_never_redirect_stderr_into_json).
    """
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

    cache, feed = run_with_client(client, config)
    print(
        f"[moc-tree] Assembled {len(cache['entries'])} entr(y/ies), "
        f"{len(feed['map_notes'])} map_note(s), "
        f"{len(feed['placeholder_links'])} placeholder(s)",
        file=sys.stderr,
    )

    write_cache_atomic(cache, output_path)
    print(
        f"[moc-tree] MOC-structure cache written: {output_path} "
        f"({os.path.getsize(output_path)} bytes)",
        file=sys.stderr,
    )

    # cache-builder feed → stdout (JSON only).
    json.dump(feed, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
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
