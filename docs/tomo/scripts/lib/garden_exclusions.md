# WHY: lib/garden_exclusions.py

> Rationale for decisions in `tomo/scripts/lib/garden_exclusions.py`.
> The module loads and indexes the `config/garden-audit-exclusions.yaml` exclusion
> config produced by the garden-auditor wizard. It exposes `GardenExclusions`, a
> two-method class: `is_excluded(entry, check_name)` and `reappeared_exclusions()`.

## Fail-Open on Missing or Malformed Config (CON-5 / SDD Error Handling)

WHY `GardenExclusions.from_path` returns an empty instance (nothing excluded) rather
than raising when the config file is missing or unparseable: the audit skill must
produce findings on a first run before the exclusion wizard has written any config.
Raising on missing config would block every first run. Raising on a malformed YAML
would make one user-authored typo abort the entire scan. The fail-open posture is
consistent with the "graceful partial" pattern used across the garden-audit pipeline
(scan degrades when graph_audit is unavailable; render does not crash on empty findings).
The rule `_parse_rule` returns `None` on invalid entries; `from_dict` skips Nones and
logs at DEBUG — a malformed entry is silently dropped, not a fatal error.

## Active/Expired Split at Construction Time

WHY `GardenExclusions.__init__` pre-partitions rules into `_active` and `_reappeared`
at construction time rather than evaluating `is_active` on every `is_excluded` call:
the audit runs on a single date — the construction date — and the active/expired
boundary does not change mid-scan. Pre-partitioning means `is_excluded` iterates only
over active rules (typically a small list), not all rules including expired ones.
`reappeared_exclusions` is a cheap list copy of what was already separated. The only
exception is the `today` parameter on `is_excluded` itself, which is provided for
test pinning when the caller constructs without a date override; in that case
`is_active` is re-evaluated inline. In production, the construction-time split is
always sufficient.

## "checks: all" Expansion at Parse Time, Not Match Time

WHY `_normalize_checks` expands the string `"all"` to the frozen set of ALL check
names when the rule is parsed, rather than treating `"all"` as a sentinel matched at
`is_excluded` time: expanding at parse time means `is_excluded` only needs `check_name
in rule.checks` (a frozenset membership test — O(1)). Keeping `"all"` as a sentinel
would require a `rule.checks == "all" or check_name in rule.checks` branch on every
call. The expansion also future-proofs: if a new check name is added, rules with
`checks: all` in config automatically cover it (because `ALL_CHECK_NAMES` is the source
of truth), without the user needing to edit their exclusion YAML.

## Three Target Types — path Prefix, note Exact, tag Membership

WHY `_matches_target` provides three distinct target types rather than a single regex
or glob match:

- `path` prefix match covers the dominant use case (exclude a whole folder such as
  `Calendar/`). Prefix matching is O(len(prefix)) and unambiguous — it catches
  subdirectories automatically without the user writing `Calendar/**`.
- `note` exact match allows excluding a single note by path when only that specific
  file should be suppressed (e.g. a known-temporary workaround file).
- `tag` membership allows excluding notes by frontmatter tag (e.g. all notes tagged
  `status/draft`). This is read from `entry["tags"]` which the MOC-structure cache
  provides.

A regex option was considered and rejected: regexes require user expertise to author
correctly, are prone to escaping errors, and make the config harder to audit visually.
The three typed matchers cover all wizard-generated exclusion patterns without regex.

## Temporary Exclusions Report Reappearance (Wizard Feedback Loop)

WHY expired-temporary exclusions are surfaced in `reappeared_exclusions()` rather than
silently ignored: a temporary exclusion (e.g. "push back Calendar/ for 90 days while
reorganising") reaches its `until` date and should not simply vanish — the user needs
to decide whether to renew it, make it permanent, or act on the now-reappearing
findings. `reappeared_exclusions()` feeds `garden-audit-render._render_preamble`, which
surfaces them at the top of the report as a prompt to review. The raw dict (not the
parsed rule) is stored in `_reappeared` so the render has access to the original `until`
date and `target` without reconstructing it from the `_ExclusionRule`.

## Version 0.1.1

WHY: Bumped from 0.1.0 (initial spec-030 T1.2) for the `today` parameter thread-through
fix on `from_path` → `from_dict` → `__init__` (C1: both factory calls must share the same
resolved date to avoid active/expired split inconsistency at test-boundary dates).
`update-tomo.sh` skips unchanged versions.
