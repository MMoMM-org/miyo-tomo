# WHY: scripts/lib/profile_conventions.py

> Rationale for decisions in `tomo/scripts/lib/profile_conventions.py`.
> The lib is the single resolver for profile-agnostic vault conventions
> (spec 028, F-16 markers + F-55 MOC suffix): it turns the active profile's
> `relationship_defaults.*.marker` and `concept_defaults.map_note.name_suffix`
> into one immutable `Conventions(parent_marker, peer_marker, moc_suffix)`
> value object that pipeline scripts thread into the pure libs.

## WHY a `Conventions` resolver at all

Before spec 028 the strings `up::`, `related::`, and `" (MOC)"` were hardcoded
across ~10 seams in the pipeline (read regexes, write literals, title
suffixing, placeholder-MOC detection). That made the pipeline silently
`miyo`-only: any profile whose vault uses different relationship markers or no
MOC-title suffix (e.g. `lyt`) would have produced wrong parses and wrong
titles. The resolver replaces those scattered literals with one DI-friendly
value object (Constitution L2 dedup); profiles stay pure data (Constitution:
profiles carry no logic) and this lib carries no vault literals of its own
beyond the documented ADR-3 defaults.

## WHY per-script resolution (ADR-1), NOT a shared-ctx channel

Each script resolves its own `Conventions` at its entry point from the input it
already has (`--config` → profile name, or an already-loaded `profile_dict`, or
an explicit `--profile`). The rejected alternative was to broadcast the markers
through `shared-ctx.json`. That artifact is LLM-facing and is loaded by exactly
one Python consumer (the reducer, for field→section maps); adding markers there
would serve no Python consumer → YAGNI. Per-script resolution also matches how
`moc-discovery` already resolves the profile, so the pattern is uniform.
`suggestion-parser` is the one script with no config access — it receives the
conventions via the additive `conventions` block the reducer writes into
`suggestions-doc.json` (its existing input), not through this lib directly.

## WHY `profiles_dir` is caller-supplied and REQUIRED (ADR-2 / CON-4)

The resolver never derives the profiles directory from its own `__file__`. The
flattened instance runtime breaks deep `SCRIPT_DIR.parent.parent`-style path
resolution (`[[reference_instance_layout_breaks_script_default_paths]]`), so
every caller passes `profiles_dir` from its own already-working `SCRIPT_DIR`
(the `DEFAULT_PROFILES_DIR = SCRIPT_DIR.parent / "profiles"` constant, copied
verbatim from `moc-discovery`). Making the argument required — not defaulted —
forces each caller to own the path that actually works in its runtime.

## WHY the suffix-null guard (ADR-3)

`map_note.name_suffix` is read with an explicit `None` check
(`_DEFAULT_MOC_SUFFIX if _raw_suffix is None else _raw_suffix`) rather than
`or`. A profile that legitimately sets `name_suffix: ""` (lyt — plain MOC
titles) must keep the empty string, not fall back to the default. Using `or`
would coerce `""` to the default and silently re-introduce a suffix the vault
does not use. Markers use `or` because an empty marker is never a valid
convention, only a missing one → falling back to `up::`/`related::` is correct.
Absent keys default to `up::` / `related::` / `""` so a profile that omits them
gets today's behaviour without crashing (backward compatibility).

## WHY `marker_word` lives here

`marker_word(" (MOC)") → "MOC"` extracts the alphanumeric core of a suffix. Two
MOC-marker regexes (`lib.topic_clusters`, `shared-ctx-builder`) need it; homing
it in the resolver keeps the two from drifting (F-55 S1) and keeps the derivation
next to the suffix it is derived from.
