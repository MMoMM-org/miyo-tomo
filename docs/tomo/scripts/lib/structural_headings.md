# WHY: lib/structural_headings.py

> Rationale for `tomo/scripts/lib/structural_headings.py`.
> The module is the single source of truth for the #71 structural-heading list
> (spec 023 ADR-6). Pure data + two tiny helpers, no IO.

## Why this list exists as a shared module and not two literals (#71, spec 023 ADR-6)

WHY: Spec 023's insertion-point confidence gate is a *pure LLM instruction* — the
`fit_confidence >= 0.6` comparison lives only in `inbox-analyst.md`, no Python
enforces it. A live run (2026-06-17, "Asakusa Senso-ji") showed the failure mode
this leaves uncovered: the LLM scored the structural heading "Content" at ≥0.6 —
contradicting its OWN guidance that "Content" is ~0.3 scaffolding — and the note
landed under `## Content`, the exact anti-pattern 023 targets. An LLM compliance
slip has no floor when nothing deterministic backstops it.

ADR-6 adds that floor: `suggestions-reducer.demote_structural_anchors` demotes any
tier-1 heading anchor whose heading is in `DEFAULT_STRUCTURAL_HEADINGS` to a tier-2
new-section anchor, regardless of the LLM score. The offline tuning aid
`scripts/analyze-placement-confidence.py` already carried the same list to *flag*
gate-slips after a run. Two copies of a security-relevant list drift; when they
drift, the tuning aid stops reporting on exactly the headings the runtime stopped
demoting (or vice-versa). Hoisting the list into one importable module makes drift
impossible — the runtime backstop and the diagnostic read the same bytes.

## Why the runtime lib is the SSoT home (not the host tool)

WHY: The list must be importable from BOTH sides. The runtime reducer lives in
`tomo/scripts/` (synced into a Tomo instance); the tuning aid lives in `scripts/`
(host-only, never synced). A host-only home would be invisible to the instance
runtime. So the SSoT lives in `tomo/scripts/lib/` (in the synced tree) and the host
tool reaches into it via a `sys.path` insert. The runtime never reaches outward into
host-only `scripts/`, preserving the container-visibility boundary.

## Why demote-only, and why a name list is acceptable here

WHY: Spec 023 (ADR-1) deliberately rejected a structural-heading blocklist because a
name-based rule does not generalize across the open-ended space of heading names —
confidence does. ADR-6 does not reopen that: confidence stays the PRIMARY tier-1/tier-2
decision. This list is a bounded safety net for the small, closed set of *known template
scaffolding* headings, where a name rule DOES generalize (they are structural by
definition, never a topical home). The backstop only ever demotes a known-bad slip; it
never promotes. Profile-configurability is deferred (same category as the
`FOOTER_CALLOUTS` F-55 TODO in `render_resolve.py`).
