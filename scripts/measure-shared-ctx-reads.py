#!/usr/bin/env python3
# version: 0.1.0
"""measure-shared-ctx-reads.py — how each /inbox analyst read of shared-ctx arrived.

Companion to measure-inbox-phase-b-token-cost.py (tokens per item). This one
answers a different question: did every `read-shared-ctx.py` call an
inbox-analyst subagent made reach the model whole, or was it spilled to a
file and replaced by a 2 KB preview? A spilled MOC list is the failure that
spec 040 (#173) removes, and its KPI "zero MOC reads delivered as a preview"
is measured with this script before and after.

How a spill is recognised: Claude Code records a spilled Bash result with
`toolUseResult.persistedOutputPath` and `persistedOutputSize` (the full size
in bytes), and the tool_result content starts with `<persisted-output>`.
For a delivered result the size is the UTF-8 length of its stdout.

Output never contains note content. The text report names subagent
transcript files only; `--json` adds each item's stem (a note filename) so
the result can be joined with item results — write it to a gitignored place
(spec 040 keeps baseline details in tomo-instance/spec-040-baseline/).

Usage:
  python3 scripts/measure-shared-ctx-reads.py --session-latest
  python3 scripts/measure-shared-ctx-reads.py --session-latest --run-id <run_id>
  python3 scripts/measure-shared-ctx-reads.py --session <session.jsonl> --json > <gitignored>/reads.json

Exit 0 on success, 1 when the session has no subagents/ directory, no
analyst transcripts, or none for the requested run_id.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shlex
import sys
from collections import Counter
from pathlib import Path

_SIBLING = Path(__file__).resolve().parent / "measure-inbox-phase-b-token-cost.py"
_spec = importlib.util.spec_from_file_location("measure_inbox_phase_b_token_cost", _SIBLING)
_phase_b = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_phase_b)

extract_metadata = _phase_b.extract_metadata
latest_session_jsonl = _phase_b.latest_session_jsonl
subagents_dir_for = _phase_b.subagents_dir_for

READER = "read-shared-ctx"
MODES = ("--field", "--fields", "--keys", "--moc-names", "--mocs-from")
SPILL_MARKER = "<persisted-output>"


def classify(command: str) -> tuple[str, str | None]:
    """Return (mode, target) for a read-shared-ctx command line."""
    try:
        argv = shlex.split(command)
    except ValueError:
        argv = command.split()
    for i, arg in enumerate(argv):
        if arg in MODES:
            takes_value = arg not in ("--keys", "--moc-names")
            target = argv[i + 1] if takes_value and i + 1 < len(argv) else None
            return arg, target
    return "unknown", None


def _result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


def reads_in(transcript: Path) -> list[dict]:
    """Every read-shared-ctx call in one subagent transcript, in order."""
    pending: dict[str, tuple[str, str | None]] = {}
    reads: list[dict] = []
    with transcript.open(encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            content = (rec.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "tool_use":
                    command = (c.get("input") or {}).get("command") or ""
                    if READER in command:
                        pending[c.get("id")] = classify(command)
                elif c.get("type") == "tool_result" and c.get("tool_use_id") in pending:
                    mode, target = pending.pop(c["tool_use_id"])
                    tur = rec.get("toolUseResult") if isinstance(rec.get("toolUseResult"), dict) else {}
                    text = _result_text(c.get("content"))
                    spilled = bool(tur.get("persistedOutputPath")) or text.startswith(SPILL_MARKER)
                    if spilled and isinstance(tur.get("persistedOutputSize"), int):
                        size = tur["persistedOutputSize"]
                    else:
                        size = len((tur.get("stdout") if "stdout" in tur else text).encode("utf-8"))
                    reads.append({"mode": mode, "target": target, "bytes": size, "spilled": spilled})
    return reads


def scan_session(session_jsonl: Path, run_id: str | None) -> dict:
    """Collect reads per analyst subagent for one run. Raises LookupError with a message."""
    sub_dir = subagents_dir_for(session_jsonl)
    if not sub_dir.is_dir():
        raise LookupError(f"No subagents/ directory found beside {session_jsonl}\n  expected: {sub_dir}")

    agents = []
    run_ids: Counter = Counter()
    for f in sorted(sub_dir.glob("agent-*.jsonl")):
        stem, rid, _model = extract_metadata(f)
        if stem is None or rid is None:
            continue
        run_ids[rid] += 1
        agents.append({"agent": f.name, "stem": stem, "run_id": rid, "path": f})
    if not agents:
        raise LookupError(f"No inbox-analyst subagent transcripts found in {sub_dir}")

    chosen = run_id or run_ids.most_common(1)[0][0]
    selected = [a for a in agents if a["run_id"] == chosen]
    if not selected:
        raise LookupError(f"No subagents matched run_id={chosen}\n  available run_ids: {dict(run_ids)}")

    out = []
    for a in selected:
        out.append({"agent": a["agent"], "stem": a["stem"], "reads": reads_in(a["path"])})
    all_reads = [r for a in out for r in a["reads"]]
    return {
        "session": session_jsonl.name,
        "run_id": chosen,
        "agents": out,
        "summary": {
            "agents": len(out),
            "reads": len(all_reads),
            "spilled": sum(1 for r in all_reads if r["spilled"]),
        },
    }


def print_text(report: dict) -> None:
    s = report["summary"]
    print(f"shared-ctx reads — run {report['run_id']}")
    print(f"Session: {report['session']}")
    print()
    print(f"  {'agent':<32}  {'mode':<12}  {'target':<40}  {'bytes':>8}  spilled")
    for a in report["agents"]:
        for r in a["reads"]:
            target = (r["target"] or "")[:40]
            print(f"  {a['agent']:<32}  {r['mode']:<12}  {target:<40}  {r['bytes']:>8,}  {'YES' if r['spilled'] else '-'}")
    print()
    print(f"agents={s['agents']} reads={s['reads']} spilled={s['spilled']}")


def main() -> int:
    p = argparse.ArgumentParser(description="How each /inbox analyst read of shared-ctx arrived (whole or spilled).")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--session", help="Path to a Claude Code session JSONL")
    src.add_argument("--session-latest", action="store_true", help="Most recent tomo-instance session JSONL")
    p.add_argument("--run-id", help="Filter to one Pass 1 run_id (default: most common)")
    p.add_argument("--json", action="store_true", help="Emit JSON including item stems (write it somewhere gitignored)")
    args = p.parse_args()

    if args.session:
        session = Path(args.session)
        if not session.is_file():
            print(f"Not a file: {session}", file=sys.stderr)
            return 1
    else:
        session = latest_session_jsonl()
        if not session:
            print("No session JSONL found under tomo-home/.claude/projects/", file=sys.stderr)
            return 1
        print(f"Using latest session: {session.name}", file=sys.stderr)

    try:
        report = scan_session(session, args.run_id)
    except LookupError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
