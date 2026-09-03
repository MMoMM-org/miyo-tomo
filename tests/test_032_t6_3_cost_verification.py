#!/usr/bin/env python3
# version: 1.0.0
"""test_032_t6_3_cost_verification.py — Phase 6 T6.3 (spec 032).

CON-3: "The design's central claim is that this costs nothing at audit time."
The audit must issue the same number of Kado calls before and after this
change, and that count must not vary with the number of property-resident
(frontmatter-declared) broken_up findings.

Why the honest test is structural, not a bare ``calls == 0`` count (the
eighth-hollow-test trap named in this task's brief — a negative assertion
with no fixture that would ever produce a nonzero count proves nothing):

  garden-audit.py's ``_check_broken_up(entries, exclusions, counter)`` takes
  NO ``graph_audit_fn`` / ``list_dir_fn`` parameter at all (contrast
  ``_check_orphan(graph_result, entries, exclusions, counter)`` and
  ``_check_dead_link(graph_result, entries, exclusions, counter)``, which
  both take a pre-computed ``graph_result``, and ``_check_stale_moc(entries,
  list_dir_fn, exclusions, counter, ...)``, which takes ``list_dir_fn``
  directly). It is not merely undocumented as cache-only — it structurally
  CANNOT reach Kado, because run_scan() never hands it a callable capable of
  doing so. And ``up_value`` reaches the cache from content already read at
  moc-tree-builder.py:410, where ``parse_up_from_content`` was already being
  called before this spec — so populating it added no new read either.

This file proves the structural property two ways, either of which would
FAIL if a future change broke it:

  1. Signature shape: ``_check_broken_up``'s parameter set is exactly
     ``{entries, exclusions, counter}`` — no callable parameter a future
     change could route a Kado call through. This alone would catch someone
     ADDING a ``graph_audit_fn=`` parameter to the check, even before they
     wired a call through it.
  2. Behavioural, both within the current module AND against the true
     pre-032 baseline (781aaf2, loaded via ``git show`` — same technique as
     T6.2): run_scan()'s ONLY two Kado entry points are ``graph_audit_fn``
     (called exactly once, unconditionally, for orphan+dead_link — see
     garden-audit.py:452) and ``list_dir_fn`` (called at most once, for
     stale_moc — garden-audit.py:341, ``_check_stale_moc``, single
     ``list_dir_fn(path="/")`` fetch filtered client-side, never per-MOC).
     Neither call site depends on ``entries``' broken_up content in any way.
     Wrapping both with call-counting spies and running run_scan() with
     ZERO, a HANDFUL, and MANY property-resident broken_up findings (same
     MOC set held constant across all three, so list_dir_fn's call is
     forced to fire in every run) proves the counts are identical across all
     three scenarios AND identical between the pre-032 module and the
     current one. This WOULD fail if a future change added a Kado call
     anywhere reachable from broken_up processing — the counts would then
     diverge between the zero-broken and many-broken runs, or between old
     and new.
"""
from __future__ import annotations

import importlib.util
import inspect
import pathlib
import subprocess
import sys
import tempfile

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS_DIR = _ROOT / "tomo" / "scripts"
_GARDEN_AUDIT_PATH = _SCRIPTS_DIR / "garden-audit.py"

sys.path.insert(0, str(_SCRIPTS_DIR))

_PRE_032_SHA = "781aaf2"  # last commit before this branch's first code change (995e35a)


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_from_git(name: str, sha: str, repo_relative_path: str):
    """Load ``sha:repo_relative_path`` as a module under a distinct ``name``.

    Written to a fresh tempfile under $TMPDIR — never touches the working
    tree.
    """
    content = subprocess.run(
        ["git", "show", f"{sha}:{repo_relative_path}"],
        cwd=_ROOT, capture_output=True, check=True, text=True,
    ).stdout
    with tempfile.TemporaryDirectory() as td:
        old_path = pathlib.Path(td) / f"{name}.py"
        old_path.write_text(content, encoding="utf-8")
        spec = importlib.util.spec_from_file_location(name, old_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    mod._t63_source_version_line = content.splitlines()[1]
    return mod


new_ga = _load("garden_audit_t63_new", _GARDEN_AUDIT_PATH)
old_ga = _load_from_git("garden_audit_t63_old", _PRE_032_SHA, "tomo/scripts/garden-audit.py")

# Sanity: really two distinct modules from two distinct sources (guards
# against the "loaded the new module twice" trap).
assert old_ga is not new_ga
assert old_ga.__file__ != new_ga.__file__
assert old_ga._t63_source_version_line == "# version: 0.4.0"
_new_ga_version_line = _GARDEN_AUDIT_PATH.read_text(encoding="utf-8").splitlines()[1]
assert _new_ga_version_line != old_ga._t63_source_version_line


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _moc(stem: str) -> dict:
    return {
        "path": f"Maps/{stem}.md", "stem": stem, "kind": "moc", "title": stem,
        "up_state": "valid", "up_target": None, "topics": [], "tags": [],
    }


def _broken_inline(stem: str) -> dict:
    return {
        "path": f"Notes/{stem}.md", "stem": stem, "kind": "note", "title": stem,
        "up_state": "broken", "up_target": "Deleted MOC",
        "up_source": "inline", "up_value": None,
        "topics": [], "tags": [],
    }


def _broken_frontmatter(stem: str, n: int) -> dict:
    """A property-resident (frontmatter-declared) broken finding — the case
    CON-3 explicitly calls out ("does not vary with the number of
    property-resident findings"). up_value varies (scalar vs list) across
    entries so the fixture isn't accidentally uniform.
    """
    up_value = ["[[Deleted MOC]]", "[[Sibling MOC]]"] if n % 2 == 0 else "[[Deleted MOC]]"
    return {
        "path": f"Notes/PropBroken{n}.md", "stem": stem, "kind": "note", "title": stem,
        "up_state": "broken", "up_target": "Deleted MOC",
        "up_source": "frontmatter", "up_value": up_value,
        "topics": [], "tags": [],
    }


class _CountingFn:
    """A callable that counts its own invocations."""

    def __init__(self, return_value):
        self.calls = 0
        self._return_value = return_value

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return self._return_value


def _run_scan_with_spies(module, entries):
    graph_spy = _CountingFn({"orphans": [], "deadLinks": [], "total": {}})
    list_dir_spy = _CountingFn([])
    doc = module.run_scan(entries, graph_audit_fn=graph_spy, list_dir_fn=list_dir_spy)
    return doc, graph_spy.calls, list_dir_spy.calls


# One MOC entry held constant across every scenario below — its mere
# presence is what forces _check_stale_moc to call list_dir_fn exactly once
# (garden-audit.py:335-341, moc_paths non-empty -> single list_dir_fn(path="/")
# fetch); broken_up findings have no bearing on that call at all.
_BASE_MOCS = [_moc("PKM")]


# ---------------------------------------------------------------------------
# 1. Signature shape — no Kado-callable parameter exists to route a call
#    through.
# ---------------------------------------------------------------------------

class TestCheckBrokenUpSignatureHasNoKadoParameter:
    def test_new_signature_is_cache_only(self):
        params = list(inspect.signature(new_ga._check_broken_up).parameters)
        assert params == ["entries", "exclusions", "counter"]

    def test_old_signature_was_already_cache_only(self):
        # Not a regression opportunity spec 032 introduced — it was cache-only
        # before this spec too. Documents the invariant CON-3 relies on
        # existed pre-032, not something this spec had to newly establish.
        params = list(inspect.signature(old_ga._check_broken_up).parameters)
        assert params == ["entries", "exclusions", "counter"]


# ---------------------------------------------------------------------------
# 2. Behavioural: call counts don't scale with broken_up volume or
#    property-residency, in EITHER module version.
# ---------------------------------------------------------------------------

class TestCallCountsDoNotVaryWithBrokenUpFindings:
    def _scenarios(self, module):
        zero_entries = list(_BASE_MOCS)
        handful_entries = list(_BASE_MOCS) + [
            _broken_frontmatter(f"Prop{i}", i) for i in range(3)
        ]
        many_entries = list(_BASE_MOCS) + [
            _broken_frontmatter(f"Prop{i}", i) for i in range(40)
        ] + [_broken_inline(f"Inline{i}") for i in range(10)]

        results = {}
        for label, entries in (
            ("zero", zero_entries), ("handful", handful_entries), ("many", many_entries),
        ):
            doc, graph_calls, list_dir_calls = _run_scan_with_spies(module, entries)
            broken_findings = [f for f in doc["findings"] if f["check"] == "broken_up"]
            results[label] = (graph_calls, list_dir_calls, len(broken_findings))
        return results

    def test_new_module_call_counts_constant_across_broken_up_volume(self):
        results = self._scenarios(new_ga)
        # Sanity: the scenarios really do differ in broken_up findings
        # produced — otherwise this proves nothing about scaling.
        assert results["zero"][2] == 0
        assert results["handful"][2] == 3
        assert results["many"][2] == 50

        # The actual CON-3 claim: Kado call counts hold constant regardless.
        graph_counts = {label: v[0] for label, v in results.items()}
        list_dir_counts = {label: v[1] for label, v in results.items()}
        assert graph_counts == {"zero": 1, "handful": 1, "many": 1}
        assert list_dir_counts == {"zero": 1, "handful": 1, "many": 1}

    def test_old_module_call_counts_constant_across_broken_up_volume(self):
        # Same proof against the pre-032 module — establishes the baseline
        # this spec must not have moved.
        results = self._scenarios(old_ga)
        assert results["zero"][2] == 0
        assert results["handful"][2] == 3
        assert results["many"][2] == 50

        graph_counts = {label: v[0] for label, v in results.items()}
        list_dir_counts = {label: v[1] for label, v in results.items()}
        assert graph_counts == {"zero": 1, "handful": 1, "many": 1}
        assert list_dir_counts == {"zero": 1, "handful": 1, "many": 1}

    def test_call_counts_identical_old_vs_new_for_every_scenario(self):
        # THE literal CON-3 assertion: "the audit issues the same number of
        # Kado calls before and after this change" — compared directly,
        # scenario by scenario, old module vs new.
        old_results = self._scenarios(old_ga)
        new_results = self._scenarios(new_ga)
        for label in ("zero", "handful", "many"):
            old_graph, old_list_dir, _ = old_results[label]
            new_graph, new_list_dir, _ = new_results[label]
            assert (new_graph, new_list_dir) == (old_graph, old_list_dir), (
                f"scenario={label!r}: old=({old_graph},{old_list_dir}) "
                f"new=({new_graph},{new_list_dir})"
            )


# ---------------------------------------------------------------------------
# 3. CON-5: the broken_up check specifically triggers no graph_audit, proven
#    with ONLY broken_up findings present (no orphan/dead_link/stale_moc
#    entries to accidentally cover for a missing call elsewhere).
# ---------------------------------------------------------------------------

class TestBrokenUpAloneTriggersNoGraphAudit:
    def test_broken_up_only_fixture_still_calls_graph_audit_exactly_once(self):
        # graph_audit_fn is called unconditionally by run_scan for
        # orphan+dead_link (garden-audit.py:452) regardless of what
        # broken_up produces — the assertion is that adding many broken_up
        # (including property-resident) findings does not add a SECOND call
        # on top of that unconditional one.
        entries = [_broken_frontmatter(f"Prop{i}", i) for i in range(20)]
        _, graph_calls, list_dir_calls = _run_scan_with_spies(new_ga, entries)
        assert graph_calls == 1
        # No MOC entries in this fixture -> _check_stale_moc's moc_paths is
        # empty -> list_dir_fn is never called at all (garden-audit.py:335-336).
        assert list_dir_calls == 0
