#!/usr/bin/env python3
# version: 0.2.0
"""analyze-placement-confidence.py — offline tuning aid for the spec-023
MOC-placement confidence gate.

Reads one or more Pass-1 `suggestions-doc.json` artifacts and reports the
distribution of tier-1 heading `fit_confidence` values, plus a flag list of
placements where a likely *structural* heading (Content / Structure / Link MOC /
Primer Questions / Processes) scored at or above the gate threshold.

WHY this exists (#71 / #64):
    Spec 023's gate is an LLM self-assessed `fit_confidence` compared to a
    hardcoded 0.6 threshold; the SDD deliberately rejected a code-level
    structural-heading blocklist (it does not generalize). But a live run
    (2026-06-17, "Asakusa Senso-ji") let the structural heading "Content" pass
    the gate — the exact anti-pattern 023 targets. #64 shipped per-placement
    telemetry at Pass-2, but that line is metadata-only (no heading text, per
    Constitution L2), so it cannot tell you *which* high-confidence placements
    were structural.

    The suggestions-doc.json (Pass-1, before wire-stripping) carries BOTH the
    heading text and the fit_confidence. This tool reads it OFFLINE to give the
    evidence needed to tune the 0.6 threshold.

    Since 2026-07 a deterministic runtime BACKSTOP (spec 023 ADR-6,
    suggestions-reducer.demote_structural_anchors) also demotes structural-heading
    tier-1 anchors to a new section, so a live run no longer lands notes under
    them. This tool still flags them for threshold-tuning evidence: it reads the
    raw analyst fit_confidence BEFORE the backstop's rewrite, so a persistent
    high-confidence flag here means the LLM keeps mis-scoring that heading — the
    signal for tuning the 0.6 gate. The shared list (DEFAULT_STRUCTURAL_HEADINGS)
    is imported from the runtime lib so the two can never drift.

This is a host-side developer/tuning tool (user-invoked), not part of the
runtime pipeline — it is not synced into a Tomo instance.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

# Single source of truth for the #71 structural-heading list — shared with the
# runtime demotion backstop in tomo/scripts/suggestions-reducer.py so this tuning
# aid and the runtime can never drift on which headings count as structural.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tomo" / "scripts"))
from lib.structural_headings import DEFAULT_STRUCTURAL_HEADINGS  # noqa: E402

# The spec-023 gate threshold (ADR-4). A structural heading at/above this scored
# high enough to be chosen as a tier-1 anchor — i.e. it slipped the gate.
DEFAULT_THRESHOLD = 0.6


class Placement:
    """One resolved Pass-1 placement anchor with its context."""

    __slots__ = ("doc", "stem", "moc_path", "heading", "fit_confidence")

    def __init__(self, doc, stem, moc_path, heading, fit_confidence):
        self.doc = doc
        self.stem = stem
        self.moc_path = moc_path
        self.heading = heading
        self.fit_confidence = fit_confidence


def _iter_heading_placements(doc: dict, doc_label: str):
    """Yield Placement for every tier-1 heading anchor carrying a numeric
    fit_confidence. Tolerant of missing/varying fields (fail-open walk)."""
    for section in doc.get("sections") or []:
        stem = section.get("stem", "?")
        for action in section.get("actions") or []:
            for cand in action.get("candidate_mocs") or []:
                anchor = cand.get("anchor") or {}
                if anchor.get("type") != "heading":
                    continue
                fit = anchor.get("fit_confidence")
                # Exclude bool explicitly: True/False are int subclasses.
                if not isinstance(fit, (int, float)) or isinstance(fit, bool):
                    continue
                yield Placement(
                    doc=doc_label,
                    stem=stem,
                    moc_path=cand.get("path", "?"),
                    heading=anchor.get("value") or "",
                    fit_confidence=round(float(fit), 2),
                )


def _count_tiers(doc: dict) -> tuple[int, int]:
    """Return (tier2_new_section, other) placement counts for context."""
    tier2 = 0
    other = 0
    for section in doc.get("sections") or []:
        for action in section.get("actions") or []:
            for cand in action.get("candidate_mocs") or []:
                anchor = cand.get("anchor") or {}
                if anchor.get("new_section"):
                    tier2 += 1
                elif anchor.get("type") != "heading":
                    other += 1
    return tier2, other


def _is_structural(heading: str, structural: set[str]) -> bool:
    return heading.strip().casefold() in structural


def _histogram(values: list[float]) -> list[tuple[str, int]]:
    """Bucket values into 0.1-wide bins from 0.0 to 1.0."""
    edges = [(round(i / 10, 1), round((i + 1) / 10, 1)) for i in range(10)]
    out = []
    for lo, hi in edges:
        # Top bin is inclusive of 1.0; others are half-open [lo, hi).
        n = sum(1 for v in values if (lo <= v < hi) or (hi == 1.0 and v == 1.0))
        out.append((f"[{lo:.1f},{hi:.1f})", n))
    return out


def analyze(paths: list[Path], structural: set[str], threshold: float) -> dict:
    """Load docs and return a structured report."""
    placements: list[Placement] = []
    tier2_total = 0
    other_total = 0
    loaded = 0
    for p in paths:
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  [warn] skipping {p}: {exc}", file=sys.stderr)
            continue
        loaded += 1
        label = p.name
        placements.extend(_iter_heading_placements(doc, label))
        t2, other = _count_tiers(doc)
        tier2_total += t2
        other_total += other

    values = [pl.fit_confidence for pl in placements]
    flagged = sorted(
        (pl for pl in placements
         if _is_structural(pl.heading, structural) and pl.fit_confidence >= threshold),
        key=lambda pl: pl.fit_confidence,
    )
    return {
        "docs_loaded": loaded,
        "tier1_heading": len(placements),
        "tier2_new_section": tier2_total,
        "other": other_total,
        "values": values,
        "flagged": flagged,
        "threshold": threshold,
    }


def render_report(report: dict) -> str:
    lines: list[str] = []
    lines.append("Placement fit_confidence analysis")
    lines.append(
        f"  docs analyzed: {report['docs_loaded']}   "
        f"tier-1 heading: {report['tier1_heading']}   "
        f"tier-2 new-section: {report['tier2_new_section']}   "
        f"other: {report['other']}"
    )
    lines.append("")

    values = report["values"]
    if values:
        lines.append("Distribution (tier-1 heading fit_confidence):")
        lines.append(
            f"  count={len(values)}  min={min(values):.2f}  "
            f"median={statistics.median(values):.2f}  max={max(values):.2f}"
        )
        for label, n in _histogram(values):
            # Bar width is the raw count — simple and deterministic.
            lines.append(f"  {label} {'█' * n} {n}" if n else f"  {label} · 0")
    else:
        lines.append("Distribution: no tier-1 heading placements found.")
    lines.append("")

    flagged = report["flagged"]
    thr = report["threshold"]
    if flagged:
        lines.append(
            f"⚠ Structural-heading placements at/above threshold {thr:.2f} "
            f"(gate slips — tune candidates, #71):"
        )
        for pl in flagged:
            lines.append(
                f"  {pl.fit_confidence:.2f}  {pl.heading!r:<22} "
                f"MOC: {pl.moc_path}   note: {pl.stem}   [{pl.doc}]"
            )
    else:
        lines.append(
            f"✓ No structural-heading placements at/above threshold {thr:.2f}."
        )
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Analyze spec-023 MOC-placement fit_confidence from "
        "suggestions-doc.json artifacts (tuning aid for #71).",
    )
    p.add_argument(
        "docs", nargs="+", type=Path,
        help="One or more suggestions-doc.json files.",
    )
    p.add_argument(
        "--threshold", type=float, default=DEFAULT_THRESHOLD,
        help=f"Gate threshold to flag against (default {DEFAULT_THRESHOLD}).",
    )
    p.add_argument(
        "--structural-heading", action="append", default=[], metavar="HEADING",
        help="Add a heading to the structural set (repeatable). Extends the "
        "built-in list (Content, Structure, Link MOC, ...).",
    )
    p.add_argument(
        "--json", action="store_true",
        help="Emit the report as JSON instead of the text summary.",
    )
    args = p.parse_args()

    structural = {
        h.strip().casefold()
        for h in DEFAULT_STRUCTURAL_HEADINGS + args.structural_heading
    }
    report = analyze(args.docs, structural, args.threshold)

    if args.json:
        out = {
            "docs_loaded": report["docs_loaded"],
            "tier1_heading": report["tier1_heading"],
            "tier2_new_section": report["tier2_new_section"],
            "other": report["other"],
            "threshold": report["threshold"],
            "values": report["values"],
            "flagged": [
                {
                    "fit_confidence": pl.fit_confidence,
                    "heading": pl.heading,
                    "moc_path": pl.moc_path,
                    "stem": pl.stem,
                    "doc": pl.doc,
                }
                for pl in report["flagged"]
            ],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(render_report(report))

    # Exit 1 when structural gate-slips are present, so the tool can gate a
    # tuning-review step in a script/CI without parsing stdout.
    return 1 if report["flagged"] else 0


if __name__ == "__main__":
    sys.exit(main())
