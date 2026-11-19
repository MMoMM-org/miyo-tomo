# review_setup_rows.py — may these section and off-limits rows be saved: the setup-input row checks of /review.
# version: 0.2.0
"""The row checks of ``review-session.py setup-input`` (spec 046 T2.2; PRD F2-AC4, F2-AC11, F2-AC12, Rule 4).

``read_evidence(path)`` reads the rows file ``match`` wrote (``lib/review_match.write_rows``):
``{template, outline, resolved}``, None when it is absent or of another shape. ``previous_rows(config,
kind, template)`` are the saved section rows the ids come from (the confirmed template's and the
configured one's); ``saved_off_limits(config, kind, template)`` the saved marks. ``with_ids(data,
previous)`` gives every section row without an id its id (``review_mapping.assign_ids``).
``problems(data, evidence, saved_off)`` returns the refusals of a schema-valid writer input, as
``review_config.Problem``: ``template-not-found`` (``/template``), and per row ``section-not-in-template``,
``section-off-limits``, ``section-left-out`` (with ``reason``), ``analysis-not-automatic``
(``/sections/<i>``), ``landing-off-limits`` (``/sections/<i>/placement``, ``/place``). The evidence is
never read from ``data``. No Kado, no model, no writes.

Design notes: docs/tomo/scripts/lib/review_setup_rows.md
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from lib import review_config as rc
from lib.review_mapping import (
    AUTOMATIC, OFF_LIMITS, HeadingKey, TemplateHeading, assign_ids, from_outline, landing, landing_off_limits,
    outline_top, row_key,
)
from lib.vault_config_edit import get_path

TEMPLATE_NOT_FOUND = "template-not-found"
NOT_IN_TEMPLATE = "section-not-in-template"
SECTION_OFF_LIMITS = "section-off-limits"
LEFT_OUT = "section-left-out"
NOT_AUTOMATIC = "analysis-not-automatic"
LANDING = "landing-off-limits"
MISSING = "missing"                       # the template_kind of a name Kado did not find
REVIEW = "review"                         # an analysis row's placement (F2-AC12)
LANDS = {"before": "before", "inside": "inside"}   # placements whose lines leave the heading

Outline = Tuple[List[TemplateHeading], List[Tuple[int, str]]]


# --- the evidence and the saved rows --------------------------------------------------------

def read_evidence(path: Path) -> Optional[dict]:
    """``{template, outline, resolved}`` of the rows file; None when absent or not what ``match`` writes."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        from_outline(data["outline"], [])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    resolved = data.get("resolved")
    if not isinstance(resolved, dict):
        return None
    return {"template": data.get("template"), "outline": data["outline"], "resolved": resolved}


def _saved(config: dict, kind: str, template, name: str) -> List[dict]:
    return rc.template_rows(config, kind, template, name, []) if isinstance(template, str) else []


def previous_rows(config: dict, kind: str, template) -> List[dict]:
    """The saved section rows ids are kept from: the configured template's first, the confirmed one's last."""
    configured = get_path(config, ("templates", "mapping", rc.GRANULARITY[kind]))[1]
    rows = _saved(config, kind, configured, rc.SECTIONS) if configured != template else []
    return rows + _saved(config, kind, template, rc.SECTIONS)


def saved_off_limits(config: dict, kind: str, template) -> List[dict]:
    return _saved(config, kind, template, rc.OFF_LIMITS)


def with_ids(data: dict, previous: Sequence[dict]) -> dict:
    """``data`` with an id on every section row; unchanged when the rows are not dicts, a heading key is
    unhashable or no id is left (the schema then names the row)."""
    rows = data.get(rc.SECTIONS)
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        return data
    try:
        return {**data, rc.SECTIONS: assign_ids(rows, previous)}
    except (ValueError, TypeError):
        return data


# --- the refusals ---------------------------------------------------------------------------

def _resolved(evidence: dict, template: str) -> bool:
    resolved = evidence["resolved"]
    return resolved.get("template") == template and resolved.get("kind") != MISSING


def _template_problem(data: dict, evidence: Optional[dict]) -> Optional[rc.Problem]:
    template = data.get("template")
    if isinstance(template, str) and evidence is not None and not _resolved(evidence, template):
        return rc.Problem("/template", TEMPLATE_NOT_FOUND)
    rows = data.get(rc.SECTIONS) or data.get(rc.OFF_LIMITS)
    if rows and (evidence is None or evidence["template"] != template):
        return rc.Problem("/template", TEMPLATE_NOT_FOUND)
    return None


def _covered(outline: Outline, head: TemplateHeading, placement: str, off: Sequence[dict]) -> bool:
    found = landing(outline[0], outline[1], head.line, placement)
    return found is not None and landing_off_limits(found, off) is not None


def _row_problem(i: int, row: dict, by_key: Dict[HeadingKey, TemplateHeading], outline: Outline,
                 off: Sequence[dict]) -> Optional[rc.Problem]:
    pointer = f"/{rc.SECTIONS}/{i}"
    head = by_key.get(row_key(row))
    if head is None:
        return rc.Problem(pointer, NOT_IN_TEMPLATE)
    if head.reason == OFF_LIMITS:
        return rc.Problem(pointer, SECTION_OFF_LIMITS)
    if row["placement"] == REVIEW and head.reason is None:
        return rc.Problem(pointer, NOT_AUTOMATIC)
    if head.reason is not None and not (row["placement"] == REVIEW and head.reason == AUTOMATIC):
        return rc.Problem(pointer, LEFT_OUT, reason=head.reason)
    if row["placement"] in LANDS and _covered(outline, head, LANDS[row["placement"]], off):
        return rc.Problem(pointer + "/placement", LANDING)
    return None


def _place_problem(place: dict, outline: Outline, off: Sequence[dict]) -> Optional[rc.Problem]:
    """The "Tomo Review" place lands ``before`` / ``inside`` (its whole section) the first heading with the anchor
    text."""
    heads, top = outline
    entries = sorted([(h.line, h.heading) for h in heads] + list(top))
    line = next((ln for ln, text in entries if text == place["anchor"]), None)
    if line is None:
        return None
    found = landing(heads, top, line, LANDS[place["placement"]])
    if found is not None and landing_off_limits(found, off) is not None:
        return rc.Problem("/place", LANDING)
    return None


def problems(data: dict, evidence: Optional[dict], saved_off: Sequence[dict]) -> List[rc.Problem]:
    """The refusals of a schema-valid writer input against the ``match`` evidence (never against ``data``)."""
    refused = _template_problem(data, evidence)
    if refused is not None:
        return [refused]
    if evidence is None or evidence["template"] != data.get("template"):
        return []                                    # no rows to check; the place is checked at plan time
    off = data[rc.OFF_LIMITS] if rc.OFF_LIMITS in data else list(saved_off)
    heads = from_outline(evidence["outline"], off)
    outline = (heads, outline_top(evidence["outline"]))
    by_key = {h.key: h for h in heads}
    out = [_row_problem(i, row, by_key, outline, off) for i, row in enumerate(data.get(rc.SECTIONS, []))]
    out.append(_place_problem(data["place"], outline, off))
    return [p for p in out if p is not None]
