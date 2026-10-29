# version: 0.1.0
"""moc_discovery_uplinks.py — `--check-moc-uplinks` audit of moc-discovery.

A focused MOC-parentage pass: the orphan link-or-create suggestions over
`kind == "moc"` entries, capped for display, with no clustering pipeline.
`moc-discovery.py` re-exports every name.

Rationale: docs/tomo/scripts/lib/moc_discovery_uplinks.md (issue #216).
"""
from __future__ import annotations

from pathlib import Path

from lib.moc_discovery_common import _load_moc_config, _log
from lib.moc_discovery_report import empty_report
from lib.orphan_link import emit_orphan_suggestions


def _cap_orphans(
    suggestions: list[dict], cap: int
) -> tuple[list[dict], int, int]:
    """Truncate a (pre-ordered) orphan-suggestion list to `cap` (ADR-12).

    `suggestions` arrives link-first ordered from emit_orphan_suggestions, so the
    head is the most-actionable. Returns (kept, total, overflow). A cap < 0 (or
    a total at/under the cap) keeps everything with overflow 0.
    """
    total = len(suggestions)
    if cap is not None and cap >= 0 and total > cap:
        return suggestions[:cap], total, total - cap
    return suggestions, total, 0


def _run_moc_uplink_check(
    cache: dict, config_path: Path, profile_name: str
) -> dict:
    """Focused MOC-parentage audit (ADR-12 / `--check-moc-uplinks`).

    Runs ONLY the orphan link-or-create pass over `kind=="moc"` entries — no
    clustering pipeline — and returns a `check-moc-uplinks` DiscoveryReport with
    the (capped) MOC orphan suggestions.
    """
    moc_config = _load_moc_config(config_path)
    orphan_all = emit_orphan_suggestions(cache.get("entries") or [], kinds=("moc",))
    kept, total, overflow = _cap_orphans(orphan_all, moc_config.orphan_display_cap)
    _log(f"check-moc-uplinks: {total} orphan MOC(s) → {len(kept)} shown (overflow {overflow})")
    report = empty_report("check-moc-uplinks", "", profile_name)
    report["orphan_suggestions"] = kept
    report["orphan_total"] = total
    report["orphan_overflow"] = overflow
    return report
