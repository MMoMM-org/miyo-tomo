# cost_history.py — Append one record of what a triage run cost.
# version: 0.2.0
"""Persist the observed Kado cost of a completed /inbox run.

One append-only JSONL record per run, in the instance's persistent state
directory beside the squelch registry. Entries accumulate and are never
rewritten, so a later reader can compare runs and tell a pipeline regression
(the base cost moved) from a busy run (more items, more destination folders).

Public API:

    build_entry(...) -> dict
        Assemble one record. The two folder fields are OMITTED when None —
        they are present only on the paths where the reducer actually ran.
        Zero would assert a measurement nobody took.

    append_entry(entry, history_path) -> bool
        Append one record. Never raises: an unwritable history warns to stderr
        and returns False. Measurement must never fail a run.

    record_run(...) -> bool
        The reducer's form. Reads triage's own metrics back from
        routing-plan.json, combines them with the folder counts the caller
        measured, and appends. Used by the two paths whose folder counts do not
        exist until after triage has finished.

Stdlib only — no new dependencies.
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

# cwd-relative, matching mark-captured.py's state/moc-squelch.json default —
# correct for the instance runtime, overridable for host and test runs.
DEFAULT_HISTORY_PATH = "state/inbox-cost-history.jsonl"


def _now_iso() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def build_entry(
    *,
    run_id: str,
    action: str,
    item_count: int,
    base_kado_calls: int,
    total_kado_calls: int,
    folder_listing_calls: int | None = None,
    distinct_destination_folders: int | None = None,
    timestamp: str | None = None,
) -> dict:
    """Assemble one cost-history record.

    Args:
        run_id:               Identifier of the run this record describes.
        action:               The action triage routed to (suggest, synthesize,
                              idle, transcribe, fan-resolve).
        item_count:           Inbox markdown files this run's listing found.
        base_kado_calls:      Observed round trips spent on the fixed pipeline
                              cost — the recursive listing and the embed
                              extraction (ADR-3).
        total_kado_calls:     Observed round trips for the whole triage run.
        folder_listing_calls: Round trips the reducer spent listing destination
                              folders; None on the paths where it never ran.
        distinct_destination_folders: How many distinct folders produced them;
                              None on the paths where the reducer never ran.
        timestamp:            Override for the record's ISO-8601 stamp.
    """
    entry = {
        "timestamp": timestamp or _now_iso(),
        "run_id": run_id,
        "action": action,
        "item_count": int(item_count),
        "base_kado_calls": int(base_kado_calls),
        "total_kado_calls": int(total_kado_calls),
    }
    if folder_listing_calls is not None:
        entry["folder_listing_calls"] = int(folder_listing_calls)
    if distinct_destination_folders is not None:
        entry["distinct_destination_folders"] = int(distinct_destination_folders)
    return entry


def append_entry(
    entry: dict, history_path: "str | Path" = DEFAULT_HISTORY_PATH
) -> bool:
    """Append one record as a JSONL line. Returns False if it could not be written."""
    path = Path(history_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except (OSError, TypeError, ValueError) as exc:
        print(
            f"WARNING: could not append to the cost history at {path}: {exc}",
            file=sys.stderr,
        )
        return False
    return True


def _load_json(path: "str | Path") -> dict | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def record_run(
    *,
    run_id: str,
    routing_plan_path: "str | Path",
    folder_listing_calls: int | None = None,
    distinct_destination_folders: int | None = None,
    history_path: "str | Path" = DEFAULT_HISTORY_PATH,
) -> bool:
    """Append the entry for a run whose folder counts the caller has measured.

    The action, item count and call counts come from the routing plan triage
    wrote earlier in the same run — one definition of each figure, rather than
    the caller re-deriving its own.

    Args:
        run_id:               Identifier of the run this record describes.
        routing_plan_path:    routing-plan.json, carrying triage's metrics.
        folder_listing_calls: Round trips spent listing destination folders.
        distinct_destination_folders: How many folders produced them.
        history_path:         Where to append.
    """
    plan = _load_json(routing_plan_path)
    if plan is None:
        print(
            f"WARNING: no readable routing plan at {routing_plan_path} — "
            "this run's cost was not recorded",
            file=sys.stderr,
        )
        return False

    metrics = plan.get("metrics") or {}
    return append_entry(
        build_entry(
            run_id=run_id,
            action=plan.get("action", "unknown"),
            item_count=metrics.get("item_count", 0),
            base_kado_calls=metrics.get("base_kado_calls", 0),
            total_kado_calls=metrics.get("kado_calls", 0),
            folder_listing_calls=folder_listing_calls,
            distinct_destination_folders=distinct_destination_folders,
        ),
        history_path,
    )
