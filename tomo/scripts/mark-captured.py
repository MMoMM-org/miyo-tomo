#!/usr/bin/env python3
# version: 1.0.0
"""mark-captured.py — Mark processed inbox source items with tomo.state=captured.

Reads the state-file, finds all items with status=done, and writes a
tomo: frontmatter block (doc_type=source, state=captured) to each item
via kado_client.write_frontmatter (merge mode). Idempotent — Kado's
merge mode naturally handles re-runs: the state field is simply
overwritten with the same value.

Non-markdown items (audio, binaries, stray text) are skipped — they
carry no frontmatter.

Called by the orchestrator after successfully writing the suggestions
document to the vault (Phase C5).

Usage:
    python3 scripts/mark-captured.py \
        --state tomo-tmp/inbox-state.jsonl \
        --run-id <run-id>

Exit codes:
    0 — all done items marked (or already marked)
    1 — one or more items failed (partial, logged to stderr)
    2 — fatal error (no Kado connection, no state-file)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.doc_frontmatter import build_tomo_block  # noqa: E402
from lib.kado_client import KadoClient, KadoError  # noqa: E402
from lib.squelch_persist import persist_rejected_clusters  # noqa: E402


def last_state_per_stem(state_path: Path) -> dict[str, dict]:
    """Read state-file and return the last entry per stem."""
    state: dict[str, dict] = {}
    for line in state_path.read_text(encoding="utf-8").strip().splitlines():
        entry = json.loads(line)
        state[entry["stem"]] = entry
    return state


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
        print(f"FATAL: state-file not found: {state_path}", file=sys.stderr)
        return 2

    try:
        client = KadoClient()
    except KadoError as exc:
        print(f"FATAL: Cannot connect to Kado: {exc}", file=sys.stderr)
        return 2

    state = last_state_per_stem(state_path)
    done_stems = [s for s, e in state.items() if e.get("status") == "done"]

    if not done_stems:
        print("mark-captured: no done items to mark", file=sys.stderr)
        return 0

    marked = 0
    errors = 0
    skipped_non_md = 0
    squelched_total = 0
    registry_path = Path(args.squelch_registry)
    squelch_cfg = _load_squelch_config(args.config)

    for stem in sorted(done_stems):
        entry = state[stem]
        path = entry.get("path", "")
        if not path:
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
            client.write_frontmatter(path, {"tomo": block}, mode="merge")
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
        f"mark-captured: marked={marked} errors={errors} "
        f"skipped_non_md={skipped_non_md} squelched={squelched_total}",
        file=sys.stderr,
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
