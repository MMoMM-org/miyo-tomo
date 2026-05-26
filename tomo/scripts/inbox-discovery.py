#!/usr/bin/env python3
# version: 0.3.0
"""inbox-discovery.py — Unified byFrontmatter discovery + bucketing + drift detection.

Replaces the legacy state-init.py listDir + body-read discovery path (F-47 Phase 3).
Performs NO body-reads — state is read from frontmatter only (AC-2.1).

CLI: python3 inbox-discovery.py <inbox_path> [--json] [--run-id <id>]

Outputs JSON object on stdout:
  {
    "buckets": {
      "pendingApproval": [{"path": str, "modified": int, "frontmatter": {...}}, ...],
      "pendingAccept":   [...],
      "pendingApply":    [...],
      "captured":        [...],
      "newSources":      [{"path": str, "modified": int}, ...]
    },
    "drift": bool,                # True iff captured.count > 0 AND all pending* lists empty
    "metrics": {
      "byFrontmatter_hits": int,  # Total hits across all 4 byFrontmatter calls
      "listDir_hits": int,        # Items returned by listDir
      "phase_a_duration_ms": int, # Wall-clock for the 5 Kado calls + bucketing
      "token_estimate": int,      # Rough orchestrator-side cost: response_bytes // 4
      "run_id": str               # Echoed from --run-id or auto-generated UTC ISO
    }
  }

Spec: docs/XDD/specs/017-tomo-lifecycle-tags/ — PRD §7 Tracking Requirements
AC:   AC-2.1, AC-2.2, AC-2.3, AC-5a.1
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.kado_client import KadoClient, KadoError  # noqa: E402


# ---------------------------------------------------------------------------
# Bucket routing: doc_type → bucket name
# ---------------------------------------------------------------------------

_DOC_TYPE_TO_BUCKET: dict[str, str] = {
    "suggestions": "pendingApproval",
    "suggestions-fan": "pendingApproval",
    "moc-proposal": "pendingAccept",
    "instructions": "pendingApply",
}


# ---------------------------------------------------------------------------
# Core discover function
# ---------------------------------------------------------------------------

def discover(client: KadoClient, inbox_path: str, run_id: str | None = None) -> dict:
    """Discover all Tomo-managed and fresh source docs in inbox_path.

    Four byFrontmatter calls + one listDir call.
    Kado frontmatterValueMatches uses strict equality only — no wildcard support.
    Three separate calls cover pending-approval / pending-accept / pending-apply;
    one call covers captured.  No body-reads — state is derived from frontmatter only.

    Parameters
    ----------
    client:     Initialised KadoClient.
    inbox_path: Vault-relative path to the inbox folder (e.g. "100 Inbox/").
    run_id:     Optional run identifier echoed into metrics. Auto-generated if None.

    Returns
    -------
    dict with keys: buckets (dict), drift (bool), metrics (dict per PRD §7).
    """
    # Normalise trailing slash for consistent path_prefix
    path_prefix = inbox_path.rstrip("/") + "/"

    # Start phase-A timer + accumulate response byte count for token_estimate
    _t_start = time.perf_counter()
    response_bytes = 0

    if run_id is None:
        run_id = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # --- Calls 1-3: pending-<value> docs (strict equality; no wildcard) ------
    # Kado search-adapter performs exact-match only (search-adapter.ts:381).
    # The original AC-2.1 "ONE call for pending-*" wording assumed wildcard
    # support that does not exist; three calls are the correct implementation.
    _pending_states = ["pending-approval", "pending-accept", "pending-apply"]
    pending_hits: list = []
    for state in _pending_states:
        hits = client.search_by_frontmatter(
            f"tomo.state={state}",
            path_prefix=path_prefix,
            limit=500,
        )
        pending_hits.extend(hits)
        response_bytes += len(json.dumps(hits, ensure_ascii=False))

    # --- Call 4: captured docs ------------------------------------------------
    captured_hits = client.search_by_frontmatter(
        "tomo.state=captured",
        path_prefix=path_prefix,
        limit=500,
    )
    response_bytes += len(json.dumps(captured_hits, ensure_ascii=False))

    # --- Call 5: all files in inbox (for newSources set-diff) ----------------
    listdir_items = client.list_dir(path_prefix, depth=1, limit=500)
    response_bytes += len(json.dumps(listdir_items, ensure_ascii=False))

    # --- Bucket pending hits by doc_type -------------------------------------
    buckets: dict[str, list] = {
        "pendingApproval": [],
        "pendingAccept": [],
        "pendingApply": [],
        "captured": [],
        "newSources": [],
    }

    for hit in pending_hits:
        tomo_block = (hit.get("frontmatter") or {}).get("tomo") or {}
        doc_type = tomo_block.get("doc_type", "")
        bucket_name = _DOC_TYPE_TO_BUCKET.get(doc_type)
        if bucket_name is None:
            print(
                f"[inbox-discovery] WARNING: unknown doc_type={doc_type!r} in {hit.get('path')!r}",
                file=sys.stderr,
            )
            continue
        buckets[bucket_name].append(hit)

    buckets["captured"] = captured_hits

    # --- newSources: .md files not in pending or captured --------------------
    known_paths = {h["path"] for h in pending_hits} | {h["path"] for h in captured_hits}
    for item in listdir_items:
        item_path = item.get("path", "")
        item_type = (item.get("type") or item.get("kind") or "").lower()
        if item_type and item_type != "file":
            continue  # skip subdirectories
        if not item_path.endswith(".md"):
            continue  # skip non-markdown files
        if item_path in known_paths:
            continue
        buckets["newSources"].append({
            "path": item_path,
            "modified": item.get("modified", 0),
        })

    # --- Drift detection (AC-5a.1) -------------------------------------------
    pending_total = (
        len(buckets["pendingApproval"])
        + len(buckets["pendingAccept"])
        + len(buckets["pendingApply"])
    )
    drift = len(buckets["captured"]) > 0 and pending_total == 0

    # --- PRD §7 metrics ------------------------------------------------------
    # token_estimate: rough orchestrator-side reading cost.
    # response_bytes covers all Kado payloads the orchestrator will read in
    # via discovery.json. Divide by 4 — typical English/JSON chars-per-token.
    # Body-reads in state-promoter are tracked by its own events, not here.
    metrics = {
        "byFrontmatter_hits": len(pending_hits) + len(captured_hits),
        "listDir_hits": len(listdir_items),
        "phase_a_duration_ms": int((time.perf_counter() - _t_start) * 1000),
        "token_estimate": response_bytes // 4,
        "run_id": run_id,
    }

    return {"buckets": buckets, "drift": drift, "metrics": metrics}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Unified byFrontmatter discovery for the Tomo inbox."
    )
    p.add_argument("inbox_path", help="Vault-relative inbox path (e.g. '100 Inbox/')")
    p.add_argument(
        "--json", action="store_true", dest="output_json",
        help="Output JSON on stdout (default: also JSON, kept for explicitness)"
    )
    p.add_argument(
        "--run-id", default=None, dest="run_id",
        help="Run identifier echoed into metrics. Auto-generated (UTC ISO) if omitted."
    )
    return p


def main() -> int:
    args = _build_arg_parser().parse_args()

    try:
        client = KadoClient()
    except KadoError as exc:
        print(f"ERROR: Kado client init failed: {exc}", file=sys.stderr)
        return 1

    try:
        result = discover(client, args.inbox_path, run_id=args.run_id)
    except KadoError as exc:
        print(f"ERROR: Discovery failed: {exc}", file=sys.stderr)
        return 1

    # Log discovery summary to stderr as a JSON line — parsable by
    # scripts/measure-f47-token-cost.py and aligned with PRD §7 properties.
    # Never pollute stdout JSON — ref: feedback_never_redirect_stderr_into_json.
    buckets = result["buckets"]
    metrics = result["metrics"]
    event = {
        "event": "lifecycle.discovery",
        "run_id": metrics["run_id"],
        "byFrontmatter_hits": metrics["byFrontmatter_hits"],
        "listDir_hits": metrics["listDir_hits"],
        "pending_body_reads": 0,  # discovery is read-only on frontmatter; state-promoter tracks its own body reads
        "bucket_counts": {
            "pendingApproval": len(buckets["pendingApproval"]),
            "pendingAccept": len(buckets["pendingAccept"]),
            "pendingApply": len(buckets["pendingApply"]),
            "captured": len(buckets["captured"]),
            "newSources": len(buckets["newSources"]),
        },
        "drift_hint_emitted": result["drift"],  # orchestrator suppresses when --recover set
        "phase_a_duration_ms": metrics["phase_a_duration_ms"],
        "token_estimate": metrics["token_estimate"],
    }
    print(f"[inbox-discovery] {json.dumps(event, ensure_ascii=False)}", file=sys.stderr)

    # JSON on stdout — clean output, no stderr contamination
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
