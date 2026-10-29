#!/usr/bin/env python3
# version: 0.24.0
"""instructions-diff.py — Reconcile parsed-suggestions.json with instructions.json.

Pass-2 coverage audit: every approved suggestion should produce a
well-formed instruction, and the instruction set should not contain
actions without a matching source in the suggestions doc. This script
cross-checks the two JSONs item-by-item and surfaces:

  - Count mismatches per action kind (expected from suggestions vs.
    actual in instructions.json).
  - Per-confirmed-item coverage: each atomic/create_moc item should have
    exactly one file action (move_note or create_moc) plus one
    link_to_moc per parent_moc. link_to_moc coverage is counted as
    (note, MOC) pairs so a #70-batched action (several notes merged under
    one target_moc + new_section) credits each note via its bullets.
  - Daily-update coverage: each accepted tracker/log_entry/log_link in
    parsed-suggestions should produce one matching action.
  - Skip / delete coverage: explicit skipped[] entries and daily-only
    delete inferences reconciled.
  - Observations (soft, non-blocking): e.g. approved `create_moc` with
    no confirmed items linking up to it.
  - Garden-audit docs (confirmed_items carrying garden_action) route to a
    dedicated mode: expected instruction counts per garden_action
    (resolve_dead_link / remove_up_link / add_relationship / file_note →
    link_to_moc + add_relationship) plus path-anchored per-item coverage.

Usage:
  python3 scripts/instructions-diff.py \\
    --suggestions tomo-tmp/parsed-suggestions.json \\
    --instructions tomo-tmp/rendered/instructions.json

  # Shorthand with default paths relative to CWD:
  python3 scripts/instructions-diff.py          # uses tomo-tmp/ defaults

Exit codes:
  0 — all expected actions accounted for (observations OK)
  1 — hard mismatch (count disagreement or missing/extra actions)
  2 — I/O or JSON parse error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

# The audit's logic lives in lib/instructions_diff_*.py (#216); this file keeps
# the CLI (args, file loading, exit code). Every name below is re-exported so
# callers that load this script by path keep reaching it here.
from lib.item_key import derive as _item_key  # noqa: F401
from lib.render_helpers import WITHDRAWAL_GUARDS  # noqa: F401
from lib.instructions_diff_keys import (  # noqa: F401
    _BULLET_RE,
    _bullet_titles,
    _confirmed_key,
    _daily_key,
    _key_segments,
    _keys_match,
    _moc_stem,
    _parse_supporting_items,
    _same_note_as_any,
    _stem,
    _unique_members,
)
from lib.instructions_diff_expected import (  # noqa: F401
    derive_expected,
    group_id,
    summarize_actual,
)
from lib.instructions_diff_reconcile import (  # noqa: F401
    _CLASH_WITHDRAWAL_GUARDS,
    _subtract_skipped_assets,
    _subtract_skipped_daily,
    _subtract_unresolvable_links,
    _subtract_withdrawn_deletes,
    _subtract_withheld_moves,
    _unresolvable_link_notes,
)
from lib.instructions_diff_extensions import _reconcile_extensions  # noqa: F401
from lib.instructions_diff_garden import (  # noqa: F401
    _GARDEN_EXPECTED_KINDS,
    GARDEN_ACTION_ORDER,
    _garden_item_covered,
    _is_garden_parsed,
    run_diff_garden,
)
from lib.instructions_diff_report import ACTION_ORDER, run_diff  # noqa: F401


def _load_tag_handler_groups(groups_dir: str | None) -> list[dict]:
    """Load tag-handler group-result JSONs from `groups_dir` (mirrors the
    renderer's loader). Returns [] when the dir is missing/empty so an absent
    registry leaves coverage unchanged."""
    if not groups_dir:
        return []
    d = Path(groups_dir)
    if not d.is_dir():
        return []
    groups: list[dict] = []
    for f in sorted(d.glob("*.json")):
        try:
            groups.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return groups


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(2)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Compare parsed-suggestions.json vs instructions.json."
    )
    p.add_argument(
        "--suggestions", default="tomo-tmp/parsed-suggestions.json",
        help="Path to parsed-suggestions.json (default: tomo-tmp/parsed-suggestions.json)",
    )
    p.add_argument(
        "--instructions", default="tomo-tmp/rendered/instructions.json",
        help="Path to instructions.json (default: tomo-tmp/rendered/instructions.json)",
    )
    p.add_argument(
        "--groups-dir", default="tomo-tmp/tag-handler-groups",
        help="Dir of tag-handler group-result JSONs (default: tomo-tmp/tag-handler-groups). "
             "Used to count expected delete_source for approved tag-handler groups.",
    )
    args = p.parse_args()

    parsed = load_json(Path(args.suggestions))
    instrs = load_json(Path(args.instructions))
    tag_handler_groups = _load_tag_handler_groups(args.groups_dir)

    rc, _obs = run_diff(parsed, instrs, tag_handler_groups)
    return rc


if __name__ == "__main__":
    sys.exit(main())
