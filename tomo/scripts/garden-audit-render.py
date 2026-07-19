#!/usr/bin/env python3
# version: 0.1.0
"""Render garden-audit-doc.json to a severity-ordered markdown report + wire JSON.

Deterministic renderer — no LLM. The garden-auditor agent runs this after the scan
and writes both artifacts to the vault inbox via kado-write-file.py.

Input:  garden-audit-doc.json (from garden-audit.py)
Output: Report .md (severity-ordered, caveats, fixable checkboxes, advisory read-only)
        garden-audit-wire.json (complete mirror, emit_digest, ADR-4 / ADR-026)

ADR-4: both artifacts are projected from the same doc dict — no drift by construction.
emit_digest is the SHA-256 change signal for Pass-2 (garden-audit-parser.py).
Stamped: tomo.doc_type=garden-audit, tomo.state=pending-accept, tomo_skip_inbox_analysis: true.

Section order (strict):
  1. Frontmatter (YAML, tomo block)
  2. Title + caveats (index-lag, ACL scope)
  3. Preamble: skipped checks + reappeared exclusions (when non-empty)
  4. Summary (tier counts, zero-findings → "vault healthy")
  5. Integrity findings (broken_up, dead_link) — omitted when empty
  6. Structure findings (unparented, orphan) — omitted when empty
  7. Advisory findings (duplicate_stem, stale_moc) — omitted when empty
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

from lib.doc_frontmatter import build_tomo_block
from lib.render_md import compute_payload_digest

# ── Tier ordering ────────────────────────────────────────────────────────────
_TIER_ORDER = {"integrity": 0, "structure": 1, "advisory": 2}
_TIER_LABEL = {
    "integrity": "Integrity",
    "structure": "Structure",
    "advisory": "Advisory",
}

# ── Check-level display labels ────────────────────────────────────────────────
_CHECK_LABEL = {
    "broken_up": "Broken up:: link",
    "dead_link": "Dead link",
    "unparented": "Unparented note",
    "orphan": "Orphan note",
    "duplicate_stem": "Duplicate stem",
    "stale_moc": "Stale MOC",
}


# ── Frontmatter ───────────────────────────────────────────────────────────────

def render_frontmatter(d: dict) -> list[str]:
    """Emit the YAML frontmatter stamped per ADR-1 + ADR-4.

    tomo.doc_type=garden-audit, tomo.state=pending-accept, tomo_skip_inbox_analysis: true.
    """
    tomo_block = build_tomo_block(
        doc_type="garden-audit",
        state="pending-accept",
        run_id=d["run_id"],
    )
    fm: dict = {
        "generated": d["generated"],
        "profile": d["profile"],
        "run_id": d["run_id"],
        "tomo_skip_inbox_analysis": True,
        "tomo": tomo_block,
    }
    body = yaml.dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return ["---"] + body.rstrip("\n").splitlines() + ["---"]


# ── Report body ───────────────────────────────────────────────────────────────

def _render_caveats() -> list[str]:
    """Index-lag and ACL-scope caveats — present in every report (PRD Feature 4)."""
    return [
        "> **Index lag:** This report is a snapshot. The discovery cache may lag behind"
        " very recent vault edits — a note can appear as orphaned after a bulk operation.",
        "> **ACL scope:** Findings reflect only the notes accessible via Kado's current"
        " permission config. ACL-gated notes are invisible; absent findings do not mean"
        " the vault is clean beyond the ACL boundary.",
        "",
    ]


def _render_preamble(d: dict) -> list[str]:
    """Skipped checks and reappeared (expired-temporary) exclusions in the preamble."""
    lines: list[str] = []

    skipped = d.get("skipped_checks") or []
    if skipped:
        reason = d.get("skipped_checks_reason") or "external tool unavailable"
        names = ", ".join(skipped)
        lines += [
            f"> **Checks not run:** {names} — {reason}",
            "",
        ]

    reappeared = d.get("reappeared_exclusions") or []
    if reappeared:
        lines += [
            "**Reappeared exclusions** — the following temporary exclusions have expired"
            " and their findings now appear again:",
            "",
        ]
        for excl in reappeared:
            target = excl.get("target", {})
            ttype = target.get("type", "")
            tvalue = target.get("value", "")
            until = excl.get("until", "?")
            lines.append(f"- `{ttype}: {tvalue}` (expired {until})")
        lines.append("")

    return lines


def _render_summary(findings: list[dict]) -> list[str]:
    """Summary block with per-tier counts; zero findings → positive message."""
    lines = ["## Summary", ""]

    if not findings:
        lines += [
            "Vault healthy — no findings produced by this scan.",
            "",
        ]
        return lines

    counts: dict[str, int] = {"integrity": 0, "structure": 0, "advisory": 0}
    for f in findings:
        counts[f["tier"]] = counts.get(f["tier"], 0) + 1

    total = sum(counts.values())
    lines.append(f"Total findings: {total}")
    lines.append("")
    for tier in ("integrity", "structure", "advisory"):
        n = counts.get(tier, 0)
        if n:
            lines.append(f"- {_TIER_LABEL[tier]}: {n}")
    lines.append("")
    return lines


def _render_finding(f: dict) -> list[str]:
    """Render one finding as a report block.

    Fixable findings get a pre-selected (or deselected) checkbox.
    Advisory findings are read-only — no checkbox.
    """
    fid = f["id"]
    check = f["check"]
    label = _CHECK_LABEL.get(check, check)
    target = f["target"]
    path = target.get("path", "")
    stem = target.get("stem") or Path(path).stem
    detail = f.get("detail", {})

    lines = [f"### {fid} — {label}: `{stem}`", ""]

    # Detail lines per check type
    if check == "unparented":
        mocs = detail.get("candidate_mocs") or []
        if mocs:
            lines.append(f"Candidate MOC: `{mocs[0]['target_moc']}` (score: {mocs[0]['score']:.2f})")
    elif check == "orphan":
        mocs = detail.get("candidate_mocs") or []
        if mocs:
            lines.append(f"Candidate MOC: `{mocs[0]['target_moc']}` (score: {mocs[0]['score']:.2f})")
    elif check == "broken_up":
        up_target = detail.get("up_target")
        if up_target:
            lines.append(f"Broken `up::` → `{up_target}`")
    elif check == "dead_link":
        dead_target = detail.get("dead_target", "")
        count = detail.get("count", 1)
        lines.append(f"Dead link: `{dead_target}` ({count}× in `{path}`)")
    elif check == "duplicate_stem":
        dupes = detail.get("dupes") or []
        lines.append(f"Paths sharing stem `{stem}`:")
        for dup in dupes:
            lines.append(f"  - `{dup}`")
    elif check == "stale_moc":
        mtime = detail.get("mtime", "unknown")
        lines.append(f"Last modified: {mtime}")

    lines.append("")

    # Fixable → checkbox (pre-selected from decision.selected)
    decision = f.get("decision")
    if decision is not None:
        action = decision.get("action") or "fix"
        selected = decision.get("selected", True)
        check_mark = "x" if selected else " "
        lines += [
            "**Fix:**",
            f"- [{check_mark}] Apply `{action}` — tick to confirm, untick to skip",
            "",
        ]
    # Advisory → no checkbox, just a note
    elif f.get("tier") == "advisory":
        lines += [
            "_Advisory — no automated fix. Review and handle manually._",
            "",
        ]

    return lines


def _render_tier_section(tier: str, findings: list[dict]) -> list[str]:
    """Render one tier section (e.g. ## Integrity). Returns [] when no findings."""
    tier_findings = [f for f in findings if f["tier"] == tier]
    if not tier_findings:
        return []
    lines = [f"## {_TIER_LABEL[tier]}", ""]
    for f in tier_findings:
        lines.extend(_render_finding(f))
    return lines


def render_report(d: dict) -> str:
    """Render the full markdown report body (without frontmatter) as a string."""
    findings = d.get("findings") or []
    date = d["generated"][:10]

    parts: list[str] = []
    parts += ["", f"# Knowledge-Garden Audit — {date}", ""]
    parts += _render_caveats()
    parts += _render_preamble(d)
    parts += _render_summary(findings)
    for tier in ("integrity", "structure", "advisory"):
        parts += _render_tier_section(tier, findings)

    return "\n".join(parts)


# ── Wire (ADR-4 / ADR-026) ───────────────────────────────────────────────────

def build_wire_payload(d: dict) -> dict:
    """Project garden-audit-doc.json to the full-mirror wire + emit_digest.

    ADR-4: the wire is a complete, structured serialization of the review surface.
    Both the report and the wire are projected from the same doc dict — no drift.
    emit_digest is computed over the payload with emit_digest absent (ADR-026 pattern).
    """
    findings = d.get("findings") or []

    # Severity-sort the wire findings (integrity → structure → advisory) so the
    # wire order is guaranteed regardless of how the caller ordered the doc.
    sorted_findings = sorted(findings, key=lambda f: _TIER_ORDER.get(f.get("tier", ""), 99))

    wire_findings = []
    for f in sorted_findings:
        wf: dict = {
            "id": f["id"],
            "check": f["check"],
            "tier": f["tier"],
            "fixable": f["fixable"],
            "target": {
                "path": f["target"]["path"],
                "stem": f["target"].get("stem"),
            },
            "detail": f.get("detail", {}),
        }
        # decision block present ONLY on fixable findings
        decision = f.get("decision")
        if decision is not None:
            wf["decision"] = {
                "selected": decision.get("selected", True),
                "action": decision.get("action"),
            }
        wire_findings.append(wf)

    payload: dict = {
        "schema_version": "1",
        "generated": d["generated"],
        "run_id": d["run_id"],
        "profile": d.get("profile"),
        "findings": wire_findings,
    }
    payload["emit_digest"] = compute_payload_digest(payload)
    return payload


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(
        description="Render garden-audit-doc.json to markdown report + wire JSON."
    )
    p.add_argument("--input", required=True, help="Path to garden-audit-doc.json")
    p.add_argument("--output", required=True, help="Output markdown file path")
    p.add_argument("--json-output", help="Optional path for garden-audit-wire.json (ADR-4)")
    args = p.parse_args()

    with open(args.input, encoding="utf-8") as f:
        d = json.load(f)

    fm_lines = render_frontmatter(d)
    report_body = render_report(d)
    content = "\n".join(fm_lines) + "\n" + report_body

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(content)

    if args.json_output:
        wire = build_wire_payload(d)
        with open(args.json_output, "w", encoding="utf-8") as f:
            json.dump(wire, f, ensure_ascii=False, indent=2)

    finding_count = len(d.get("findings") or [])
    print(
        f"garden-audit-render: findings={finding_count} out={args.output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
