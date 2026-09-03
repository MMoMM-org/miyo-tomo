#!/usr/bin/env python3
# version: 0.18.3
"""Render garden-audit-doc.json to a severity-ordered markdown report + wire JSON.

Deterministic renderer — no LLM. The garden-auditor agent runs this after the scan
and writes both artifacts to the vault inbox via kado-write-file.py.

Input:  garden-audit-doc.json (from garden-audit.py)
Output: Report .md (human-facing DECISIONS only — Apply ticks + Repoint/Replace
                    fields; joined to the wire by the F-id in each ### F<id> heading)
        garden-audit-wire.json (complete STRUCTURE mirror + emit_digest, ADR-4)

Two-artifact split (spec 030): the markdown is purely human-facing (no HTML
comment); ALL machine structure (path, detail, candidate_mocs, decision defaults)
lives in the wire, which garden-audit-parser ALWAYS reads for structure and joins
to the markdown decisions by F-id.

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
import re
import sys
from pathlib import Path

import yaml

from lib.doc_frontmatter import build_tomo_block
from lib.profile_conventions import marker_word, resolve_conventions
from lib.render_md import compute_garden_audit_digest, unwrap_list_repr
from lib.target_suggest import (
    suggest_dead_link_targets,
    suggest_file_under_mocs,
    suggest_repoint_mocs,
)

# Instance-relative profiles dir (ADR-2, profile_conventions.py): the script
# supplies profiles_dir, the lib never derives it from its own __file__.
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PROFILES_DIR = SCRIPT_DIR.parent / "profiles"

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
    "parent_not_moc": "Parent not a MOC",
}


# ── Unroutable broken_up findings (spec 032 T5.2) ──────────────────────────────
# Sentinel mirroring garden-audit-parser.py's ADR-3 _MISSING — detail.up_value
# may legitimately be None (a property that exists and holds nothing), so only
# identity-checking against a sentinel distinguishes that from a cache that
# never wrote the key at all (a pre-032 cache, CON-1).
_MISSING = object()

_UNROUTABLE_REMEDY = {
    # Verbatim (solution.md, User Interface & UX) — DO NOT PARAPHRASE.
    "stale-cache": [
        "- **Not fixable this run:** the discovery cache predates property routing.",
        "  Run `/explore-vault` to refresh it, then re-run the audit.",
    ],
    # Not spec-locked: the PRD/SDD only give verbatim wording for stale-cache.
    # no-declaration-site is documented in garden-audit-parser.py as
    # "unreachable in practice" (a broken state requires a target, and a
    # target requires a declared source) with no specified user-facing text.
    # Reuses the /explore-vault remedy — a cache refresh is the only recovery
    # lever this system offers — but this wording is proposed, not verbatim.
    "no-declaration-site": [
        "- **Not fixable this run:** this note's broken `up::` has no recorded"
        " declaration site.",
        "  Run `/explore-vault` to refresh the cache, then re-run the audit.",
    ],
    # Not spec-locked: neither the PRD nor the SDD give verbatim wording for
    # unsupported-shape (spec 032 T3.2). Proposed wording, following T5.2's
    # no-declaration-site precedent — it deliberately does NOT point at
    # /explore-vault, unlike the other two reasons: the cache here is healthy
    # and current, so a refresh changes nothing (SDD Complex Logic).
    # {prop} is substituted with the derived property name (ADR-6) at render
    # time — never hardcoded to "up". "up::" is the inline-marker spelling;
    # this reason only ever arises for a frontmatter-sourced finding (a
    # map-shaped value comes from parsed YAML), so the property name is the
    # correct noun here, not the inline marker.
    "unsupported-shape": [
        "- **Not fixable this run:** this note's `{prop}` property has a value"
        " shape (a map) this fix does not yet support.",
        "  This is not a stale cache — refreshing it will not change the"
        " outcome. Edit the property by hand instead.",
    ],
}


def _broken_up_withhold_reason(f: dict) -> str | None:
    """Reason a broken_up finding cannot be routed to a fix this run, or None
    when it is routable.

    Mirrors garden-audit-parser.py's ``_route_broken_up`` reason logic
    (ADR-3/ADR-5) so the report agrees with Pass-2 about what is (un)routable
    — without needing the user's remove/repoint choice, since routability
    doesn't depend on it. Only meaningful for a fixable broken_up finding
    (decision present); a malformed finding with no decision block at all
    still falls through to the ValueError guard in ``_render_finding``.
    """
    if f.get("check") != "broken_up" or f.get("decision") is None:
        return None
    detail = f.get("detail") or {}
    up_source = detail.get("up_source")
    up_value = detail.get("up_value", _MISSING)
    if up_value is _MISSING:
        return "stale-cache"
    if isinstance(up_value, dict):
        # spec 032 T3.2: a map-shaped up_value has no defined transform — the
        # cache is healthy (not stale-cache), so it gets its own reason.
        # Mirrors garden-audit-parser._route_broken_up's shape check.
        return "unsupported-shape"
    if up_source in ("frontmatter", "inline"):
        return None
    return "no-declaration-site"


def _render_withheld_block(reason: str, up_property: str) -> list[str]:
    """The reason + remedy for one withheld finding — no Apply checkbox and no
    Suggest opt-in, because there is nothing to approve or suggest a target
    for until the cache is refreshed (PRD AC-F6.1/F6.2).

    ``up_property`` fills the "unsupported-shape" template's ``{prop}`` slot
    (ADR-6, derived — never hardcoded); the other two reasons have no
    placeholder, so .format is a no-op for them.
    """
    return [ln.format(prop=up_property) for ln in _UNROUTABLE_REMEDY[reason]] + [""]


# ── Note-reference rendering ──────────────────────────────────────────────────

def _wikilink(ref) -> str:
    """Render a note reference as a clickable Obsidian wikilink `[[Stem]]`.

    Accepts a str or a list of stems (cache `up::` is a multi-value list).
    Strips any pre-existing `[[ ]]`, `.md`, and path prefix so the result is a
    bare, hover-able stem. Multiple targets render as `[[a]], [[b]]`.
    Empty / None → `(none)` so nothing renders as a raw `[]` or `None`.
    """
    # DEFENSIVE: a dirty cache may store a list as its str repr ("['020 …']").
    # Unwrap to the real list before formatting so it renders [[020 …]], not
    # [[['020 …']]]. Bare stems / [[wikilinks]] pass through unchanged.
    ref = unwrap_list_repr(ref)
    if ref is None or ref == "" or ref == []:
        return "(none)"
    if isinstance(ref, (list, tuple)):
        return ", ".join(_wikilink(r) for r in ref) if ref else "(none)"
    stem = str(ref).strip()
    if stem.startswith("[[") and stem.endswith("]]"):
        stem = stem[2:-2].strip()
    stem = stem.split("/")[-1]  # drop any folder path
    if stem.endswith(".md"):
        stem = stem[:-3]
    # An aliased link [[target|alias]] — keep the human-facing alias.
    if "|" in stem:
        stem = stem.split("|", 1)[1].strip()
    return f"[[{stem}]]"


def _fix_summary(check: str, detail: dict, decision: dict, up_property: str) -> str:
    """One plain-language line describing what applying the fix will DO to the note.

    The report must let the user decide without reading the wire — spell out the
    concrete before→after change, not just "Apply fix".

    ``up_property`` (ADR-6, derived — never hardcoded) names the fix action for
    a property-resident broken_up finding: it is fixed via a YAML-property
    edit, not a body-text edit, so the summary must say "property", not
    "up::" / "the broken line" — those describe the body-resident action.
    """
    if check in ("unparented", "orphan"):
        mocs = detail.get("candidate_mocs") or []
        if mocs:
            moc = _wikilink(mocs[0]["target_moc"])
            return f"Add `up:: {moc}` — files this note under {moc}."
        return (
            "No candidate MOC found — tick **Suggest targets** and run "
            "`/garden-audit suggest`, or set one in **File under:** below."
        )
    if check == "broken_up":
        up = _wikilink(detail.get("up_target"))
        if detail.get("up_source") == "frontmatter":
            return (
                f"The broken `{up_property}` property (was {up}) — repoint it to "
                "a MOC you enter below, or leave empty to remove the property value."
            )
        return (
            f"The broken `up::` (was {up}) — repoint it to a MOC you enter below, "
            "or leave empty to remove the broken line."
        )
    if check == "dead_link":
        dead = _wikilink(detail.get("dead_target"))
        replace = (decision or {}).get("replace", "")
        if replace:
            return f"Replace every {dead} with {_wikilink(replace)} in the note body."
        return (
            f"Unlink every {dead} (removes the [[ ]] brackets, keeps the text); "
            "fill **Replace with:** to repoint to a different note instead."
        )
    return "Apply the automated fix."


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
        counts[f["tier"]] += 1

    total = sum(counts.values())
    fixable_count = sum(1 for f in findings if f.get("fixable"))

    lines.append(f"Total findings: {total}")
    lines.append("")
    for tier in ("integrity", "structure", "advisory"):
        n = counts.get(tier, 0)
        if n:
            lines.append(f"- {_TIER_LABEL[tier]}: {n}")
    lines.append("")

    # All-advisory run: no fixable findings — user must handle manually (PRD Feature 2).
    if fixable_count == 0:
        lines += [
            "No fixable findings — all findings are advisory; review the sections"
            " below and handle manually.",
            "",
        ]

    return lines


_UNROUTABLE_REASON_LABEL = {
    "stale-cache": "stale cache",
    "no-declaration-site": "no declaration site",
    "unsupported-shape": "unsupported value shape",
}
_UNROUTABLE_SUMMARY_TEXT = {
    "stale-cache": (
        "the discovery cache predates property routing. Run `/explore-vault` "
        "to refresh it, then re-run the audit"
    ),
    "no-declaration-site": (
        "no recorded declaration site for the broken `up::`. Run "
        "`/explore-vault` to refresh the cache, then re-run the audit"
    ),
    # {prop} substituted with the derived property name (ADR-6) at render
    # time — never hardcoded to "up" — mirrors _UNROUTABLE_REMEDY's
    # unsupported-shape template above. This reason only ever arises for a
    # frontmatter-sourced finding, so "property" is the correct noun here,
    # not the inline-marker "up::" spelling.
    "unsupported-shape": (
        "a map-shaped `{prop}` property value this fix does not yet support "
        "— not a stale cache, edit the property by hand"
    ),
}


def _render_unroutable_summary(findings: list[dict], up_property: str) -> list[str]:
    """Once-per-run summary of withheld findings (PRD Should-have: unroutable
    summary; ADR-4-adjacent observability). In addition to the per-finding
    reason + remedy blocks, not a replacement for them (SDD render shape) —
    the measured first-run reality is that EVERY broken_up finding can be
    withheld at once, and the reader must not have to infer the collective
    remedy from N identical blocks.

    ``up_property`` fills the "unsupported-shape" template's ``{prop}`` slot
    (ADR-6, derived — never hardcoded), the same substitution
    _render_withheld_block applies to the per-finding remedy for the same
    reason; the other two reasons have no placeholder, so .format is a no-op
    for them.
    """
    counts: dict[str, int] = {}
    for f in findings:
        reason = _broken_up_withhold_reason(f)
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
    if not counts:
        return []

    total = sum(counts.values())
    noun = "finding" if total == 1 else "findings"
    lines = [f"**{total} {noun} withheld this run — not fixable:**", ""]
    for reason in ("stale-cache", "no-declaration-site", "unsupported-shape"):
        n = counts.get(reason, 0)
        if n:
            label = _UNROUTABLE_REASON_LABEL[reason]
            text = _UNROUTABLE_SUMMARY_TEXT[reason].format(prop=up_property)
            lines.append(f"- {n} {label} — {text}.")
    lines.append("")
    return lines


# ── Routing-split line (spec 032 T5.3, ADR-4) ───────────────────────────────
def _broken_up_site(f: dict) -> str | None:
    """Where a broken_up finding's up:: is declared — "body" or "property" —
    or None when the site can't be attributed: a stale cache predating
    ADR-1's raw_value capture (up_source absent), or the "unreachable in
    practice" no-declaration-site branch (up_source present but not one of
    the two known values).

    Deliberately reads detail.up_source directly rather than routing through
    _broken_up_withhold_reason: a T3.2 unsupported-shape finding (map-shaped
    up_value) is withheld, but ADR-1 still populated its up_source at
    cache-build time, so its declaration site IS known. ADR-4's population
    visibility is about where the parent is declared, not about fixability —
    those are separate questions, answered by separate report lines.
    """
    if f.get("check") != "broken_up":
        return None
    up_source = (f.get("detail") or {}).get("up_source")
    if up_source == "frontmatter":
        return "property"
    if up_source == "inline":
        return "body"
    return None


def _render_broken_up_split(findings: list[dict]) -> list[str]:
    """Once-per-run routing-split line (ADR-4, verbatim per solution.md UI &
    UX): "Broken parents: N findings — B in the note body, P in a note
    property."

    N is deliberately B + P, not the raw broken_up finding count. A finding
    whose site can't be attributed (see _broken_up_site) is excluded here
    rather than folded into N — a mismatched "29 findings — 0 in the note
    body, 0 in a note property" would be true, useless, and alarming. Those
    findings are already named by _render_unroutable_summary; this line just
    doesn't double-count them. Suppressed entirely when B + P == 0, which
    covers both "no broken_up findings this run" and the measured first-run
    reality where every broken_up finding is stale-cache and unattributable.
    """
    body = sum(1 for f in findings if _broken_up_site(f) == "body")
    prop = sum(1 for f in findings if _broken_up_site(f) == "property")
    total = body + prop
    if total == 0:
        return []
    return [
        f"Broken parents: {total} findings — {body} in the note body, "
        f"{prop} in a note property.",
        "",
    ]


def _render_property_edit_disclosure(up_property: str) -> list[str]:
    """The property-edit disclosure (spec 032 T5.1) — verbatim per solution.md
    UI & UX, `up_property` derived (ADR-6), never hardcoded to "up".

    Rendered at approval time (before the Apply checkbox): a successful
    edit_frontmatter fix drops YAML comments in the note's property block
    irreversibly, so the cost must be visible before the user ticks Apply,
    not after — a post-hoc note is too late by construction.
    """
    return [
        f"- **Fix target:** note property `{up_property}` — editing YAML properties.",
        "  ⚠️ Comments inside this note's property block will not survive the edit.",
    ]


def _render_finding(f: dict, up_property: str) -> list[str]:
    """Render one finding as a human-facing report block.

    The report carries the user's DECISIONS only, joined to the machine wire by
    the F-id in the ``### F<id>`` heading (spec 030 two-artifact split). Fixable
    findings get a pre-selected (or deselected) Apply checkbox and — where a
    target is editable — a Replace with: / Repoint to: field. Advisory findings
    are read-only. All STRUCTURE (path, detail, candidate_mocs) lives in the wire,
    not in the markdown — there is no HTML comment.
    """
    fid = f["id"]
    check = f["check"]
    label = _CHECK_LABEL.get(check, check)
    target = f["target"]
    path = target.get("path", "")
    stem = target.get("stem") or Path(path).stem
    detail = f.get("detail", {})

    # Integrity checks (broken_up, dead_link) live INSIDE the note — say "in:" so
    # the note reads as the container, not the broken link itself. Structure +
    # advisory checks: the note IS the subject — a plain colon (Change 1).
    joiner = " in" if f.get("tier") == "integrity" else ""
    lines = [f"### {fid} — {label}{joiner}: {_wikilink(stem)}", ""]

    # Detail lines per check type
    if check in ("unparented", "orphan"):
        mocs = detail.get("candidate_mocs") or []
        if mocs:
            lines.append(f"Candidate MOC: {_wikilink(mocs[0]['target_moc'])} (score: {mocs[0]['score']:.2f})")
    elif check == "broken_up":
        up_target = detail.get("up_target")
        if up_target:
            # Same site branch as _fix_summary: a frontmatter-declared parent has
            # no `up::` line to name, and saying so contradicts the property
            # language the same block carries two lines below.
            if detail.get("up_source") == "frontmatter":
                lines.append(
                    f"Broken `{up_property}` property → {_wikilink(up_target)}"
                )
            else:
                lines.append(f"Broken `up::` → {_wikilink(up_target)}")
    elif check == "dead_link":
        dead_target = detail.get("dead_target", "")
        count = detail.get("count", 1)
        lines.append(f"Dead link: {_wikilink(dead_target)} ({count}× in {_wikilink(stem)})")
    elif check == "duplicate_stem":
        dupes = detail.get("dupes") or []
        lines.append(f"Notes sharing stem {_wikilink(stem)}:")
        for dup in dupes:
            lines.append(f"  - `{dup}`")  # full path kept raw — disambiguates the collision
    elif check == "stale_moc":
        mtime = detail.get("mtime", "unknown")
        lines.append(f"Last modified: {mtime}")

    lines.append("")

    # Fixable → checkbox (opt-in: decision.selected defaults False since 0.11.0)
    decision = f.get("decision")
    # Unroutable broken_up (spec 032 T5.2): checked BEFORE the decision branch
    # so a withheld finding never reaches the Apply/Suggest affordances below —
    # there is nothing to approve. A malformed finding with no decision block
    # at all is unaffected (_broken_up_withhold_reason returns None when
    # decision is None) and still falls through to the ValueError guard.
    withhold_reason = _broken_up_withhold_reason(f)
    if withhold_reason is not None:
        lines += _render_withheld_block(withhold_reason, up_property)
    elif decision is not None:
        selected = decision.get("selected", False)
        check_mark = "x" if selected else " "
        lines.append("**Fix:** " + _fix_summary(check, detail, decision, up_property))
        # Property-edit disclosure (spec 032 T5.1): only for a broken_up finding
        # whose up:: lives in frontmatter — an edit_frontmatter fix drops YAML
        # comments in that property block, and the cost must be visible BEFORE
        # Apply is ticked. Body-resident (inline/absent up_source) findings are
        # unaffected — CON-7 byte-identical rendering.
        if check == "broken_up" and detail.get("up_source") == "frontmatter":
            lines += _render_property_edit_disclosure(up_property)
        lines.append(f"- [{check_mark}] Apply — tick to apply this fix")
        # Editable target field — the parser reads it back to decide the fix.
        if check == "dead_link":
            lines.append(
                "- **Replace with:** [[]]    ← fill a target to repoint, "
                "or leave empty to unlink (keeps the text, drops the [[ ]])"
            )
        elif check == "broken_up":
            # Every broken_up offers repoint OR remove — the user chooses by
            # filling (repoint) or leaving empty (remove). The parser reads this
            # field for all broken_up findings, not just pre-marked repoints.
            # Property-resident (up_source == "frontmatter") names the target
            # as a property (ADR-6 derived, never hardcoded) — the fix is a
            # YAML-property edit, not a body edit, so "up::" would misdescribe
            # the action. Body-resident wording is unchanged (CON-7).
            if detail.get("up_source") == "frontmatter":
                lines.append(
                    "- **Repoint to:** [[]]    ← enter the correct MOC to "
                    f"repoint the `{up_property}` property, or leave empty to remove"
                )
            else:
                lines.append(
                    "- **Repoint to:** [[]]    ← enter the correct MOC to repoint "
                    "up::, or leave empty to remove"
                )
        elif check in ("unparented", "orphan"):
            # File under: the MOC to file this orphan under. Semantically clearer
            # than "Repoint to:" for filing (Change 2). Typed value / picked
            # suggestion / scan candidate feed the file_note target (parser).
            lines.append(
                "- **File under:** [[]]    ← enter a MOC to file this note under, "
                "or pick a suggestion below"
            )
        # Suggest opt-in (Phase 7, D1): a SEPARATE box, decoupled from Apply.
        # Pass-1 renders only this static checkbox — no per-finding computation.
        # Ticking it and running `/garden-audit --suggest` fills a pick list.
        # Change 2: structure findings (unparented/orphan) also get the opt-in.
        if check in ("dead_link", "broken_up", "unparented", "orphan"):
            lines.append(
                "- [ ] Suggest targets — tick, then run `/garden-audit --suggest` "
                "to get candidate picks here"
            )
        lines.append("")
    elif f.get("tier") == "advisory":
        # Advisory → read-only note, no checkbox. Auto-pushback (2026-07-23):
        # approving the report pauses ALL advisories for the window — no
        # per-finding tick (the preamble states this once).
        lines += [
            "_Advisory — no automated fix. Review and handle manually._",
            "",
        ]
    else:
        # Fixable finding without a decision block is a contract violation from the
        # producer. Fail loudly — a silent skip would produce an incomplete render.
        raise ValueError(
            f"fixable finding {fid!r} missing decision block — "
            "garden-audit.py must always emit a decision on fixable findings"
        )

    return lines


def _render_tier_section(tier: str, findings: list[dict], up_property: str,
                         ack_days: int = 30) -> list[str]:
    """Render one tier section (e.g. ## Integrity). Returns [] when no findings."""
    tier_findings = [f for f in findings if f["tier"] == tier]
    if not tier_findings:
        return []
    lines = [f"## {_TIER_LABEL[tier]}", ""]
    if tier == "advisory":
        # Auto-pushback note (2026-07-23): approving the report pauses every
        # advisory below for the window — no per-finding action needed.
        lines += [
            f"_Approving this report pauses the advisories below for "
            f"{ack_days} days — they reappear afterwards if still unresolved._",
            "",
        ]
    for f in tier_findings:
        lines.extend(_render_finding(f, up_property))
    return lines


def render_report(d: dict) -> str:
    """Render the full markdown report body (without frontmatter) as a string."""
    findings = d.get("findings") or []
    date = d["generated"][:10]

    # ADR-6 (spec 032): the property name shown in the T5.1 disclosure is always
    # derived from the active profile's configured parent marker — never
    # hardcoded to "up" — via the same marker_word() SSoT the rest of the
    # pipeline uses.
    conventions = resolve_conventions(
        profile_override=d.get("profile"), profiles_dir=DEFAULT_PROFILES_DIR
    )
    up_property = marker_word(conventions.parent_marker)

    ack_days = d.get("advisory_pushback_days") or 30
    parts: list[str] = []
    parts += ["", f"# Knowledge-Garden Audit — {date}", ""]
    parts += [
        "Review the findings below. Tick **Apply** on the fixes you want; fill in "
        "**Replace with:** / **Repoint to:** where offered. Then run `/inbox` to "
        "apply via Hashi. Advisory findings are read-only — approving this report "
        f"pauses them for {ack_days} days (they reappear if still unresolved).",
        "",
        # Top-level approve gate (ADR-1 revised): garden-audit now mirrors the
        # suggestions doc — the doc is only picked up by /inbox once this box is
        # ticked. Matches suggestions-render.py's Approved box shape.
        "- [ ] Approved — check this box when you've finished reviewing, then "
        "run `/inbox` to apply the ticked fixes.",
        "",
    ]
    parts += _render_caveats()
    parts += _render_preamble(d)
    parts += _render_summary(findings)
    parts += _render_broken_up_split(findings)
    parts += _render_unroutable_summary(findings, up_property)
    for tier in ("integrity", "structure", "advisory"):
        parts += _render_tier_section(tier, findings, up_property, ack_days)

    return "\n".join(parts)


# ── --suggest enrichment (Phase 7, T7.2) ──────────────────────────────────────
# Second-pass, on-demand: rewrite ONLY Suggest-ticked dead_link/broken_up blocks
# with a candidate pick list. Everything else (Approved gate, other findings,
# un-ticked blocks) is preserved byte-for-byte.

_RE_FINDING_HEADER = re.compile(r"^###\s+(F\d+)\b")
_RE_SUGGEST_TICKED = re.compile(r"^\s*-\s+\[x\]\s+Suggest targets\b", re.IGNORECASE)
# The editable field line a pick list / no-suggestions note is inserted after.
_RE_EDITABLE_FIELD = re.compile(
    r"^\s*-\s+\*\*(Replace with|Repoint to|File under):\*\*", re.IGNORECASE
)
# A pick sub-checkbox line inserted by a prior --suggest run (for idempotency).
_RE_PICK_LINE = re.compile(r"^\s*-\s+\[[ x]\]\s+\[\[.*\]\]\s*\(\d")
_PICK_HEADER = "  Pick one (tick a candidate, or type your own above):"
# Explicit feedback when no candidate cleared the cutoff (Change 3).
_NO_SUGGESTIONS_NOTE = (
    "  _No suggestions found — nothing cleared the similarity cutoff. "
    "Type a target manually above._"
)


def _split_report_blocks(report_md: str) -> list[list[str]]:
    """Split the report into blocks: the preamble, then one per `### F<id>`.

    Block 0 is everything before the first finding heading (frontmatter, banner,
    Approved gate, summary, tier headings). Each subsequent block starts at a
    `### F<id>` heading and runs until the next one (or EOF).
    """
    blocks: list[list[str]] = [[]]
    for line in report_md.splitlines():
        if _RE_FINDING_HEADER.match(line):
            blocks.append([line])
        else:
            blocks[-1].append(line)
    return blocks


def _strip_existing_pick_list(block: list[str]) -> list[str]:
    """Remove a prior run's pick header + pick lines + no-suggestions note from a
    block, so re-running --suggest replaces rather than duplicates (idempotent)."""
    out: list[str] = []
    for line in block:
        r = line.rstrip()
        if r == _PICK_HEADER.rstrip() or r == _NO_SUGGESTIONS_NOTE.rstrip():
            continue
        if _RE_PICK_LINE.match(line):
            continue
        out.append(line)
    return out


def _split_cache_entries(entries: list[dict]) -> tuple[list[str], list[dict]]:
    """Split MOC-structure cache entries into (note_stems, moc_entries).

    Shared by the markdown (enrich_report_with_suggestions) and wire
    (enrich_wire_with_candidates) enrichment paths so the candidate-scoring inputs
    are derived identically in both.
    """
    note_stems = [
        str(e.get("stem")) for e in entries
        if isinstance(e, dict) and e.get("kind") == "note" and e.get("stem")
    ]
    moc_entries = [
        e for e in entries if isinstance(e, dict) and e.get("kind") == "moc"
    ]
    return note_stems, moc_entries


def _candidates_for_block(finding: dict, note_stems: list[str],
                          moc_entries: list[dict]) -> list[dict]:
    """Compute candidate picks for one fixable finding from the wire + cache."""
    check = finding.get("check")
    detail = finding.get("detail") or {}
    if check == "dead_link":
        dead_target = detail.get("dead_target", "")
        return suggest_dead_link_targets(dead_target, note_stems)
    if check == "broken_up":
        target = finding.get("target") or {}
        note_entry = {
            "stem": target.get("stem", ""),
            "path": target.get("path", ""),
            "topics": detail.get("topics") or [],
        }
        broken = unwrap_list_repr(detail.get("up_target", ""))
        if isinstance(broken, (list, tuple)):
            broken = broken[0] if broken else ""
        return suggest_repoint_mocs(note_entry, moc_entries, str(broken))
    if check in ("unparented", "orphan"):
        target = finding.get("target") or {}
        note_entry = {
            "stem": target.get("stem", ""),
            "path": target.get("path", ""),
            "topics": detail.get("topics") or [],
        }
        return suggest_file_under_mocs(note_entry, moc_entries)
    return []


def _enrich_block(block: list[str], finding: dict, note_stems: list[str],
                  moc_entries: list[dict]) -> list[str]:
    """Rewrite a Suggest-ticked block: insert a pick list after the editable field
    when candidates exist, else an explicit 'No suggestions found' note (Change 3),
    so the user always gets feedback. Non-ticked blocks are untouched."""
    block = _strip_existing_pick_list(block)
    if not any(_RE_SUGGEST_TICKED.match(ln) for ln in block):
        return block  # not opted in — untouched

    candidates = _candidates_for_block(finding, note_stems, moc_entries)
    if candidates:
        insert_lines = [_PICK_HEADER]
        insert_lines += [
            f"  - [ ] [[{c['target']}]] ({c['score']:.2f})" for c in candidates
        ]
    else:
        # Zero candidates cleared the cutoff — an explicit note, never silent.
        insert_lines = [_NO_SUGGESTIONS_NOTE]

    out: list[str] = []
    inserted = False
    for line in block:
        out.append(line)
        if not inserted and _RE_EDITABLE_FIELD.match(line):
            out.extend(insert_lines)
            inserted = True
    if not inserted:
        # No editable field found — append at the block end rather than dropping.
        out.extend(insert_lines)
    return out


def enrich_report_with_suggestions(
    report_md: str, wire: dict, entries: list[dict]
) -> str:
    """Rewrite Suggest-ticked dead_link/broken_up blocks with a candidate pick list.

    STRUCTURE comes from ``wire`` (joined by F-id) and the note/MOC stems come from
    the cache ``entries``. Only Suggest-ticked fixable blocks are rewritten; every
    other line — the preamble, the Approved gate, un-ticked and advisory blocks —
    is preserved byte-for-byte. Idempotent: a prior run's pick list is stripped
    before a fresh one is inserted.
    """
    findings_by_id = {
        f.get("id"): f for f in (wire or {}).get("findings") or [] if f.get("id")
    }
    note_stems, moc_entries = _split_cache_entries(entries)

    blocks = _split_report_blocks(report_md)
    out_blocks: list[list[str]] = [blocks[0]]  # preamble untouched
    for block in blocks[1:]:
        m = _RE_FINDING_HEADER.match(block[0])
        fid = m.group(1) if m else None
        finding = findings_by_id.get(fid)
        if finding and finding.get("check") in (
            "dead_link", "broken_up", "unparented", "orphan"
        ):
            out_blocks.append(_enrich_block(block, finding, note_stems, moc_entries))
        else:
            out_blocks.append(block)

    result = "\n".join("\n".join(b) for b in out_blocks)
    # splitlines() drops a trailing newline — restore it so an un-enriched report
    # round-trips byte-for-byte.
    if report_md.endswith("\n") and not result.endswith("\n"):
        result += "\n"
    return result


# ── --suggest wire enrichment (spec 030 Tomo-Editor channel) ──────────────────
# The Tomo-Editor reads the JSON (Hashi's channel), so --suggest must write the
# scored candidates into decision.candidates there too — not only into the
# markdown pick lists. Candidate computation is SSoT'd via _candidates_for_block.

def _suggest_requested_ids(report_md: str, wire: dict) -> set[str]:
    """F-ids that want LLM candidates: markdown Suggest-ticked OR wire suggest_requested.

    Two channels select findings for enrichment: the human channel (a
    ``- [x] Suggest targets`` tick in the markdown block, existing) and the
    Tomo-Editor channel (``decision.suggest_requested: true`` in the wire, new).
    Union of both — either opts a finding in.
    """
    ids: set[str] = set()
    # Markdown channel: a Suggest-ticked block.
    for block in _split_report_blocks(report_md)[1:]:
        m = _RE_FINDING_HEADER.match(block[0])
        if not m:
            continue
        if any(_RE_SUGGEST_TICKED.match(ln) for ln in block):
            ids.add(m.group(1))
    # Wire channel: decision.suggest_requested.
    for f in (wire or {}).get("findings") or []:
        decision = f.get("decision") or {}
        if decision.get("suggest_requested") and f.get("id"):
            ids.add(f["id"])
    return ids


def enrich_wire_with_candidates(
    wire: dict, entries: list[dict], requested_ids: set[str]
) -> tuple[dict, int]:
    """Write decision.candidates=[{stem,score}] + the suggested ran-marker into the wire.

    Mutates ``wire`` and returns ``(wire, processed)`` where ``processed`` counts
    the findings enriched this run. For each fixable finding whose id is in
    ``requested_ids``, decision.candidates is set to the scored candidates
    (SSoT via _candidates_for_block, mapped {target,score}→{stem,score}) AND
    decision.suggested is stamped True — whatever the candidate count — so a
    ran-and-empty finding (suggested:true, candidates:[]) is distinguishable
    from one still awaiting a run (suggest_requested:true, no suggested).
    Every other finding's candidates is cleared to [] and its suggested marker
    removed so a re-run is idempotent (un-ticking returns the default state).
    The caller MUST NOT re-stamp emit_digest — candidates and suggested are
    excluded from compute_garden_audit_digest, so the original baseline stays
    correct (and re-stamping would clobber a pre-existing user apply-edit).
    """
    note_stems, moc_entries = _split_cache_entries(entries)
    processed = 0
    for finding in (wire or {}).get("findings") or []:
        decision = finding.get("decision")
        if not isinstance(decision, dict):
            continue  # advisory finding — no decision block
        if finding.get("id") in requested_ids:
            cands = _candidates_for_block(finding, note_stems, moc_entries)
            decision["candidates"] = [
                {"stem": c["target"], "score": c["score"]} for c in cands
            ]
            decision["suggested"] = True
            processed += 1
        else:
            decision["candidates"] = []
            decision.pop("suggested", None)
    # Recompute the suggest-before-approve gate: after this run, every requested
    # finding carries `suggested`, so pending clears (unless a request remains
    # un-run for some reason). Excluded from emit_digest — no re-stamp needed.
    if isinstance(wire, dict):
        wire["suggest_pending"] = _wire_suggest_pending(wire.get("findings") or [])
    return wire, processed


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
            check = f.get("check")
            wire_decision: dict = {
                # Opt-in ticking (0.11.0): unselected unless the doc says otherwise.
                "selected": decision.get("selected", False),
                "action": decision.get("action"),
            }
            # dead_link: add editable replace slot (empty = remove intent).
            # The user fills this in the wire to specify a replacement target;
            # garden-audit-parser reads decision.replace (not detail.dead_target).
            if check == "dead_link":
                wire_decision["replace"] = ""
            # broken_up: add editable repoint slot (empty = remove intent). Wire
            # parity with the markdown path's "Repoint to:" field — a non-empty
            # value repoints up:: to the user's chosen MOC (add_relationship),
            # empty removes the broken line. Parser reads decision.repoint.
            if check == "broken_up":
                wire_decision["repoint"] = ""
            # unparented/orphan: add editable file_under slot (empty = no target)
            # — the Tomo-Editor's filing target, parallel to repoint/replace.
            # Parser's file_note branch reads decision.file_under.
            if check in ("unparented", "orphan"):
                wire_decision["file_under"] = ""
            # Tomo-Editor channel fields (spec 030). candidates: display-only LLM
            # picks the editor renders — empty at first render, populated by
            # --suggest. suggest_requested: the editor's flag marking findings that
            # want LLM candidates (drives --suggest selection). Both are EXCLUDED
            # from the change-detection digest (compute_garden_audit_digest) so
            # Tomo-written candidates never read as a user edit.
            wire_decision["candidates"] = []
            wire_decision["suggest_requested"] = False
            wf["decision"] = wire_decision
        wire_findings.append(wf)

    payload: dict = {
        "schema_version": "1",
        "generated": d["generated"],
        "run_id": d["run_id"],
        "profile": d.get("profile"),
        # Top-level JSON-side approve gate (Q1): the Tomo-Editor works from the
        # JSON, so it sets this true on "ready for /inbox". The markdown "- [x]
        # Approved" box still works for .md-only users. Excluded from the
        # change-detection digest.
        "approved": bool(d.get("approved", False)),
        # Suggest-before-approve gate (2026-07-24): true while any finding
        # requested candidates but --suggest hasn't run. False at initial render
        # (nothing requested yet); the editor sets it true on a suggest request,
        # --suggest recomputes it false. Excluded from emit_digest.
        "suggest_pending": _wire_suggest_pending(wire_findings),
        "findings": wire_findings,
    }
    payload["emit_digest"] = compute_garden_audit_digest(payload)
    return payload


def _wire_suggest_pending(findings: list[dict]) -> bool:
    """True iff any fixable finding requested suggestions that --suggest hasn't
    fulfilled yet (decision.suggest_requested and not decision.suggested)."""
    for f in findings or []:
        decision = f.get("decision")
        if isinstance(decision, dict) and decision.get("suggest_requested") \
                and not decision.get("suggested"):
            return True
    return False


def _log_unroutable_findings(findings: list[dict], stream=None) -> None:
    """One [garden-audit]-prefixed stderr line per withheld finding (solution.md
    System-Wide Patterns: "unroutable findings go to stderr with the existing
    [garden-audit] prefix, naming the note and the reason").

    ``stream`` defaults to ``sys.stderr`` read at CALL time, not def time — a
    default bound at definition time would capture the stream object current
    at module import, before a test's capsys redirection ever takes effect.
    """
    stream = stream if stream is not None else sys.stderr
    for f in findings:
        reason = _broken_up_withhold_reason(f)
        if reason is None:
            continue
        target = f.get("target") or {}
        note = target.get("stem") or target.get("path") or f.get("id")
        print(
            f"[garden-audit] Withheld {f.get('id')} — {note}: not routable ({reason})",
            file=stream,
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(
        description="Render garden-audit-doc.json to markdown report + wire JSON."
    )
    # Instance-relative STABLE defaults (spec 030): the agent calls this bare and
    # stamps the RUN_ID only on the kado-write-file --vault target, not here.
    p.add_argument(
        "--input", default="tomo-tmp/garden-audit-doc.json",
        help="Path to garden-audit-doc.json",
    )
    p.add_argument(
        "--output", default="tomo-tmp/garden-audit-report.md",
        help="Output markdown file path",
    )
    p.add_argument(
        "--json-output", default="tomo-tmp/garden-audit-wire.json",
        help="Output path for garden-audit-wire.json (ADR-4). The wire is the "
             "STRUCTURE source and is always written.",
    )
    args = p.parse_args()

    with open(args.input, encoding="utf-8") as f:
        d = json.load(f)

    fm_lines = render_frontmatter(d)
    report_body = render_report(d)
    content = "\n".join(fm_lines) + "\n" + report_body

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(content)

    # The wire is the always-read STRUCTURE source (two-artifact split) — always
    # write it alongside the report.
    wire = build_wire_payload(d)
    with open(args.json_output, "w", encoding="utf-8") as f:
        json.dump(wire, f, ensure_ascii=False, indent=2)

    _log_unroutable_findings(d.get("findings") or [])

    finding_count = len(d.get("findings") or [])
    print(
        f"garden-audit-render: findings={finding_count} out={args.output} "
        f"wire={args.json_output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
