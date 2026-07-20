#!/usr/bin/env python3
# version: 0.1.0
"""garden-audit-configure.py — Wizard-support helper for the garden-auditor agent.

Two modes, invoked by garden-auditor.md during the exclusion wizard:

  --summarize --input <doc.json>
      Reads garden-audit-doc.json in Python (no 256 KB Read-tool cap), computes
      per-folder cluster counts (findings by check), filters to abnormality clusters
      (>=10 absolute findings OR >=20% of total), sorts descending, and writes a
      compact human-readable cluster summary to stdout.  The agent pastes this into
      the wizard prompt instead of reading the doc itself.

  --write --choices <json> --output <config.yaml>
      Receives user wizard choices as a JSON string, composes a schema-valid
      garden-audit-exclusions.yaml, always sets configured: true, and writes it to
      --output.  Bypasses the Write-tool read-before-write trap because the agent
      never needs to read the file first.

Choices JSON shape (for --write):
  {
    "today": "YYYY-MM-DD",           # ISO date; defaults to date.today() if absent
    "exclusions": [                   # may be an empty list
      {
        "target": {"type": "path"|"note"|"tag", "value": "..."},
        "checks": "all" | ["check1", ...],
        "mode": "permanent" | "temporary",
        "reason": "...",
        "push_back_days": 90          # only for mode=temporary; default 90
      }
    ]
  }

Design notes: docs/tomo/scripts/garden-audit-configure.md
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import yaml  # noqa: E402


# ──────────────────────────────────────────────────────────────────────────────
# --summarize
# ──────────────────────────────────────────────────────────────────────────────

_CLUSTER_ABS_THRESHOLD = 10    # absolute findings to qualify as a cluster
_CLUSTER_PCT_THRESHOLD = 0.20  # 20% of total findings


def _top_folder(path: str) -> str:
    """Return the top-level folder prefix of a vault path ('Calendar/' from 'Calendar/Jan.md')."""
    parts = Path(path).parts
    if len(parts) > 1:
        return parts[0] + "/"
    return "(root)"


def summarize(doc_path: str) -> int:
    """Read doc.json, compute clusters, write summary to stdout. Returns exit code."""
    try:
        with open(doc_path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        print(f"[error] garden-audit-doc not found: {doc_path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"[error] Failed to parse garden-audit-doc: {exc}", file=sys.stderr)
        return 1

    findings = doc.get("findings") or []
    total = len(findings)

    if total == 0:
        print("Garden-audit found 0 findings. No clusters to display.")
        return 0

    # Count findings per top-level folder, broken down by check
    by_folder: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for f in findings:
        folder = _top_folder(f.get("target", {}).get("path", "") or "")
        check = f.get("check", "unknown")
        by_folder[folder][check] += 1

    # Filter to abnormality clusters: >= absolute threshold OR >= pct threshold.
    # A folder qualifies when it crosses EITHER bar.
    pct_floor = int(total * _CLUSTER_PCT_THRESHOLD)
    clusters = [
        (folder, dict(counts))
        for folder, counts in by_folder.items()
        if (
            sum(counts.values()) >= _CLUSTER_ABS_THRESHOLD
            or sum(counts.values()) >= pct_floor
        )
    ]
    clusters.sort(key=lambda x: sum(x[1].values()), reverse=True)

    # Count unique note paths across findings
    note_paths = {f.get("target", {}).get("path", "") for f in findings}
    note_count = len(note_paths)

    lines = [f"Garden-audit found {total} findings across {note_count} notes."]
    if clusters:
        lines.append("")
        lines.append("Top finding clusters (>= 10 findings or >= 20% of total):")
        for folder, counts in clusters:
            folder_total = sum(counts.values())
            breakdown = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            lines.append(f"  - {folder}  ({folder_total} findings: {breakdown})")
    else:
        lines.append("No dominant clusters detected — findings are spread across many folders.")

    # Remaining (non-cluster) folders, for agent context
    cluster_set = {f for f, _ in clusters}
    non_cluster_folders = [
        (folder, dict(counts))
        for folder, counts in by_folder.items()
        if folder not in cluster_set
    ]
    if non_cluster_folders:
        non_total = sum(sum(counts.values()) for _, counts in non_cluster_folders)
        lines.append(
            f"\nRemaining {non_total} findings across {len(non_cluster_folders)} other folder(s)."
        )

    print("\n".join(lines))
    return 0


# ──────────────────────────────────────────────────────────────────────────────
# --write
# ──────────────────────────────────────────────────────────────────────────────

_VALID_CHECKS = frozenset([
    "unparented", "orphan", "broken_up", "dead_link", "duplicate_stem", "stale_moc"
])


def _validate_target(target: object) -> dict:
    """Validate and return a normalised target dict. Raises ValueError on bad shape."""
    if not isinstance(target, dict):
        raise ValueError(f"target must be a dict, got {type(target).__name__}")
    t_type = target.get("type")
    t_value = target.get("value")
    if t_type not in ("path", "note", "tag"):
        raise ValueError(f"target.type must be path|note|tag, got {t_type!r}")
    if not t_value or not isinstance(t_value, str):
        raise ValueError("target.value must be a non-empty string")
    return {"type": t_type, "value": t_value}


def _validate_checks(checks: object) -> object:
    """Validate checks field. Returns 'all' or list of check names."""
    if checks == "all":
        return "all"
    if isinstance(checks, list):
        bad = [c for c in checks if c not in _VALID_CHECKS]
        if bad:
            raise ValueError(f"unknown check names: {bad!r}")
        if not checks:
            raise ValueError("checks list must not be empty")
        return checks
    raise ValueError(f"checks must be 'all' or a list of check names, got {checks!r}")


def write_config(choices_json: str, output_path: str) -> int:
    """Parse wizard choices JSON and write schema-valid exclusions YAML. Returns exit code."""
    try:
        choices = json.loads(choices_json)
    except json.JSONDecodeError as exc:
        print(f"[error] Failed to parse --choices JSON: {exc}", file=sys.stderr)
        return 1

    today_str = choices.get("today") or date.today().isoformat()
    raw_exclusions = choices.get("exclusions") or []

    if not isinstance(raw_exclusions, list):
        print("[error] choices.exclusions must be a list", file=sys.stderr)
        return 1

    exclusion_entries = []
    for idx, raw in enumerate(raw_exclusions):
        if not isinstance(raw, dict):
            print(f"[error] exclusion #{idx} is not a dict", file=sys.stderr)
            return 1
        try:
            target = _validate_target(raw.get("target"))
            checks = _validate_checks(raw.get("checks"))
            mode = raw.get("mode")
            if mode not in ("permanent", "temporary"):
                raise ValueError(f"mode must be permanent|temporary, got {mode!r}")
            reason = raw.get("reason") or ""
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError("reason must be a non-empty string")
        except ValueError as exc:
            print(f"[error] exclusion #{idx} invalid: {exc}", file=sys.stderr)
            return 1

        entry: dict = {
            "target": target,
            "checks": checks,
            "mode": mode,
            "reason": reason.strip(),
            "created": today_str,
        }
        if mode == "temporary":
            push_back_days = raw.get("push_back_days", 90)
            try:
                push_back_days = int(push_back_days)
            except (TypeError, ValueError):
                push_back_days = 90
            until_date = (
                date.fromisoformat(today_str) + timedelta(days=push_back_days)
            ).isoformat()
            entry["until"] = until_date
        exclusion_entries.append(entry)

    config: dict = {
        "version": 1,
        "configured": True,
        "exclusions": exclusion_entries,
    }

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    header_comment = (
        "# Skill-owned exclusion config for /garden-audit (spec 030, ADR-2).\n"
        "# Managed via /garden-audit --configure. Do not edit manually.\n"
    )
    try:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(header_comment)
            yaml.dump(
                config, fh,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
    except OSError as exc:
        print(f"[error] Failed to write {output_path}: {exc}", file=sys.stderr)
        return 1

    entry_count = len(exclusion_entries)
    noun = "entry" if entry_count == 1 else "entries"
    print(
        f"Exclusion config written: {output_path} ({entry_count} {noun}).",
        file=sys.stderr,
    )
    return 0


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(
        prog="garden-audit-configure.py",
        description=(
            "Wizard-support helper for garden-auditor.md. "
            "Use --summarize to emit a cluster summary, or --write to write the config."
        ),
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--summarize",
        action="store_true",
        help="Emit cluster summary from garden-audit-doc.json to stdout",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Write schema-valid garden-audit-exclusions.yaml from wizard choices JSON",
    )
    p.add_argument(
        "--input",
        help="(--summarize) Path to garden-audit-doc.json",
    )
    p.add_argument(
        "--choices",
        help="(--write) Wizard choices as a JSON string",
    )
    p.add_argument(
        "--output",
        help="(--write) Output path for the YAML config",
    )

    args = p.parse_args()

    if args.summarize:
        if not args.input:
            print("[error] --summarize requires --input", file=sys.stderr)
            return 2
        return summarize(args.input)

    # --write path
    if not args.choices:
        print("[error] --write requires --choices", file=sys.stderr)
        return 2
    if not args.output:
        print("[error] --write requires --output", file=sys.stderr)
        return 2
    return write_config(args.choices, args.output)


if __name__ == "__main__":
    sys.exit(main())
