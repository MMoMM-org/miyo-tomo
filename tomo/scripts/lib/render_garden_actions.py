# version: 0.1.0
"""render_garden_actions.py — garden-audit action assembly (spec 030/032).

Split out of render_actions.py (#216, Constitution L2 file size). Garden-audit
confirmed_items are semantic fix items, not the suggestions manifest, so they
get their own assembler (build_garden_audit_actions) and their own builders:
edit_note_text, and edit_frontmatter with its pure value/expected transform.
Nothing here is reached from build_actions.
"""
from __future__ import annotations

from lib.profile_conventions import marker_word
from lib.render_emit import _next_id
from lib.render_md import bare_stem


def _build_edit_note_text_actions(
    items: list[dict],
    counter: list[int],
) -> list[dict]:
    """Emit edit_note_text actions for body-level text edits (ADR-3, spec 030).

    Each item must carry: path (str), match (str), replace (str).
    occurrence defaults to "first" when absent.

    Covers three fix cases with one primitive:
      - dead wikilink fix:    match="[[Old]]", replace="[[New]]"
      - dead wikilink remove: match="[[Old]]", replace=""
      - broken up:: remove:   match="up:: [[Deleted MOC]]", replace=""

    Broken-up REPOINT stays on add_relationship (marker-located line replace) —
    this builder is ONLY for removal + free-text wikilink substitution (ADR-5,
    Rule 7). Never call this builder for repoints.

    Caller is responsible for stamping ``applied: False`` before wire emission —
    this builder does not emit ``applied``, matching the convention of _build_*
    helpers normally stamped centrally by build_actions(). T4.2's garden-audit-
    parser calls this builder directly via build_from_wire, bypassing build_actions,
    so the caller must stamp applied explicitly.
    """
    out: list[dict] = []
    for item in items:
        out.append({
            "id": _next_id(counter),
            "action": "edit_note_text",
            "path": item["path"],
            "match": item["match"],
            "replace": item["replace"],
            "occurrence": item.get("occurrence", "first"),
        })
    return out


class UnsupportedShapeError(ValueError):
    """Raised by ``_construct_edit_frontmatter_fields`` when ``up_value``'s
    shape has no defined transform (spec 032 T3.2 — a YAML map, today the only
    such shape).

    A distinct exception rather than a sentinel return: it keeps the success
    contract of ``_construct_edit_frontmatter_fields`` to exactly one shape
    (always the ``{operation, value?, expected}`` triad) instead of a second,
    easy-to-forget-to-check return shape. The caller (``_route_broken_up``,
    T3.2's minimal parser touch) never actually triggers this — it detects the
    map shape itself before calling the transform, using the SAME
    ``isinstance(up_value, dict)`` test, and records "unsupported-shape" in
    ``unroutable`` directly. This exception exists so the transform's own
    contract is enforced and independently testable, per the SDD: "guessing a
    transform for a shape we have never seen is how the current defect was
    born."
    """


def _construct_edit_frontmatter_fields(
    up_value, up_target: str, choice: str, *, new_target: str | None = None,
) -> dict:
    """Build the ``{operation, value, expected}`` triad for one broken-`up`
    frontmatter fix (spec 032 T3.2 — SDD "Constructing value and expected —
    traced walkthrough").

    Pure transform only: given the observed property value, the broken stem,
    and the user's remove/repoint choice, decides ``operation`` (``set`` vs
    ``remove``), builds ``value`` (only for ``set``), and carries ``expected``
    through untouched. Does NOT assemble an action dict, derive the property
    name, stamp ``applied``, or touch a confirmed_item — that wiring is T3.3's
    ``_build_edit_frontmatter_actions``.

    ``new_target`` is required (and used) only when ``choice == "repoint"`` —
    keyword-only so a caller cannot accidentally supply it positionally for a
    "remove" call.

    Three rules this function exists to get right (SDD, "three consequences
    worth stating plainly"):

    1. **"Remove" is usually ``operation: "set"``, not ``"remove"``.**
       ``remove`` deletes the WHOLE property and is correct only when the
       broken entry was its sole content — reaching for ``remove`` on user
       choice alone would delete a legitimate sibling parent MOC.
    2. **Order is preserved by construction.** A copy of ``up_value`` is
       transformed in place (index-replaced for repoint, filtered for
       remove) — never rebuilt from a re-derived set of stems.
    3. **Scalar shape is preserved.** A scalar ``up_value`` yields a scalar
       ``value``; it is never normalised into a one-item list. Normalising
       would change the note beyond the approved fix AND fail Hashi's
       deep-equal ``expected`` guard.

    4. **CONTRACT — ``up_value`` is never normalised, anywhere on the path
       from cache to wire.** Not sorted, not de-duplicated, not re-wrapped.
       Hashi confirmed the mechanism 2026-09-03 (handoff
       ``2026-09-03_hashi-to-tomo_up-source-routing-confirmed-and-one-rerun-asymmetry``):
       their ``expected`` comparison is ``deepEqual`` over the PARSED YAML
       value, and for arrays it is element-wise **and order-sensitive** —
       ``[A, B]`` does not match ``[B, A]``, deliberately, so the guard
       cannot pass on a note someone reordered. A normalising "cleanup" here
       would therefore fail every guard at APPLY time in a user's vault
       while every fixture in this repo stayed green. Treat as a contract,
       not a convention.

    ``expected`` is always the ``up_value`` argument itself, byte-for-byte,
    in every branch — never the transformed copy. ``expected_absent`` is
    never emitted: every property this spec targets exists (it is the source
    of the broken target), so the guard is a plain absence, not a code path.

    A map-shaped ``up_value`` has no defined transform (SDD, Complex Logic:
    "no known occurrence in the measured population, and guessing a transform
    for a shape we have never seen is how the current defect was born") and
    raises ``UnsupportedShapeError`` rather than silently guessing one.
    """
    if isinstance(up_value, dict):
        raise UnsupportedShapeError(
            f"up_value is a map — no transform defined (up_target={up_target!r})"
        )
    if choice not in ("remove", "repoint"):
        raise ValueError(f"unknown choice: {choice!r}")
    if choice == "repoint" and new_target is None:
        raise ValueError("repoint requires new_target")

    match_key = bare_stem(up_target)
    is_scalar = not isinstance(up_value, list)

    if choice == "repoint":
        replacement = f"[[{new_target}]]"
        if is_scalar:
            # No match (observed value != the broken target) is a deliberate
            # no-op — a stale/inconsistent cache must never crash the pipeline
            # or guess a transform; locked by test (T3.3 code-quality carryover).
            value = replacement if bare_stem(up_value) == match_key else up_value
            return {"operation": "set", "value": value, "expected": up_value}
        value = list(up_value)
        for i, entry in enumerate(value):
            if bare_stem(entry) == match_key:
                value[i] = replacement
        return {"operation": "set", "value": value, "expected": up_value}

    # choice == "remove"
    if is_scalar:
        if bare_stem(up_value) == match_key:
            return {"operation": "remove", "expected": up_value}
        # Same deliberate no-op as the repoint branch above: no match, no guess.
        return {"operation": "set", "value": up_value, "expected": up_value}
    remaining = [e for e in up_value if bare_stem(e) != match_key]
    if not remaining:
        return {"operation": "remove", "expected": up_value}
    return {"operation": "set", "value": remaining, "expected": up_value}


def _build_edit_frontmatter_actions(
    items: list[dict], counter: list[int], parent_marker: str = "up::",
) -> list[dict]:
    """Build ``edit_frontmatter`` actions for broken-`up` fixes whose parent is
    declared in frontmatter (spec 032 T3.3 — the wiring named by the SDD's
    Integration Points).

    Each item is an ``edit_frontmatter`` confirmed_item carrying ``up_value``,
    ``up_target``, ``choice`` (and ``new_target`` for a repoint) — threaded by
    garden-audit-parser.py exactly as ``add_relationship`` carries ``up_line``
    and ``remove_up_link`` carries ``link``. This builder derives ``property``
    via ``marker_word(parent_marker)`` (ADR-6 — never hardcoded, so a profile
    configured with a different marker yields a different property name), and
    delegates ``operation``/``value``/``expected`` to the pure transform
    ``_construct_edit_frontmatter_fields`` (T3.2). ``value`` is included only
    when the transform returns it (operation='set') — T3.2 omits the key
    entirely for 'remove', and this builder must not re-add it via a default.

    Caller is responsible for stamping ``applied: False`` before wire emission
    — this builder does not emit it, matching ``_build_edit_note_text_actions``'
    convention; ``build_garden_audit_actions`` stamps the whole output
    centrally.
    """
    property_name = marker_word(parent_marker)
    out: list[dict] = []
    for item in items:
        fields = _construct_edit_frontmatter_fields(
            item["up_value"], item["up_target"], item["choice"],
            new_target=item.get("new_target"),
        )
        action = {
            "id": _next_id(counter),
            "action": "edit_frontmatter",
            "path": item["path"],
            "property": property_name,
            "operation": fields["operation"],
            "expected": fields["expected"],
        }
        if "value" in fields:
            action["value"] = fields["value"]
        out.append(action)
    return out


def build_garden_audit_actions(
    confirmed: list[dict],
    counter: list[int] | None = None,
    parent_marker: str = "up::",
) -> list[dict]:
    """Assemble Hashi actions from garden-audit confirmed_items (spec 030).

    Isolated from build_actions — garden-audit's confirmed_items are semantic
    fix items (garden_check / garden_action), NOT the suggestions manifest shape.
    Keeping a separate assembler leaves the suggestions/moc-proposal hot path in
    build_actions untouched (ADR: "no new apply path… mirror /moc-propose").

    garden_action → actions:
      - resolve_dead_link → one resolve_dead_link (dead_link unlink/repoint —
        Hashi edits the body with alias/embed awareness; replace='' unlinks
        keeping the display, '[[New]]' repoints). Supersedes the literal
        edit_note_text construction, which no-opped on aliased links.
      - remove_up_link  → one remove_up_link (broken_up empty=remove — Hashi
        removes ONLY the broken link from the up:: line, keeps the up:: field
        (emptied) when it was the last link).
      - edit_note_text  → forward-compat only: no garden_action emits it now
        (dead_link moved to resolve_dead_link, broken_up remove to
        remove_up_link). Kept for the shared builder + Hashi's shipped surface.
      - add_relationship→ one add_relationship up:: (broken_up repoint).
      - file_note       → link_to_moc (bullet on the MOC) + add_relationship up::
        (up-link on the note). Files an unparented/orphan note under a MOC.
      - edit_frontmatter→ one edit_frontmatter (broken_up frontmatter-declared
        parent — spec 032 T3.3). Property name derived via
        marker_word(parent_marker) (ADR-6); operation/value/expected from
        _construct_edit_frontmatter_fields (T3.2).

    Single loop over ``confirmed`` — action IDs track input order (a file_note
    before an edit_note_text yields link_to_moc, add_relationship, edit_note_text
    with ascending IDs). Every action is stamped applied=False (build_actions does
    this centrally; this assembler bypasses it, so it stamps here).
    """
    counter = counter or [0]
    out: list[dict] = []

    for c in confirmed:
        ga = c.get("garden_action")
        if ga == "edit_note_text":
            # Reuse the shared builder on a one-item list — wires in dead code
            # while keeping this item's action in input order.
            out.extend(_build_edit_note_text_actions([c], counter))
        elif ga == "remove_up_link":
            out.append({
                "id": _next_id(counter),
                "action": "remove_up_link",
                "path": c["path"],
                "link": c["link"],
            })
        elif ga == "resolve_dead_link":
            out.append({
                "id": _next_id(counter),
                "action": "resolve_dead_link",
                "path": c["path"],
                "target": c["target"],
                "replace": c["replace"],
            })
        elif ga == "add_relationship":
            out.append({
                "id": _next_id(counter),
                "action": "add_relationship",
                "target_moc": None,
                "target_moc_path": c["path"],
                "marker": "up::",
                "line": c["up_line"],
                "source_note_title": None,
            })
        elif ga == "file_note":
            target_moc = c.get("target_moc", "")
            out.append({
                "id": _next_id(counter),
                "action": "link_to_moc",
                "target_moc": target_moc,
                "target_moc_path": c.get("target_moc_path"),
                "anchor": {"type": "callout", "value": None},
                "placement": "after",
                "line_to_add": f"- [[{c['stem']}]]",
                # A garden item is already in the vault, so its on-disk stem is
                # both its display name and its key — no split is needed here.
                # source_note_stem is deliberately ABSENT (spec 034 T6.4b): the
                # withholding passes that join on it act on move_note /
                # create_moc, which this branch never emits, and this builder's
                # output goes to the wire WITHOUT _strip_internal_link_fields —
                # scripts/gen-garden-audit-hashi-example.py calls it directly
                # and embeds the result in a Hashi handoff document. An internal
                # field here reaches Hashi and its schema rejects the action.
                "source_note_title": c["stem"],
            })
            out.append({
                "id": _next_id(counter),
                "action": "add_relationship",
                "target_moc": target_moc,
                "target_moc_path": c["path"],
                "marker": "up::",
                "line": f"up:: [[{target_moc}]]",
                "source_note_title": None,
            })
        elif ga == "edit_frontmatter":
            # Reuse the shared builder on a one-item list — same pattern as
            # edit_note_text above, keeping this item's action in input order.
            out.extend(_build_edit_frontmatter_actions([c], counter, parent_marker))

    for a in out:
        a["applied"] = False
    return out
