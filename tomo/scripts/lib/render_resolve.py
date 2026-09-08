# version: 0.4.0
"""render_resolve.py — post-build resolution + filtering passes for the action list.

Extracted from instruction-render.py (#42, D-07 Constitution L2 split). These passes
run AFTER build_actions and read the vault via Kado to resolve anchors, section
names, and target MOC paths, then filter out actions that cannot be applied
(missing daily notes, unappliable relationships). Kado-coupled — every function
takes the client as an argument; nothing here is imported by render_actions or
render_md, keeping the module graph a DAG.
"""
from __future__ import annotations

import re
import sys

import lib.moc_structure as moc_structure
from lib.render_helpers import _moc_stem, _stem, resolve_source_path
from lib.render_io import read_template

# Editable-callout name regex: captures the callout keyword from a callout header
# line, e.g. "[!blocks] Key Concepts" → "blocks". Used by resolve_section_names
# to score the list returned by moc_structure.parse_editable_callouts.
_EDITABLE_NAME_RE = re.compile(r"^\[!([A-Za-z][A-Za-z0-9_-]*)\]")

# Footer-marker callouts: content sections live BEFORE the first of these.
# Used to anchor a new section ahead of the MOC footer (#28 / F-36). Mirrors
# the LYT MOC template footer (docs/XDD/reference/tier-3/lyt-moc/section-placement.md).
# TODO F-55: make this profile-configurable rather than a hardcoded set.
FOOTER_CALLOUTS = {"video", "calendar", "puzzle", "compass"}


def resolve_section_names(actions: list[dict], client, editable_callouts: list[str]) -> int:
    """Best-effort: resolve the insertion anchor on callout- or line-typed
    link_to_moc actions by reading the target MOC.

    NOTE on "tier" — three independent concepts share the word elsewhere in
    this module; this docstring's tiers are ONLY the fourth:
      - Pass-1 LLM confidence tier (fit_confidence threshold, upstream).
      - Pass-2 source fallback (live MOC body first, then the create_moc's
        `template` body for not-yet-existing in-set MOCs) — see _resolve_from_moc
        / _resolve_from_template below.
      - The Pass-2 resolver fallback tier described here: _pick_anchor's
        four-way anchor selection, first match wins, applied to whichever body
        the source fallback supplied.

    _pick_anchor four-way anchor selection (first match wins):

      1. Editable callout — the highest-priority editable callout (config-driven,
         scored blocks > other > connect). Anchor stays type=callout.
      2. Content heading (#29 / F-30) — when the MOC has no editable callout,
         fall back to a content H2–H6 heading before the footer. Rewrites
         anchor.type to "heading" and placement to "after" (Hashi has no
         "inside" for headings).
      3. Footer callout (#28 / F-36) — when neither exists, anchor on the first
         footer-marker callout with placement="before". No heading is injected
         here (ADR-6, T5.2): the heuristic path emits a bare bullet. A fresh
         "## <section>" heading is added only when the Pass-1 LLM anchor carried
         a top-level new_section field, which _serialize_new_sections bakes into
         line_to_add later in the pipeline.
      4. Last body line (spec 023 AC-9) — when the MOC has no footer callout,
         anchor on the last non-blank, non-heading body line with type=line and
         placement="after". Returns None when no usable body line exists.

    The four-way selection is run against the live MOC body first, then (for
    not-yet-existing in-set MOCs) against the create_moc's `template` body —
    same selection rules apply.

    Function name retained for import stability. Leaves the anchor unresolved
    (action emitted as-is) when:
      - client is None (offline / test mode) or editable_callouts is empty
      - target_moc_path is null
      - neither the MOC nor its template yields a callout, heading, footer, or
        usable body line
      - Kado read fails for both the MOC and (where applicable) the template

    Returns the count of actions resolved.
    """
    if client is None or not editable_callouts:
        return 0
    editable_set = {name for name in editable_callouts if name}

    # `connect` is conventionally the navigation callout (up:: / related::),
    # not where content-note bullets belong. Drop it to the back of the line:
    # prefer `blocks` (Key Concepts) → any other editable → connect as last
    # resort.
    def _score(name: str) -> int:
        if name == "blocks":
            return 3
        if name == "connect":
            return 1
        return 2

    def _pick_editable_callout(editable_lines: list[str]) -> str | None:
        """Return the highest-priority editable callout's full first line (sans
        leading `> `) from a pre-parsed list, or None. Same scoring rules apply
        to live MOC bodies and template bodies (ADR-4)."""
        if not editable_lines:
            return None

        def _line_name(line: str) -> str:
            m = _EDITABLE_NAME_RE.match(line)
            return m.group(1) if m else ""

        # Highest score wins; ties resolved by first occurrence (stable sort
        # key: -i). _line_name extracts the callout type for _score.
        best = max(
            enumerate(editable_lines),
            key=lambda iv: (_score(_line_name(iv[1])), -iv[0]),
        )
        return best[1]

    def _pick_content_heading(headings: list[dict]) -> str | None:
        """First content H2–H6 heading (from a pre-parsed list) before the
        footer; prefer one that reads like a content section. Returns the
        heading text (sans leading #)."""
        texts = [h["text"] for h in headings]
        if not texts:
            return None
        preferred = {"key concepts", "concepts", "notes"}
        for h in texts:
            if h.lower() in preferred:
                return h
        return texts[0]

    def _find_footer_callout(lines: list[str]) -> str | None:
        """Full first line (sans `> `) of the first footer-marker callout."""
        idx = moc_structure.footer_index(lines, FOOTER_CALLOUTS)
        if idx >= len(lines):
            return None
        return moc_structure.strip_gt_prefix(lines[idx].rstrip())

    def _pick_anchor(content: str) -> dict | None:
        """Four-tier anchor resolution. Returns the anchor decision as a dict
        (type/value plus optional placement), or None when nothing is anchorable.
        new_section is no longer injected here (ADR-6, T5.2); it comes from
        the Pass-1 LLM anchor and lives at the top-level action field."""
        # Single split of the body (M5): one inventory covers editable callouts,
        # headings, and footer presence; `lines` is reused for the footer-line
        # lookup and the tier-4 body-line scan.
        lines = content.splitlines()
        inventory = moc_structure.parse_moc_inventory(
            content, FOOTER_CALLOUTS, editable_set
        )
        callout = _pick_editable_callout(inventory["editable_callouts"])
        if callout:
            return {"type": "callout", "value": callout}
        heading = _pick_content_heading(inventory["headings"])
        if heading:
            return {"type": "heading", "value": heading, "placement": "after"}
        if inventory["has_footer"]:
            footer = _find_footer_callout(lines)
            if footer:
                # ADR-6 (spec 022 T5.2): no hardcoded section name here.
                # new_section must come from the Pass-1 LLM anchor; the heuristic
                # path produces a bare bullet (placement=before, no heading prefix).
                return {
                    "type": "callout", "value": footer, "placement": "before",
                }
        # Tier 4 (spec 023 AC-9): no footer callout → last body line.
        # placement stays "after" (bullet lands below the last line).
        # Exclude blank lines and ALL heading lines (#, ##, … — any level).
        # Invariant: only H1 can realistically appear here because any H2–H6
        # would have been claimed by _pick_content_heading (tier 2) before
        # reaching this branch. The broad `#` filter is belt-and-suspenders.
        # Graceful degradation: if the body has no usable line, return None —
        # do NOT fabricate a line.
        # Also exclude callout-opener lines (`> [!important] …`): a non-editable,
        # non-footer callout opener is not a plain body line, so anchoring on it
        # as type=line would produce a type/value mismatch.
        body_lines = [
            ln for ln in lines
            if ln.strip()
            and not ln.lstrip().startswith("#")
            and not ln.lstrip().lstrip(">").lstrip().startswith("[!")
        ]
        if body_lines:
            return {"type": "line", "value": body_lines[-1], "placement": "after"}
        return None

    # Cache of anchor decisions keyed by live MOC path (read each MOC once).
    moc_body_cache: dict[str, dict | None] = {}

    def _resolve_from_moc(path: str) -> dict | None:
        if path in moc_body_cache:
            return moc_body_cache[path]
        try:
            result = client.read_note(path)
            content = result.get("content", "") or ""
        except Exception:  # noqa: BLE001
            moc_body_cache[path] = None
            return None
        res = _pick_anchor(content)
        moc_body_cache[path] = res
        return res

    # Cache of anchor decisions keyed by template name (templates are usually
    # shared across many in-set create_moc actions — read each at most once).
    template_body_cache: dict[str, dict | None] = {}

    def _resolve_from_template(template: str) -> dict | None:
        if template in template_body_cache:
            return template_body_cache[template]
        body = read_template(client, template)
        if body is None:
            template_body_cache[template] = None
            return None
        res = _pick_anchor(body)
        template_body_cache[template] = res
        return res

    # Index in-set create_moc actions by destination so the template-body
    # fallback can find the template a not-yet-existing MOC will be built from.
    # Keyed case-folded (CON-6, spec 034 T6.0) — the paired consumer of
    # `_build_create_moc_actions`' `by_dest`, which folds for the same reason.
    # Folding one without the other lets a link_to_moc miss the create_moc that
    # will actually land at its target and lose its anchor.
    create_moc_by_dest: dict[str, dict] = {}
    for a in actions:
        if a.get("action") == "create_moc":
            dest = a.get("destination")
            if dest:
                create_moc_by_dest[dest.casefold()] = a

    resolved = 0
    for a in actions:
        if a.get("action") != "link_to_moc":
            continue
        anchor = a.get("anchor")
        if not isinstance(anchor, dict):
            continue
        if anchor.get("type") not in ("callout", "line"):
            continue  # heading anchors are populated upstream, not here
        if anchor.get("value"):
            continue  # already set (honor-guard — leave populated anchors untouched)
        path = a.get("target_moc_path")
        if not path:
            continue
        res = _resolve_from_moc(path)
        if res is None:
            # Template-body fallback: in-set create_moc landing at this path
            # (the live MOC doesn't exist yet, so resolve against its template).
            create = create_moc_by_dest.get(path.casefold())
            if create:
                template = create.get("template")
                if template:
                    res = _resolve_from_template(template)
        if res:
            anchor["type"] = res["type"]
            anchor["value"] = res["value"]
            if res.get("placement"):
                a["placement"] = res["placement"]
            # new_section serialization removed: _serialize_new_sections (T5.2)
            # now handles this for ALL link_to_moc actions after this pass,
            # covering both honored (Pass-1) and heuristic-resolved anchors.
            resolved += 1
    return resolved


def _emit_resolution_telemetry(actions: list[dict]) -> None:
    """Emit a single metadata-only stderr line reporting four-tier MOC-insertion outcomes.

    Tallies per-tier counts across all link_to_moc actions and prints ONE tagged
    line. Privacy (Constitution L2): only metadata is recorded — tier names, MOC
    paths/stems, and counts. anchor.value (heading text) and note body content
    are NEVER included.

    Tier derivation (first match wins, execution order):
      1. top-level new_section set            → new_section tier
      2. anchor.value is None/absent          → unresolved
      3. anchor.type == "heading"             → heading tier
         + tier1_confident when fit_confidence is a number
      4. anchor.type == "callout"             → callout tier
      5. anchor.type == "line"                → line tier
      6. else                                 → unresolved

    Extra spec-023 counts (metadata-only — numbers, never text):
      tier1_confident   — heading anchors that carry a numeric fit_confidence
    """
    counts: dict[str, int] = {
        "heading": 0,
        "new_section": 0,
        "callout": 0,
        "line": 0,
        "unresolved": 0,
        "tier1_confident": 0,
    }
    moc_paths: list[str] = []
    # Individual placement confidence values (#64) — numbers only, never the
    # heading text (Constitution L2). Lets a multi-item run reconstruct the
    # fit_confidence distribution for tuning the 0.6 threshold (ADR-4).
    fit_values: list[float] = []

    for a in actions:
        if a.get("action") != "link_to_moc":
            continue
        moc_path = a.get("target_moc_path") or a.get("target_moc") or ""
        if moc_path:
            moc_paths.append(moc_path)
        anchor = a.get("anchor") or {}
        anchor_type = anchor.get("type")
        anchor_value = anchor.get("value")
        # fit_confidence is lifted to the top-level action field by _emit (it is
        # stripped before the wire alongside new_section). Read it here so the
        # per-placement score is observable in the real pipeline, not only in
        # unit tests. Exclude bool explicitly: True/False are int subclasses.
        fit_conf = a.get("fit_confidence")
        has_fit = isinstance(fit_conf, (int, float)) and not isinstance(fit_conf, bool)

        if a.get("new_section"):
            counts["new_section"] += 1
        elif not anchor_value:
            counts["unresolved"] += 1
        elif anchor_type == "heading":
            counts["heading"] += 1
            # tier1_confident: a heading anchor whose fit_confidence is a number.
            if has_fit:
                counts["tier1_confident"] += 1
                fit_values.append(round(float(fit_conf), 2))
        elif anchor_type == "callout":
            counts["callout"] += 1
        elif anchor_type == "line":
            counts["line"] += 1
        else:
            counts["unresolved"] += 1

    # Dedup paths preserving first-seen order: a MOC linked N times appears N
    # times in moc_paths, but the telemetry line should list each MOC once.
    unique_paths = list(dict.fromkeys(moc_paths))
    moc_count = len(unique_paths)
    moc_list = " ".join(unique_paths)
    print(
        f"[instruction-render] moc-insertion resolution — "
        f"heading={counts['heading']} "
        f"new_section={counts['new_section']} "
        f"callout={counts['callout']} "
        f"line={counts['line']} "
        f"unresolved={counts['unresolved']} "
        f"tier1_confident={counts['tier1_confident']} "
        f"mocs={moc_count}"
        + (f" fit_confidence=[{', '.join(f'{v:.2f}' for v in fit_values)}]" if fit_values else "")
        + (f" paths=[{moc_list}]" if moc_paths else ""),
        file=sys.stderr,
    )


def _merge_new_section_links(actions: list[dict]) -> int:
    """Merge link_to_moc actions targeting the same (target_moc, new_section)
    into ONE action, so two notes assigned the same new section produce a single
    heading with multiple bullets instead of duplicate `## <section>` headings (#70).

    Must run BEFORE _serialize_new_sections: at this point each action's
    line_to_add is still the bare "- [[Note]]" bullet, so merging is a simple
    newline-join of bullets. The first action of each group is kept and
    accumulates every member's bullet (emission order preserved); the rest are
    removed in place. Only groups with a truthy new_section are merged —
    anchor-based inserts (no new_section) are left untouched. A merged section
    spans multiple source notes, so source_note_title is cleared on the survivor.

    Returns the count of actions removed.
    """
    heads: dict[tuple[str, str], dict] = {}
    drop: set[int] = set()
    for idx, a in enumerate(actions):
        if a.get("action") != "link_to_moc":
            continue
        new_section = a.get("new_section")
        if not new_section:
            continue
        key = (_moc_stem(a.get("target_moc") or ""), new_section)
        head = heads.get(key)
        if head is None:
            heads[key] = a
            continue
        bullet = a.get("line_to_add", "")
        head_line = head.get("line_to_add", "")
        if bullet and bullet not in head_line.split("\n"):
            head["line_to_add"] = f"{head_line}\n{bullet}" if head_line else bullet
        head["source_note_title"] = None
        drop.add(idx)
    if drop:
        actions[:] = [a for i, a in enumerate(actions) if i not in drop]
    return len(drop)


def _rewrite_existing_section_anchors(actions: list[dict], client) -> int:
    """#73: when a link_to_moc carries a top-level new_section whose heading
    ALREADY exists in the target MOC, rewrite it to a heading anchor
    (placement=after) and drop new_section — so apply lands the bullet(s) under
    the existing section instead of creating a duplicate `## <name>` heading.

    Producer-side only (no Hashi change). Runs AFTER _merge_new_section_links
    (so a same-name group is already one multi-bullet action) and BEFORE
    _serialize_new_sections (while new_section is still a live top-level field
    and line_to_add is still the bare bullet block). Reads each distinct target
    MOC once; offline/None client → no-op. Matches heading names
    case-insensitively and anchors on the MOC's actual heading text.

    Returns the count of actions rewritten.
    """
    if client is None:
        return 0
    # target_moc_path → {casefolded heading text: actual heading text}
    heading_cache: dict[str, dict[str, str]] = {}

    def _existing_headings(path: str) -> dict[str, str]:
        if path in heading_cache:
            return heading_cache[path]
        try:
            result = client.read_note(path)
            content = result.get("content", "") or ""
        except Exception:  # noqa: BLE001
            heading_cache[path] = {}
            return heading_cache[path]
        inv = moc_structure.parse_moc_inventory(content, FOOTER_CALLOUTS, set())
        names = {h["text"].casefold(): h["text"] for h in inv["headings"]}
        heading_cache[path] = names
        return names

    rewritten = 0
    for a in actions:
        if a.get("action") != "link_to_moc":
            continue
        new_section = a.get("new_section")
        if not new_section:
            continue
        path = a.get("target_moc_path")
        if not path:
            continue
        actual = _existing_headings(path).get(new_section.casefold())
        if actual is None:
            continue
        a["anchor"] = {"type": "heading", "value": actual}
        a["placement"] = "after"
        a["new_section"] = None
        rewritten += 1
    return rewritten


def _strip_internal_link_fields(actions: list[dict]) -> int:
    """Remove Tomo-internal fields from link_to_moc AND move_note actions before the wire (#68/#64).

    move_note.audio_peer (spec 027) is Tomo-internal: _build_move_note_actions
    attaches it so _build_delete_source_actions can emit the paired audio
    delete_source; it is absent from Hashi's move_note schema
    (additionalProperties:false) and must be stripped here (see the move_note branch).
    new_section is baked into line_to_add by _serialize_new_sections and
    fit_confidence is consumed by telemetry; both are Tomo-internal and absent
    from Hashi's link_to_moc schema (additionalProperties:false). Leaving them on
    makes Hashi reject every MOC link (the un-discriminated oneOf falls through to
    move_note and reports a misleading "must have required property source").
    MUST run AFTER _serialize_new_sections and _emit_resolution_telemetry.

    Returns the count of fields removed.
    """
    stripped = 0
    for a in actions:
        kind = a.get("action")
        if kind == "move_note":
            # audio_peer is consumed by _build_delete_source_actions during the
            # render pass (spec 027 paired audio delete); it must never reach the
            # wire — Hashi's move_note schema is additionalProperties:false.
            if "audio_peer" in a:
                del a["audio_peer"]
                stripped += 1
            continue
        if kind != "link_to_moc":
            continue
        # unresolved_moc (spec 034 T6.0d) is the same kind of guard from the
        # other direction: filter_unresolvable_moc_links removes every action
        # carrying it before this runs, so a survivor here means that filter
        # was moved or removed — and the field must still not reach the wire.
        # alt_headings is a defense-in-depth guard: it does not reach the
        # action level today, but the Hashi anchor schema is
        # additionalProperties:false {type,value}, so if a future change ever
        # lifts alt_headings to the action level it must not reach the wire.
        for field in ("new_section", "fit_confidence", "alt_headings",
                      UNRESOLVED_MOC_FIELD):
            if field in a:
                del a[field]
                stripped += 1
    return stripped


def _serialize_new_sections(actions: list[dict]) -> int:
    """Build line_to_add from the top-level new_section field for every link_to_moc action.

    This is the SINGLE serialize site for new-section headings (ADR-3, spec 022
    T5.2). It runs AFTER resolve_section_names so it covers both:
      - Honored Pass-1 anchors (value already set → skipped by resolver).
      - Heuristic-resolved anchors: new_section is NOT set by the resolver;
        only Pass-1 LLM anchors produce a non-None top-level new_section field.

    Contract (AC-6): the serialized shape is exactly
        "## <section>\\n\\n<bullet>\\n"
    where <bullet> is the current line_to_add (the "- [[Note]]" line) and the
    trailing \\n ensures Hashi writes the blank-line gap between the new heading
    and whatever follows. Hashi writes line_to_add VERBATIM (hashi#65).

    Idempotency guard: if line_to_add already starts with "## ", the action is
    skipped to prevent double-prepending when the function is called more than
    once on the same action list.

    Returns the count of actions whose line_to_add was mutated.
    """
    mutated = 0
    for a in actions:
        if a.get("action") != "link_to_moc":
            continue
        # new_section is a TOP-LEVEL field on link_to_moc (instructions schema),
        # not nested inside anchor. Read from the action, not from anchor dict.
        new_section = a.get("new_section")
        if not new_section:
            continue
        # Collapse a (possibly hallucinated) multi-line LLM value to one line so
        # a single heading is written into the MOC, never two.
        new_section = new_section.split("\n", 1)[0].strip()
        if not new_section:
            continue
        bullet = a.get("line_to_add", "")
        if bullet.startswith("## "):
            continue  # idempotency guard
        a["line_to_add"] = f"## {new_section}\n\n{bullet}\n"
        mutated += 1
    return mutated


# Why a link_to_moc's `target_moc_path` stayed null (spec 034 T6.0d). Recorded
# at the point the answer is known and never reconstructed from the null: only
# MOC_ABSENT means the MOC does not exist. The other two mean nothing was
# learned about it this run, which is a different sentence to the user and a
# different outcome in the coverage audit.
MOC_ABSENT = "absent"              # Kado answered; no note by that name
MOC_UNCHECKED = "unchecked"        # no Kado client — nothing was asked
MOC_PROBE_FAILED = "probe-failed"  # the Kado call raised

# Tomo-internal marker carrying one of the three causes above. Stripped by
# filter_unresolvable_moc_links (every action carrying it is withheld) and
# again by _strip_internal_link_fields as defence in depth — Hashi's
# link_to_moc schema is additionalProperties:false.
UNRESOLVED_MOC_FIELD = "unresolved_moc"


def resolve_target_moc_paths(actions: list[dict], client) -> int:
    """Best-effort: resolve `target_moc_path` on link_to_moc actions.

    Two-tier resolution:
      1. In-set lookup — if the target_moc matches a `create_moc` action in
         THIS instruction set, use its `destination` directly. The MOC doesn't
         exist in the vault yet, so Kado can't find it; but we know where it
         WILL be after Tomo Hashi applies I01.
      2. Kado `search_by_name` — for MOCs that already exist in the vault.

    Actions that can't be resolved by either route keep their
    `target_moc_path: null` and are stamped with `UNRESOLVED_MOC_FIELD`
    carrying WHY, for `filter_unresolvable_moc_links` to act on. The cause is
    recorded here because here is the only place it is known: a bare null
    downstream cannot tell "Kado said no" from "Kado was never asked", and
    treating those alike tells an offline run's user that every MOC in their
    vault has vanished.

    Returns the number of resolutions populated.
    """
    # Tier 1 — index create_moc actions by stem of their title so we can
    # resolve links that target a new MOC in the same instruction set.
    # Keyed by the EXACT stem, deliberately (spec 034 T6.0). This is a second
    # paired consumer of `_build_create_moc_actions`' `by_dest` and folding it
    # was tried and reverted: two create_moc surviving that fold in DIFFERENT
    # folders collide on one folded key, and last-write-wins then redirects one
    # MOC's bullets to the other's destination. Redirecting an action is a
    # behaviour change, not an addressing fix. The cost of leaving it exact is
    # recorded in docs/tomo/scripts/lib/render_actions.md.
    in_set: dict[str, str] = {}
    for a in actions:
        if a.get("action") == "create_moc":
            title = a.get("title") or ""
            dest = a.get("destination")
            if title and dest:
                in_set[_moc_stem(title)] = dest

    # (path, cause) per unique stem. The cause is cached alongside the path so
    # a repeated target reports the same reason as its first lookup rather
    # than a reconstructed one.
    cache: dict[str, tuple[str | None, str | None]] = {}

    def _resolve(stem: str) -> tuple[str | None, str | None]:
        if stem in cache:
            return cache[stem]
        # Tier 1: in-set create_moc lookup (no Kado call, no I/O)
        if stem in in_set:
            cache[stem] = (in_set[stem], None)
            return cache[stem]
        # Tier 2: Kado byName search, cached per unique stem
        if client is None:
            cache[stem] = (None, MOC_UNCHECKED)
            return cache[stem]
        try:
            hits = client.search_by_name(stem)
        except Exception:  # noqa: BLE001
            cache[stem] = (None, MOC_PROBE_FAILED)
            return cache[stem]
        if not hits:
            cache[stem] = (None, MOC_ABSENT)
            return cache[stem]
        # Prefer a hit whose filename stem matches exactly (not a substring).
        exact = [h for h in hits if _stem(h.get("path", "")) == stem]
        chosen = (exact or hits)[0]
        path = chosen.get("path") or None
        # A hit with no usable path is Kado answering without saying where —
        # not a confirmed absence.
        cache[stem] = (path, None if path else MOC_PROBE_FAILED)
        return cache[stem]

    resolved = 0
    for a in actions:
        if a.get("action") != "link_to_moc":
            continue
        target = a.get("target_moc")
        if not target:
            continue
        path, cause = _resolve(_moc_stem(target))
        if path:
            a["target_moc_path"] = path
            # Idempotency: a second call over the same list must not leave a
            # stale cause behind on an action that now resolves.
            a.pop(UNRESOLVED_MOC_FIELD, None)
            resolved += 1
        elif cause:
            a[UNRESOLVED_MOC_FIELD] = cause
    return resolved


def filter_unresolvable_moc_links(
    actions: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Drop link_to_moc actions whose target MOC the run could not confirm.

    A null `target_moc_path` is a legal schema value, so such an action used to
    pass validation, the dryrun and the coverage audit and reach the user as an
    ordinary `- [ ] Applied` checkbox telling them to open a MOC that will
    never exist. Under CON-2 the user approves on what this document says, so
    the action is withheld and reported instead.

    Pure function over the marker `resolve_target_moc_paths` stamped — the same
    shape as `filter_unappliable_relationships` over `add_relationship.error`,
    and for the same reason: the cause is known at emission and nowhere else.

    `add_relationship` never needed this because its null is rejected by
    Hashi's wire schema outright; `link_to_moc` escapes that only because its
    `target_moc_path` is typed `["string","null"]` and not required. One kind
    was defended, its sibling was not.

    Returns (kept, skipped). Non-link_to_moc actions are always kept. The
    marker is left on the skipped actions — the caller projects it into the
    report — and never survives on a kept one.
    """
    kept: list[dict] = []
    skipped: list[dict] = []
    for a in actions:
        if a.get("action") == "link_to_moc" and a.get(UNRESOLVED_MOC_FIELD):
            skipped.append(a)
        else:
            kept.append(a)
    return kept, skipped


def unresolvable_link_reports(skipped: list[dict]) -> list[dict]:
    """Project withheld link_to_moc actions to metadata-only report records.

    Constitution L2: ids, the MOC stem, the source note's title and the cause
    discriminator — never note content or the bullet text. `cause` is the
    stable discriminator renderers and the audit branch on; the prose that
    explains it belongs to whoever renders it.
    """
    return [
        {
            "id": a.get("id"),
            "target_moc": a.get("target_moc"),
            "source_note_title": a.get("source_note_title"),
            "cause": a.get(UNRESOLVED_MOC_FIELD),
        }
        for a in skipped
    ]


# Daily-note-targeting actions modify (never create) their daily note.
DAILY_NOTE_ACTIONS = {"update_tracker", "update_log_entry", "update_log_link"}


def filter_missing_daily_notes(
    actions: list[dict], client,
) -> tuple[list[dict], list[dict]]:
    """Drop daily-note actions whose target daily note does not exist (#37/I38).

    update_tracker / update_log_entry / update_log_link MODIFY an existing daily
    note. Hashi only modifies — it cannot create a daily note (unlike create_moc
    / move_note, which create their targets). When the target is absent (e.g. a
    log entry dated to a historical day the user never opened), the action is
    unappliable, so skip it here instead of emitting an instruction Hashi must
    fail on. Skipped actions are surfaced (stderr + the instructions.md
    "Skipped" section) so the user can create the daily note and re-run.

    Returns (kept, skipped). Non-daily actions are always kept. Fail-open: if
    `client` is None (offline/test) or a Kado read fails for any reason other
    than a definitive not-found, the action is kept — never drop on a transient
    error.
    """
    if client is None:
        return actions, []
    exists_cache: dict[str, bool] = {}

    def _exists(path: str) -> bool:
        if path in exists_cache:
            return exists_cache[path]
        ok = True  # fail-open default
        try:
            # Cheap existence probe (1-char partial read) — body unused.
            ok = client.note_exists(path)
        except Exception:  # noqa: BLE001 — transient/other error: keep the action
            ok = True
        exists_cache[path] = ok
        return ok

    kept: list[dict] = []
    skipped: list[dict] = []
    for a in actions:
        path = a.get("daily_note_path")
        if a.get("action") in DAILY_NOTE_ACTIONS and path and not _exists(path):
            skipped.append(a)
            continue
        kept.append(a)
    return kept, skipped


def filter_missing_source_notes(
    confirmed: list[dict], client, inbox_path: str,
) -> tuple[list[dict], list[dict]]:
    """Drop confirmed items whose source note no longer exists (#116).

    An item that carries both a `template` and a `source_path` renders a new
    note FROM that source. If the source note is gone (e.g. a stale suggestion
    re-processed after the source was deleted or already moved), reading it
    fail-opens to an empty body and the renderer would fabricate an empty stub
    note. Worse, the item stays in `confirmed`, so build_actions would still
    emit a link_to_moc pointing at a note that was never created.

    Dropping the whole item here — before the render loop and before
    build_actions — keeps every downstream action (move_note, link_to_moc,
    delete_source) consistent: none reference the missing source.

    Items without a `template` (instruction-only: link_to_moc, update_daily) or
    without a `source_path` (synthesized MOC proposals) are always kept — this
    filter targets note-fabrication only.

    The item is addressed by `item_key` — its vault-relative path, verbatim
    (spec 034 ADR-1). Only when no key is present does it fall back to the
    inbox-root reconstruction, which is correct for a document produced before
    recursive discovery and a guess for anything after it.

    Three outcomes, not two. A Kado failure used to be treated as "exists",
    which KEPT the item — it then read an empty body downstream and fabricated
    exactly the stub #116 exists to prevent. An unverifiable source is
    therefore no longer rendered either; the source note stays untouched in the
    inbox and is re-proposed on the next run, which is recoverable, whereas a
    fabricated stub is not. `client is None` is a different case — no check was
    requested at all — and still keeps everything.

    Returns (kept_items, drop_reports). A drop report is metadata only
    (Constitution L2): `id`, `title`, `source_path`, `item_key`, the
    `probed_path` actually asked about, and a `reason`. It carries no note
    content, and it is a report — not the item — because the caller's job with
    it is to tell the user what happened, not to re-render it.
    """
    if client is None:
        return confirmed, []
    exists_cache: dict[str, bool | None] = {}

    def _exists(path: str) -> bool | None:
        """True/False on a definitive answer, None when Kado could not say."""
        if path in exists_cache:
            return exists_cache[path]
        try:
            # bool(), not the raw return: the tri-state distinguishes "the
            # client answered" from "the client could not", so a truthy answer
            # from a duck-typed client must read as a yes, not as a non-answer.
            ok: bool | None = bool(client.note_exists(path))
        except Exception:  # noqa: BLE001 — transport/validation: not a verdict
            ok = None
        exists_cache[path] = ok
        return ok

    kept: list[dict] = []
    dropped: list[dict] = []
    for item in confirmed:
        source_path = item.get("source_path", "")
        if item.get("template") and source_path:
            item_key = item.get("item_key")
            full_path = resolve_source_path(item_key, source_path, inbox_path)
            if not full_path.endswith(".md"):
                full_path += ".md"
            verdict = _exists(full_path)
            if verdict is not True:
                dropped.append({
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "source_path": source_path,
                    "item_key": item_key or "",
                    "probed_path": full_path,
                    # `kind` is the stable discriminator renderers branch on;
                    # `reason` is prose for a human and must never be parsed.
                    "kind": "not-found" if verdict is False else "unverifiable",
                    "reason": (
                        "no note at this path"
                        if verdict is False
                        else "Kado could not confirm this path"
                    ),
                })
                continue
        kept.append(item)
    return kept, dropped


def filter_unappliable_relationships(
    actions: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Drop add_relationship actions that carry a truthy `error` key.

    emit_up_preservation_actions sets error='child-missing' or
    error='non-markdown-asset' on un-appliable sentinels (applied=False).
    Hashi's wire schema has additionalProperties:false and no `error` field, so
    a single error-bearing action causes Hashi to reject the entire instruction
    set. This filter intercepts them before serialisation.

    Pure function — no Kado call needed; the `error` marker is set at emission.
    Returns (kept, skipped). Non-add_relationship actions are always kept.
    Skipped items are surfaced to the user via stderr and the instructions.md
    Skipped section (same pattern as filter_missing_daily_notes).
    """
    kept: list[dict] = []
    skipped: list[dict] = []
    for a in actions:
        if a.get("action") == "add_relationship" and a.get("error"):
            skipped.append(a)
        else:
            kept.append(a)
    return kept, skipped


