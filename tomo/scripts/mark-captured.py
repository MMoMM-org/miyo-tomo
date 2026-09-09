#!/usr/bin/env python3
# version: 1.2.0
"""mark-captured.py — Mark processed inbox source items with tomo.state=captured.

Reads the state-file, finds all items with status=done, and writes a
tomo: frontmatter block (doc_type=source, state=captured) to each item
via kado_client.write_frontmatter (merge mode). Idempotent — Kado's
merge mode naturally handles re-runs: the state field is simply
overwritten with the same value.

Non-markdown items (audio, binaries, stray text) are skipped — they
carry no frontmatter.

The state-file replay joins on `item_key` — the item's vault-relative path,
verbatim (spec 034 ADR-1/ADR-2). Two inbox items in different subfolders can
share a bare filename, and this script drives a vault write: keyed on the
filename, one item's entry masks its namesake's and the captured mark lands on
the wrong note, or on no note at all. An entry that cannot be addressed
unambiguously is declined — nothing is written for it.

Called by the orchestrator after successfully writing the suggestions
document to the vault (Phase C5).

Usage:
    python3 scripts/mark-captured.py \
        --state tomo-tmp/inbox-state.jsonl \
        --run-id <run-id>

Exit codes:
    0 — all addressable done items marked (or already marked, or no state-file
        / no done items — a tag-handler-only batch records no per-item state).
        An item that cannot be addressed is declined, counted, and reported;
        declining is not a failure.
    1 — one or more items failed (partial, logged to stderr)
    2 — fatal error (no Kado connection)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.doc_frontmatter import build_tomo_block  # noqa: E402
from lib.inbox_state import display_stem, last_state_per_item_key  # noqa: E402
from lib.kado_client import KadoClient, KadoError  # noqa: E402
from lib.squelch_persist import persist_rejected_clusters  # noqa: E402


def _load_squelch_config(config_path: str) -> dict:
    """Load squelch_runs from vault-config.yaml; returns default if missing."""
    squelch_runs = 3
    try:
        import yaml  # type: ignore[import]
        with open(config_path, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}
        squelch_runs = int(
            cfg.get("tomo", {})
            .get("moc_proposal", {})
            .get("squelch_runs", 3)
        )
    except Exception:  # noqa: BLE001
        pass
    return {"squelch_runs": squelch_runs}


def main() -> int:
    p = argparse.ArgumentParser(
        description="Mark done inbox items with tomo.state=captured."
    )
    p.add_argument("--state", required=True, help="Path to inbox-state.jsonl")
    p.add_argument("--run-id", required=True, help="Run-id string for tomo block")
    p.add_argument(
        "--squelch-registry",
        default="state/moc-squelch.json",
        help="Path to MOC squelch registry (default: state/moc-squelch.json)",
    )
    p.add_argument(
        "--config",
        default="config/vault-config.yaml",
        help="vault-config.yaml path (used for squelch_runs only)",
    )
    args = p.parse_args()

    state_path = Path(args.state)
    if not state_path.exists():
        # No state file means no per-item state was recorded this run — e.g. a
        # batch consisting only of tag-handler captures, which route through the
        # handled lane and never seed the state file. There is simply nothing to
        # mark; this is not an error (same outcome as the "no done items" path
        # below). FATAL-ing here instead caused a Pass-1 hard stop and tempted
        # the orchestrator to improvise a state-file write.
        print(
            f"mark-captured: no state-file ({state_path}); no items to mark",
            file=sys.stderr,
        )
        return 0

    try:
        client = KadoClient()
    except KadoError as exc:
        print(f"FATAL: Cannot connect to Kado: {exc}", file=sys.stderr)
        return 2

    # Hardening: last_state_per_item_key() fails open on a corrupt line (bad
    # JSON, or no item_key) — it used to drop the line with no trace at all.
    # skip_report makes that audible without turning the skip into an abort.
    state_skip_report: dict[str, int] = {}
    state = last_state_per_item_key(state_path, skip_report=state_skip_report)
    state_lines_skipped = sum(state_skip_report.values())
    if state_lines_skipped:
        print(
            f"mark-captured: {state_lines_skipped} line(s) of {state_path} "
            f"skipped during replay (malformed_json="
            f"{state_skip_report.get('malformed_json', 0)}, missing_item_key="
            f"{state_skip_report.get('missing_item_key', 0)}) — run continued "
            f"past the corrupt line(s)",
            file=sys.stderr,
        )
    # #116: scope to THIS run's entries. inbox-state.jsonl is append-only and
    # never truncated, so an unfiltered done-list re-stamps prior-run items
    # (source/captured) even when their source notes are gone.
    done_keys = [
        k
        for k, e in state.items()
        if e.get("status") == "done" and e.get("run_id") == args.run_id
    ]

    if not done_keys:
        print("mark-captured: no done items to mark", file=sys.stderr)
        return 0

    marked = 0
    errors = 0
    declined = 0
    skipped_non_md = 0
    squelched_total = 0
    registry_path = Path(args.squelch_registry)
    squelch_cfg = _load_squelch_config(args.config)

    for item_key in sorted(done_keys):
        entry = state[item_key]
        stem = display_stem(entry, item_key)
        # The write target is the entry's own stored path — never a path
        # reconstructed from the display stem. Without a path the item cannot be
        # addressed, so it is declined rather than guessed at.
        path = entry.get("path", "")
        if not path:
            print(
                f"  [declined] {stem}: no path recorded for item_key={item_key}; "
                f"nothing written",
                file=sys.stderr,
            )
            declined += 1
            continue

        # Frontmatter lives only in markdown files. Skip audio, binaries, etc.
        # Without this guard, kado-write operation=frontmatter rejects non-.md
        # paths with VALIDATION_ERROR, which would count as a hard failure.
        if not path.lower().endswith(".md"):
            print(
                f"  [skip] {stem}: non-markdown path, no frontmatter ({path})",
                file=sys.stderr,
            )
            skipped_non_md += 1
            continue

        print(f"  [{stem}] marking {path}", file=sys.stderr)
        block = build_tomo_block(
            doc_type="source",
            state="captured",
            run_id=args.run_id,
        )
        try:
            # Read first to get the modified timestamp, then write with
            # expected_modified for optimistic-concurrency guard. Matches
            # state-promoter.py's existing pattern — protects against
            # concurrent edits (e.g. user editing the note in Obsidian
            # while /inbox runs). Without this guard, a concurrent edit
            # would be silently overwritten.
            read_result = client.read_frontmatter(path)
            expected_modified = read_result.get("modified")
            client.write_frontmatter(
                path, {"tomo": block}, mode="merge",
                expected_modified=expected_modified,
            )
            marked += 1
        except KadoError as exc:
            print(f"  [error] Cannot write {path}: {exc}", file=sys.stderr)
            errors += 1
            continue

        # Squelch-persist: for MOC proposal-docs, record rejected clusters.
        # Accept both naming conventions: the new canonical Tomo form
        # `<YYYY-MM-DD>_<HHMM>_moc-proposal-<slug>.md` and the legacy
        # `tomo-moc-proposal-<YYYYMMDD>-<HHMM>-<slug>.md` (pre-F-55).
        filename = os.path.basename(path)
        is_moc_proposal = filename.endswith(".md") and (
            filename.startswith("tomo-moc-proposal-")
            or "_moc-proposal-" in filename
        )
        if is_moc_proposal:
            try:
                result = client.read_note(path)
                doc_text = result.get("content", "")
            except KadoError as exc:
                print(
                    f"  [warn] {stem}: cannot read proposal-doc for squelch "
                    f"({exc}); skipping squelch-persist",
                    file=sys.stderr,
                )
                doc_text = ""
            if doc_text:
                try:
                    n_squelched = persist_rejected_clusters(
                        doc_text,
                        filename=filename,
                        registry_path=registry_path,
                        config=squelch_cfg,
                    )
                    if n_squelched:
                        print(
                            f"  [{stem}] squelch-persist: {n_squelched} rejected "
                            f"cluster(s) written to {registry_path}",
                            file=sys.stderr,
                        )
                        squelched_total += n_squelched
                except Exception as exc:  # noqa: BLE001
                    print(
                        f"  [warn] {stem}: squelch-persist failed ({exc}); continuing",
                        file=sys.stderr,
                    )

    print(
        f"mark-captured: marked={marked} errors={errors} declined={declined} "
        f"skipped_non_md={skipped_non_md} squelched={squelched_total}",
        file=sys.stderr,
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
