#!/usr/bin/env python3
# version: 0.2.0
"""state-promoter.py — Detect approval ticks and flip tomo.state via Kado.

Two public functions:
  check_tick(body, doc_type) -> bool
      Detect whether the user has ticked the approval/accept box in a
      Tomo-produced workflow doc body.

  flip_state(client, path, doc_type, from_state, to_state, run_id, ...) -> bool
      Validate the transition, then write_frontmatter with a merge-mode payload.
      Retry-once on KadoConcurrencyError (idempotent if already at to_state).

CLI mode:
  python3 state-promoter.py check-tick <path> <doc_type>
      exits 0 ticked, 10 not ticked, 11 malformed/unreadable

  python3 state-promoter.py flip <path> <doc_type> <from_state> <to_state> <run_id> [<expected_modified>]
      exits 0 success, 1 transition rejected, 2 concurrency conflict (persistent)

ADR-3 (SDD §Architecture Decisions): orchestrator-embedded logic; this script is
imported by tests AND invoked from the orchestrator via shell.

Spec: docs/XDD/specs/017-tomo-lifecycle-tags/solution.md §Implementation Examples
AC:   AC-3.1, AC-3.2, AC-3.3, AC-3.4, AC-3.5
"""
from __future__ import annotations

import datetime
import re
import sys
from datetime import timezone

from lib.kado_client import KadoClient, KadoConcurrencyError
from lib.tomo_lifecycle import validate_transition


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# suggestions / suggestions-fan: top-level header approval box
_RE_APPROVED = re.compile(r"^\s*-\s+\[x\]\s+Approved", re.MULTILINE | re.IGNORECASE)

# moc-proposal: any cluster's Accept checkbox
_RE_ACCEPT = re.compile(r"^\s*-\s+\[x\]\s+Accept", re.MULTILINE | re.IGNORECASE)


# ---------------------------------------------------------------------------
# check_tick
# ---------------------------------------------------------------------------

def check_tick(body: str, doc_type: str) -> bool:
    """Detect whether the user has ticked the approval/accept box.

    - suggestions, suggestions-fan: looks for "- [x] Approved" line.
    - garden-audit: looks for the top-level "- [x] Approved" line (ADR-1 revised —
      garden-audit now gates on an explicit approve box like suggestions).
    - moc-proposal: looks for ANY "- [x] Accept" line.

    Returns False (not True) on empty body with a warning on stderr.
    """
    if not body or not body.strip():
        print(
            f"state-promoter.check_tick: empty body for doc_type={doc_type!r}; "
            "lifecycle.check_tick_warning: body empty",
            file=sys.stderr,
        )
        return False

    if doc_type in ("suggestions", "suggestions-fan", "garden-audit"):
        return bool(_RE_APPROVED.search(body))
    if doc_type == "moc-proposal":
        return bool(_RE_ACCEPT.search(body))
    # Unknown doc_type: log and return False
    print(
        f"state-promoter.check_tick: unknown doc_type={doc_type!r}; returning False",
        file=sys.stderr,
    )
    return False


# ---------------------------------------------------------------------------
# flip_state
# ---------------------------------------------------------------------------

def flip_state(
    client: KadoClient,
    path: str,
    doc_type: str,
    from_state: str,
    to_state: str,
    run_id: str,
    expected_modified: int | None = None,
) -> bool:
    """Validate transition, then write_frontmatter with merge-mode payload.

    Only `state` and `updated_at` are included in the merge payload — all other
    existing frontmatter keys (doc_type, run_id, source_*, user tags) are
    preserved automatically by Kado's merge mode.

    Returns True on successful transition, False if transition is invalid.

    Retry-once on KadoConcurrencyError:
      - Re-read frontmatter; if current state == to_state → idempotent no-op.
      - Else: retry once with the new modified value; if still raises → re-raise.
    """
    if not validate_transition(doc_type, from_state, to_state):
        print(
            f"state-promoter.flip_state: lifecycle.transition_rejected "
            f"doc_type={doc_type!r} {from_state!r}→{to_state!r}",
            file=sys.stderr,
        )
        return False

    tomo_block = {
        "state": to_state,
        "updated_at": datetime.datetime.now(timezone.utc).isoformat(),
    }
    try:
        client.write_frontmatter(
            path,
            frontmatter={"tomo": tomo_block},
            mode="merge",
            expected_modified=expected_modified,
        )
    except KadoConcurrencyError:
        _handle_concurrency_retry(client, path, doc_type, from_state, to_state, run_id)
    return True


def _handle_concurrency_retry(
    client: KadoClient,
    path: str,
    doc_type: str,
    from_state: str,
    to_state: str,
    run_id: str,
) -> None:
    """Retry logic for KadoConcurrencyError — separated for single-responsibility."""
    latest = client.read_frontmatter(path)
    current_state = (latest.get("content") or {}).get("tomo", {}).get("state")
    if current_state == to_state:
        return  # already flipped by someone else; idempotent no-op

    new_modified = latest.get("modified")
    tomo_block = {
        "state": to_state,
        "updated_at": datetime.datetime.now(timezone.utc).isoformat(),
    }
    # Second attempt — let any exception propagate to orchestrator
    client.write_frontmatter(
        path,
        frontmatter={"tomo": tomo_block},
        mode="merge",
        expected_modified=new_modified,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli_check_tick(argv: list[str]) -> int:
    """check-tick <path> <doc_type> — exit 0 ticked, 10 not, 11 malformed."""
    if len(argv) < 2:
        print("Usage: state-promoter.py check-tick <path> <doc_type>", file=sys.stderr)
        return 11
    path, doc_type = argv[0], argv[1]
    try:
        client = KadoClient()
        note = client.read_note(path)
        body = note.get("content", "")
    except Exception as exc:
        print(f"state-promoter: failed to read {path!r}: {exc}", file=sys.stderr)
        return 11
    result = check_tick(body, doc_type)
    return 0 if result else 10


def _cli_flip(argv: list[str]) -> int:
    """flip <path> <doc_type> <from_state> <to_state> <run_id> [expected_modified]."""
    if len(argv) < 5:
        print(
            "Usage: state-promoter.py flip <path> <doc_type> <from_state> <to_state> "
            "<run_id> [expected_modified]",
            file=sys.stderr,
        )
        return 1
    path, doc_type, from_state, to_state, run_id = argv[:5]
    expected_modified: int | None = None
    if len(argv) >= 6:
        try:
            expected_modified = int(argv[5])
        except ValueError:
            print(
                f"state-promoter: expected_modified must be an integer, got {argv[5]!r}",
                file=sys.stderr,
            )
            return 1

    client = KadoClient()
    try:
        success = flip_state(
            client, path, doc_type, from_state, to_state, run_id,
            expected_modified=expected_modified,
        )
    except KadoConcurrencyError as exc:
        print(f"state-promoter: persistent concurrency conflict on {path!r}: {exc}", file=sys.stderr)
        return 2
    return 0 if success else 1


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Usage: state-promoter.py <check-tick|flip> ...", file=sys.stderr)
        return 1
    cmd, rest = args[0], args[1:]
    if cmd == "check-tick":
        return _cli_check_tick(rest)
    if cmd == "flip":
        return _cli_flip(rest)
    print(f"state-promoter: unknown command {cmd!r}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
