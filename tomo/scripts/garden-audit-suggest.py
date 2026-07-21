#!/usr/bin/env python3
# version: 0.2.0
"""garden-audit-suggest.py — `--suggest` second-pass helper (spec 030 T7.4).

The garden-auditor agent invokes this when the user has ticked
`- [ ] Suggest targets` on one or more dead_link/broken_up findings in a published
garden-audit report and re-runs `/garden-audit --suggest`. It:

  1. reads the in-vault report `.md`, its wire `.json`, and the MOC-structure cache,
  2. enriches ONLY the Suggest-ticked blocks with a candidate `Pick one:` list
     (via garden-audit-render.enrich_report_with_suggestions — the SSoT),
  3. writes the enriched report to --output for the agent to re-upload via
     kado-write-file (no new external surface — the agent owns transport).

Mirrors garden-audit-configure.py as a deterministic mode-support helper: no LLM,
no Kado access here (the agent fetches the report/wire; the cache is local).

CLI (agent calls bare from the instance cwd; --output defaults to --report in-place):
  python3 scripts/garden-audit-suggest.py             # instance-relative defaults
Switches (--report / --wire / --cache / --output) are host/test overrides only.

Degrades gracefully: an unreadable wire/cache yields no candidates (the report is
returned intact) rather than crashing — the agent still re-uploads a valid report.

Design notes: docs/tomo/scripts/garden-audit-suggest.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

# Load the hyphen-named renderer to reuse enrich_report_with_suggestions (SSoT).
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "garden_audit_render", SCRIPTS_DIR / "garden-audit-render.py"
)
_render = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_render)


def _load_wire(path: str) -> dict:
    """Load the wire JSON, or {} (+warn) on any failure — no candidates then."""
    try:
        with open(path, encoding="utf-8") as fh:
            wire = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"warning: garden-audit-suggest: wire unreadable ({exc})", file=sys.stderr)
        return {}
    return wire if isinstance(wire, dict) else {}


def _load_cache_entries(path: str) -> list[dict]:
    """Load the MOC-structure cache entries, or [] (+warn) on any failure."""
    try:
        with open(path, encoding="utf-8") as fh:
            cache = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError) as exc:
        print(f"warning: garden-audit-suggest: cache unreadable ({exc})", file=sys.stderr)
        return []
    entries = cache.get("entries") if isinstance(cache, dict) else None
    return entries or []


def run_suggest(report_path: str, wire_path: str, cache_path: str) -> str:
    """Read report + wire + cache → enriched report string (raises on report I/O)."""
    with open(report_path, encoding="utf-8") as fh:
        report_md = fh.read()
    wire = _load_wire(wire_path)
    entries = _load_cache_entries(cache_path)
    return _render.enrich_report_with_suggestions(report_md, wire, entries)


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Enrich Suggest-ticked garden-audit findings with candidate picks."
        )
    )
    # Instance-relative defaults (spec 030): the agent calls this bare after
    # fetching the published report + wire into tomo-tmp; --output defaults to
    # --report (in-place enrichment). Switches are host/test overrides only.
    p.add_argument(
        "--report", default="tomo-tmp/suggest-report.md",
        help="Path to the published report .md",
    )
    p.add_argument(
        "--wire", default="tomo-tmp/suggest-wire.json",
        help="Path to the report's wire .json",
    )
    p.add_argument(
        "--cache", default="config/moc-structure-cache.yaml",
        help="Path to moc-structure-cache.yaml",
    )
    p.add_argument(
        "--output", default=None,
        help="Output path for the enriched report .md (defaults to --report, in-place).",
    )
    args = p.parse_args()

    try:
        enriched = run_suggest(args.report, args.wire, args.cache)
    except OSError as exc:
        print(f"error: garden-audit-suggest: cannot read report: {exc}", file=sys.stderr)
        return 1

    output = args.output or args.report  # in-place by default
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(enriched, encoding="utf-8")

    n_picks = enriched.count("Pick one")
    print(
        f"garden-audit-suggest: enriched {n_picks} finding(s) → {output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
