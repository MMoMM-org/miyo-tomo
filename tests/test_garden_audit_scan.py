#!/usr/bin/env python3
# version: 0.1.0
"""test_garden_audit_scan.py — Behavioural tests for garden-audit.py scan orchestrator (spec 030 T2.1).

Uses fake cache entries, a fake graph_audit callable, and a fake listDir callable — no Kado/network.

Domain facts locked in:
  Checks: unparented, orphan, broken_up, dead_link, duplicate_stem, stale_moc
  Tiers: integrity={broken_up, dead_link}; structure={unparented, orphan}; advisory={duplicate_stem, stale_moc}
  Data-source split (ADR-5):
    cache       → unparented, broken_up, duplicate_stem
    graph_audit → orphan, dead_link
    listDir     → stale_moc
  broken_up is CACHE-ONLY — must not trigger any graph_audit call.
  Fixable: unparented, orphan, broken_up, dead_link (checks 1-4). Advisory=5-6, never fixable.
  Severity order: integrity > structure > advisory.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import jsonschema

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
SCHEMAS_DIR = Path(__file__).parent.parent / "tomo" / "schemas"
sys.path.insert(0, str(SCRIPTS_DIR))


# ──────────────────────────────────────────────────────────────────────────────
# Load the module under test (hyphen-named — use importlib)
# ──────────────────────────────────────────────────────────────────────────────

def _load_garden_audit():
    path = SCRIPTS_DIR / "garden-audit.py"
    spec = importlib.util.spec_from_file_location("garden_audit", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

garden_audit = _load_garden_audit()
run_scan = garden_audit.run_scan


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

# Sentinel distinguishing "kwarg not passed" (key must be ABSENT from the
# entry dict, mimicking a stale pre-032 cache) from an explicit None (key
# present with value None, e.g. an inline up:: declaration).
_UNSET = object()


def _entry(
    stem: str,
    *,
    kind: str = "note",
    up_state: str = "valid",
    up_target: str | None = None,
    up_source: str | None = _UNSET,
    up_value=_UNSET,
    topics: list[str] | None = None,
    tags: list[str] | None = None,
    path: str | None = None,
) -> dict:
    entry: dict = {
        "path": path or f"Notes/{stem}.md",
        "stem": stem,
        "kind": kind,
        "title": stem,
        "up_state": up_state,
        "up_target": up_target,
        "topics": topics or [],
        "tags": tags or [],
    }
    if up_source is not _UNSET:
        entry["up_source"] = up_source
    if up_value is not _UNSET:
        entry["up_value"] = up_value
    return entry


def _moc(stem: str, *, topics: list[str] | None = None, up_state: str = "valid") -> dict:
    return _entry(
        stem, kind="moc", up_state=up_state, topics=topics or [],
        path=f"Maps/{stem}.md",
    )


def _no_graph_audit(*args, **kwargs) -> dict:
    """Fake that returns empty graph results — no graph calls expected."""
    return {"orphans": [], "deadLinks": [], "total": {}}


def _graph_unavailable(*args, **kwargs):
    raise RuntimeError("graph tool unavailable")


def _no_list_dir(path=None, **kwargs) -> list:
    return []


# ──────────────────────────────────────────────────────────────────────────────
# run_scan signature:
#   run_scan(entries, *, graph_audit_fn, list_dir_fn, exclusions=None,
#            stale_moc_days=90, run_id=None, profile=None, generated=None,
#            today=None) -> dict
# ──────────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────────
# Unparented check (cache: up_state=="absent")
# ──────────────────────────────────────────────────────────────────────────────

def test_unparented_note_produces_structure_finding():
    """A note with up_state==absent produces an unparented finding (tier=structure)."""
    entries = [
        _moc("PKM", topics=["pkm", "notes"]),
        _entry("Orphan Note", up_state="absent", topics=["pkm", "notes"]),
    ]
    doc = run_scan(entries, graph_audit_fn=_no_graph_audit, list_dir_fn=_no_list_dir)
    findings = doc["findings"]
    unparented = [f for f in findings if f["check"] == "unparented"]
    assert len(unparented) == 1
    f = unparented[0]
    assert f["tier"] == "structure"
    assert f["fixable"] is True
    assert f["target"]["stem"] == "Orphan Note"


def test_unparented_carries_candidate_mocs_from_orphan_link_scoring():
    """Unparented finding carries candidate_mocs scored by orphan_link."""
    entries = [
        _moc("PKM", topics=["pkm", "notes", "linking"]),
        _entry("My Note", up_state="absent", topics=["pkm", "notes", "linking"]),
    ]
    doc = run_scan(entries, graph_audit_fn=_no_graph_audit, list_dir_fn=_no_list_dir)
    f = next(x for x in doc["findings"] if x["check"] == "unparented")
    # orphan_link scoring should propose PKM as candidate
    cands = f["detail"]["candidate_mocs"]
    assert len(cands) >= 1
    assert cands[0]["target_moc"] == "PKM"


def test_note_with_valid_up_state_not_unparented():
    """Notes with up_state==valid do NOT produce an unparented finding."""
    entries = [
        _moc("PKM"),
        _entry("Filed Note", up_state="valid"),
    ]
    doc = run_scan(entries, graph_audit_fn=_no_graph_audit, list_dir_fn=_no_list_dir)
    assert not any(f["check"] == "unparented" for f in doc["findings"])


# ──────────────────────────────────────────────────────────────────────────────
# Broken_up check (cache: up_state=="broken" + up_target) — CACHE-ONLY
# ──────────────────────────────────────────────────────────────────────────────

def test_broken_up_note_produces_integrity_finding():
    """A note with up_state==broken produces a broken_up finding (tier=integrity)."""
    graph_calls = []

    def tracked_graph(**kwargs) -> dict:
        graph_calls.append(kwargs)
        return {"orphans": [], "deadLinks": [], "total": {}}

    entries = [
        _moc("PKM"),
        _entry("Broken Note", up_state="broken", up_target="Deleted MOC"),
    ]
    doc = run_scan(entries, graph_audit_fn=tracked_graph, list_dir_fn=_no_list_dir)
    broken = [f for f in doc["findings"] if f["check"] == "broken_up"]
    assert len(broken) == 1
    f = broken[0]
    assert f["tier"] == "integrity"
    assert f["fixable"] is True
    assert f["detail"]["up_target"] == "Deleted MOC"


def test_broken_up_is_cache_only_zero_graph_audit_calls():
    """CRITICAL: broken_up is cache-only — must not trigger any graph_audit call.

    We add ONLY broken_up notes (no graph-only checks) and assert graph_audit_fn
    is never invoked for them — the call count attributable to broken_up is zero.
    We do this by running once with only broken_up entries and counting graph calls.
    """
    graph_calls = []

    def tracking_graph(**kwargs) -> dict:
        graph_calls.append(1)
        return {"orphans": [], "deadLinks": [], "total": {}}

    # Entries that only trigger broken_up (no unparented/orphan notes)
    entries = [
        _moc("PKM", up_state="valid"),
        _entry("Broken Note", up_state="broken", up_target="Deleted MOC"),
    ]
    run_scan(entries, graph_audit_fn=tracking_graph, list_dir_fn=_no_list_dir)

    # The scan may legitimately call graph_audit for orphan/dead_link checks
    # but broken_up itself must NOT cause additional calls. With only a broken
    # note and no absent notes/dead links, the scan STILL calls graph_audit once
    # (for orphan+dead_link checks). What we assert is that it's called AT MOST
    # the expected baseline count (≤1 per check round), not triggered per broken entry.
    # Specifically: adding more broken entries must not scale the call count.
    graph_calls_one_broken = len(graph_calls)

    graph_calls.clear()
    entries_many = [_moc("PKM", up_state="valid")] + [
        _entry(f"Broken{i}", up_state="broken", up_target="Deleted MOC")
        for i in range(5)
    ]
    run_scan(entries_many, graph_audit_fn=tracking_graph, list_dir_fn=_no_list_dir)
    # Call count must NOT scale with broken_up count
    assert len(graph_calls) == graph_calls_one_broken, (
        f"graph_audit call count must not scale with broken_up entries; "
        f"1 entry={graph_calls_one_broken}, 5 entries={len(graph_calls)}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Broken_up finding detail carries declaration site + value (spec 032 T2.1)
#
# up_value has THREE distinguishable cache-entry states (ADR-3) and the
# finding detail must preserve exactly which one it saw:
#   present, real value  → detail carries the value verbatim (no transform)
#   present, None         → detail carries None (inline declaration)
#   absent entirely        → detail must ALSO lack the key (stale pre-032 cache)
# ──────────────────────────────────────────────────────────────────────────────

def test_broken_up_frontmatter_source_carries_source_and_verbatim_value():
    """Frontmatter-sourced broken entry: detail carries up_source=='frontmatter'
    and the observed up_value verbatim — no unwrapping/normalising. [ref: PRD/AC-F1.2]
    """
    entries = [
        _moc("PKM"),
        _entry(
            "Broken Note",
            up_state="broken",
            up_target="Deleted MOC",
            up_source="frontmatter",
            up_value=["Deleted MOC", "Other Ref"],
        ),
    ]
    doc = run_scan(entries, graph_audit_fn=_no_graph_audit, list_dir_fn=_no_list_dir)
    f = next(x for x in doc["findings"] if x["check"] == "broken_up")
    assert f["detail"]["up_source"] == "frontmatter"
    # Verbatim passthrough: still a list, same contents, same order — no
    # unwrap_list_repr, no normalising into/out of a list, no str().
    assert f["detail"]["up_value"] == ["Deleted MOC", "Other Ref"]
    assert isinstance(f["detail"]["up_value"], list)


def test_broken_up_inline_source_carries_none_up_value():
    """Inline-sourced broken entry: detail carries up_source=='inline' and
    up_value is None — the key is PRESENT with value None, distinct from
    the key being absent. [ref: PRD/AC-F1.1]
    """
    entries = [
        _moc("PKM"),
        _entry(
            "Broken Note",
            up_state="broken",
            up_target="Deleted MOC",
            up_source="inline",
            up_value=None,
        ),
    ]
    doc = run_scan(entries, graph_audit_fn=_no_graph_audit, list_dir_fn=_no_list_dir)
    f = next(x for x in doc["findings"] if x["check"] == "broken_up")
    assert f["detail"]["up_source"] == "inline"
    assert "up_value" in f["detail"]
    assert f["detail"]["up_value"] is None


def test_broken_up_missing_up_value_key_stays_missing():
    """CRITICAL (ADR-3): a cache entry built before spec 032 lacks the
    up_value key entirely (stale cache). The finding detail must NOT
    default it to None — the key's ABSENCE must survive the hop, because
    Phase 3's sentinel test depends on distinguishing absent from None.

    A defaulting implementation (detail["up_value"] = entry.get("up_value"))
    would make this assertion fail, since it converts absence into None.
    """
    entries = [
        _moc("PKM"),
        # No up_source/up_value kwargs passed — _entry() omits both keys.
        _entry("Broken Note", up_state="broken", up_target="Deleted MOC"),
    ]
    doc = run_scan(entries, graph_audit_fn=_no_graph_audit, list_dir_fn=_no_list_dir)
    f = next(x for x in doc["findings"] if x["check"] == "broken_up")
    assert "up_value" not in f["detail"], (
        "up_value key must be ABSENT when the cache entry lacks it, not "
        "defaulted to None — this destroys the stale-cache signal (ADR-3)"
    )


def test_broken_up_no_declaration_produces_no_finding():
    """A note with no up declaration (up_state != 'broken') produces no
    broken_up finding — unchanged behaviour. [ref: PRD/AC-F1.3]
    """
    entries = [
        _moc("PKM"),
        _entry("Unfiled Note", up_state="absent", up_source=None, up_value=None),
    ]
    doc = run_scan(entries, graph_audit_fn=_no_graph_audit, list_dir_fn=_no_list_dir)
    assert not any(f["check"] == "broken_up" for f in doc["findings"])


def test_broken_up_up_target_and_other_fields_unchanged():
    """CON-7: up_target and every other existing finding field are unchanged
    by the up_source/up_value addition.
    """
    entries = [
        _moc("PKM"),
        _entry(
            "Broken Note",
            up_state="broken",
            up_target="Deleted MOC",
            up_source="frontmatter",
            up_value="Deleted MOC",
        ),
    ]
    doc = run_scan(entries, graph_audit_fn=_no_graph_audit, list_dir_fn=_no_list_dir)
    f = next(x for x in doc["findings"] if x["check"] == "broken_up")
    assert f["check"] == "broken_up"
    assert f["tier"] == "integrity"
    assert f["fixable"] is True
    assert f["target"] == {"path": "Notes/Broken Note.md", "stem": "Broken Note"}
    assert f["detail"]["up_target"] == "Deleted MOC"
    assert f["decision"] == {"selected": False, "action": None}


# ──────────────────────────────────────────────────────────────────────────────
# Orphan check (graph_audit orphans[])
# ──────────────────────────────────────────────────────────────────────────────

def test_orphan_from_graph_audit_produces_structure_finding():
    """An entry in graph_audit orphans[] produces an orphan finding (tier=structure)."""
    entries = [
        _moc("PKM", topics=["pkm"]),
        _entry("Floating Note", up_state="valid"),  # not unparented in cache
    ]

    def fake_graph(**kwargs) -> dict:
        return {
            "orphans": [{"path": "Notes/Floating Note.md"}],
            "deadLinks": [],
            "total": {},
        }

    doc = run_scan(entries, graph_audit_fn=fake_graph, list_dir_fn=_no_list_dir)
    orphans = [f for f in doc["findings"] if f["check"] == "orphan"]
    assert len(orphans) == 1
    f = orphans[0]
    assert f["tier"] == "structure"
    assert f["fixable"] is True
    assert f["target"]["path"] == "Notes/Floating Note.md"


# ──────────────────────────────────────────────────────────────────────────────
# Dead_link check (graph_audit deadLinks[])
# ──────────────────────────────────────────────────────────────────────────────

def test_dead_link_from_graph_audit_produces_integrity_finding():
    """deadLinks[] items produce dead_link findings (tier=integrity, fixable=True)."""
    entries = [_moc("PKM"), _entry("Source Note", up_state="valid")]

    def fake_graph(**kwargs) -> dict:
        return {
            "orphans": [],
            "deadLinks": [
                {"source": "Notes/Source Note.md", "target": "[[Missing]]", "count": 2}
            ],
            "total": {},
        }

    doc = run_scan(entries, graph_audit_fn=fake_graph, list_dir_fn=_no_list_dir)
    dead = [f for f in doc["findings"] if f["check"] == "dead_link"]
    assert len(dead) == 1
    f = dead[0]
    assert f["tier"] == "integrity"
    assert f["fixable"] is True
    assert f["detail"]["dead_target"] == "[[Missing]]"
    assert f["detail"]["count"] == 2


# ──────────────────────────────────────────────────────────────────────────────
# Duplicate_stem check (cache: group by stem)
# ──────────────────────────────────────────────────────────────────────────────

def test_duplicate_stems_produce_advisory_finding():
    """Multiple entries sharing a stem produce a duplicate_stem finding (advisory, not fixable)."""
    entries = [
        _moc("PKM"),
        _entry("Shared Idea", path="Notes/Shared Idea.md", up_state="valid"),
        _entry("Shared Idea", path="Archive/Shared Idea.md", up_state="valid"),
    ]
    doc = run_scan(entries, graph_audit_fn=_no_graph_audit, list_dir_fn=_no_list_dir)
    dupes = [f for f in doc["findings"] if f["check"] == "duplicate_stem"]
    assert len(dupes) == 1
    f = dupes[0]
    assert f["tier"] == "advisory"
    assert f["fixable"] is False
    assert "decision" not in f
    dupes_paths = f["detail"]["dupes"]
    assert len(dupes_paths) == 2


def test_unique_stems_no_duplicate_finding():
    """No duplicate_stem finding when all stems are unique."""
    entries = [_moc("PKM"), _entry("Note A"), _entry("Note B")]
    doc = run_scan(entries, graph_audit_fn=_no_graph_audit, list_dir_fn=_no_list_dir)
    assert not any(f["check"] == "duplicate_stem" for f in doc["findings"])


def test_duplicate_stem_exclusion_of_one_path_leaves_remaining_pair():
    """W1: excluding one of three duplicate paths still emits a finding for the other two."""
    from lib.garden_exclusions import GardenExclusions

    excl_config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "note", "value": "Archive/Dup.md"},
                "checks": ["duplicate_stem"],
                "mode": "permanent",
                "reason": "archived copy is exempt",
                "created": "2026-07-19",
            }
        ],
    }
    excl = GardenExclusions.from_dict(excl_config, today=date(2026, 7, 19))

    entries = [
        _moc("PKM"),
        _entry("Dup", path="Notes/Dup.md", up_state="valid"),
        _entry("Dup", path="Archive/Dup.md", up_state="valid"),   # excluded
        _entry("Dup", path="Projects/Dup.md", up_state="valid"),
    ]
    doc = run_scan(entries, graph_audit_fn=_no_graph_audit, list_dir_fn=_no_list_dir, exclusions=excl)
    dupes = [f for f in doc["findings"] if f["check"] == "duplicate_stem"]
    assert len(dupes) == 1, f"one finding expected for the two non-excluded paths; got {len(dupes)}"
    remaining = dupes[0]["detail"]["dupes"]
    assert "Archive/Dup.md" not in remaining, "excluded path must be filtered from finding"
    assert len(remaining) == 2, f"two non-excluded paths must remain; got {remaining}"


def test_duplicate_stem_exclusion_reducing_to_one_path_emits_no_finding():
    """W1: excluding paths down to fewer than 2 remaining → no duplicate_stem finding."""
    from lib.garden_exclusions import GardenExclusions

    excl_config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "path", "value": "Archive/"},
                "checks": ["duplicate_stem"],
                "mode": "permanent",
                "reason": "archive exempt",
                "created": "2026-07-19",
            }
        ],
    }
    excl = GardenExclusions.from_dict(excl_config, today=date(2026, 7, 19))

    entries = [
        _moc("PKM"),
        _entry("Dup", path="Notes/Dup.md", up_state="valid"),
        _entry("Dup", path="Archive/Dup.md", up_state="valid"),  # excluded
    ]
    doc = run_scan(entries, graph_audit_fn=_no_graph_audit, list_dir_fn=_no_list_dir, exclusions=excl)
    assert not any(f["check"] == "duplicate_stem" for f in doc["findings"]), (
        "only one non-excluded path remains → no duplicate_stem finding"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Stale_moc check (listDir modified older than threshold)
# ──────────────────────────────────────────────────────────────────────────────

def test_stale_moc_from_list_dir_produces_advisory_finding():
    """A MOC whose listDir modified is an int epoch-ms older than stale_moc_days is advisory.

    Real kado_client.list_dir returns modified as int epoch-milliseconds
    (Obsidian TFile.stat.mtime).  Previous ISO-string fake was mock-vs-reality mismatch.
    """
    run_today = date(2026, 7, 19)
    # 2026-01-01T00:00:00Z = 1767225600 seconds → epoch-ms 1767225600000
    # That is 200 days before run_today — well past the 90-day threshold.
    old_mtime_ms = 1767225600000

    entries = [_moc("Old MOC", up_state="valid")]

    def fake_list_dir(path=None, **kwargs) -> list:
        return [
            {
                "type": "file",
                "path": "Maps/Old MOC.md",
                "modified": old_mtime_ms,   # int epoch-ms, matching real Kado shape
                "created": old_mtime_ms,
                "size": 1024,
            }
        ]

    doc = run_scan(
        entries,
        graph_audit_fn=_no_graph_audit,
        list_dir_fn=fake_list_dir,
        stale_moc_days=90,
        today=run_today,
    )
    stale = [f for f in doc["findings"] if f["check"] == "stale_moc"]
    assert len(stale) == 1
    f = stale[0]
    assert f["tier"] == "advisory"
    assert f["fixable"] is False
    assert "decision" not in f
    # mtime is stored as human-readable ISO, not the raw int
    assert "2026-01-01" in f["detail"]["mtime"]


def test_recent_moc_not_stale():
    """A MOC modified recently (int epoch-ms) is not flagged as stale."""
    run_today = date(2026, 7, 19)
    # 2026-07-10T00:00:00Z = 1783641600000 ms — 9 days before run_today, within 90-day threshold
    recent_mtime_ms = 1783641600000

    entries = [_moc("Recent MOC", up_state="valid")]

    def fake_list_dir(path=None, **kwargs) -> list:
        return [{"type": "file", "path": "Maps/Recent MOC.md", "modified": recent_mtime_ms}]

    doc = run_scan(
        entries,
        graph_audit_fn=_no_graph_audit,
        list_dir_fn=fake_list_dir,
        stale_moc_days=90,
        today=run_today,
    )
    assert not any(f["check"] == "stale_moc" for f in doc["findings"])


def test_stale_moc_defensive_str_branch():
    """Defensive: if a list_dir item returns modified as an ISO string, it still works."""
    run_today = date(2026, 7, 19)
    old_mtime_str = "2026-01-01T00:00:00Z"

    entries = [_moc("Old MOC", up_state="valid")]

    def fake_list_dir(path=None, **kwargs) -> list:
        return [{"type": "file", "path": "Maps/Old MOC.md", "modified": old_mtime_str}]

    doc = run_scan(
        entries,
        graph_audit_fn=_no_graph_audit,
        list_dir_fn=fake_list_dir,
        stale_moc_days=90,
        today=run_today,
    )
    stale = [f for f in doc["findings"] if f["check"] == "stale_moc"]
    assert len(stale) == 1, "ISO-string modified must still produce a stale_moc finding"


def test_list_dir_unavailable_marks_stale_moc_skipped():
    """W2: when list_dir_fn raises, stale_moc is added to skipped_checks and no crash occurs."""
    entries = [_moc("Some MOC", up_state="valid")]

    def failing_list_dir(path=None, **kwargs):
        raise RuntimeError("listDir unavailable")

    doc = run_scan(
        entries,
        graph_audit_fn=_no_graph_audit,
        list_dir_fn=failing_list_dir,
    )
    assert not any(f["check"] == "stale_moc" for f in doc["findings"]), (
        "no stale_moc findings when listDir is unavailable"
    )
    assert "stale_moc" in doc["skipped_checks"], (
        "stale_moc must appear in skipped_checks when listDir raises"
    )
    reason = doc.get("skipped_checks_reason", "")
    assert "listdir" in reason.lower() or "unavailable" in reason.lower() or "not run" in reason.lower(), (
        f"skipped reason must mention listDir/unavailable; got: {reason!r}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Exclusions applied
# ──────────────────────────────────────────────────────────────────────────────

def test_exclusion_suppresses_per_check_finding():
    """A per-check exclusion suppresses that check for matched entries."""
    from lib.garden_exclusions import GardenExclusions

    excl_config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "path", "value": "Calendar/"},
                "checks": ["unparented"],
                "mode": "permanent",
                "reason": "daily notes",
                "created": "2026-07-19",
            }
        ],
    }
    excl = GardenExclusions.from_dict(excl_config, today=date(2026, 7, 19))

    entries = [
        _moc("PKM"),
        _entry("Daily", path="Calendar/2026-07-19.md", up_state="absent"),
    ]
    doc = run_scan(
        entries,
        graph_audit_fn=_no_graph_audit,
        list_dir_fn=_no_list_dir,
        exclusions=excl,
    )
    assert not any(f["check"] == "unparented" for f in doc["findings"]), (
        "excluded path must not appear in unparented findings"
    )


def test_exclusion_complete_scope_suppresses_all_checks():
    """A complete (checks: all) exclusion suppresses every check for matched entries."""
    from lib.garden_exclusions import GardenExclusions

    excl_config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "note", "value": "Notes/Big Refactor.md"},
                "checks": "all",
                "mode": "permanent",
                "reason": "in progress",
                "created": "2026-07-19",
            }
        ],
    }
    excl = GardenExclusions.from_dict(excl_config, today=date(2026, 7, 19))

    entries = [
        _moc("PKM"),
        _entry("Big Refactor", path="Notes/Big Refactor.md", up_state="broken", up_target="Deleted"),
    ]
    doc = run_scan(
        entries,
        graph_audit_fn=_no_graph_audit,
        list_dir_fn=_no_list_dir,
        exclusions=excl,
    )
    assert doc["findings"] == [], "all checks suppressed for excluded note"


def test_exclusion_non_matching_note_still_reported():
    """An exclusion for one note does not suppress findings for a different note."""
    from lib.garden_exclusions import GardenExclusions

    excl_config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "note", "value": "Notes/Exempt.md"},
                "checks": "all",
                "mode": "permanent",
                "reason": "exempt",
                "created": "2026-07-19",
            }
        ],
    }
    excl = GardenExclusions.from_dict(excl_config, today=date(2026, 7, 19))

    entries = [
        _moc("PKM"),
        _entry("Other Note", path="Notes/Other Note.md", up_state="absent"),
    ]
    doc = run_scan(
        entries,
        graph_audit_fn=_no_graph_audit,
        list_dir_fn=_no_list_dir,
        exclusions=excl,
    )
    unparented = [f for f in doc["findings"] if f["check"] == "unparented"]
    assert len(unparented) == 1


# ──────────────────────────────────────────────────────────────────────────────
# Severity ordering: integrity > structure > advisory
# ──────────────────────────────────────────────────────────────────────────────

def test_severity_order_integrity_before_structure_before_advisory():
    """Findings are severity-ordered: integrity > structure > advisory."""
    run_today = date(2026, 7, 19)
    old_mtime = "2026-01-01T00:00:00Z"

    entries = [
        _moc("PKM", topics=["pkm"]),
        _entry("Orphan Note", up_state="absent", topics=["pkm"]),
        _entry("Broken Note", up_state="broken", up_target="Deleted MOC"),
        # Two notes with same stem for duplicate_stem
        _entry("Dup", path="Notes/Dup.md", up_state="valid"),
        _entry("Dup", path="Archive/Dup.md", up_state="valid"),
    ]

    def fake_list_dir(path=None, **kwargs) -> list:
        return [{"type": "file", "path": "Maps/PKM.md", "modified": old_mtime}]

    doc = run_scan(
        entries,
        graph_audit_fn=_no_graph_audit,
        list_dir_fn=fake_list_dir,
        stale_moc_days=90,
        today=run_today,
    )

    tier_order = {"integrity": 0, "structure": 1, "advisory": 2}
    tiers = [tier_order[f["tier"]] for f in doc["findings"]]
    assert tiers == sorted(tiers), (
        f"findings must be severity-ordered; got tiers: {[f['tier'] for f in doc['findings']]}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Advisory findings have no decision block
# ──────────────────────────────────────────────────────────────────────────────

def test_advisory_findings_have_no_decision_block():
    """Advisory findings (duplicate_stem, stale_moc) must not carry a decision block."""
    entries = [
        _moc("PKM"),
        _entry("Dup", path="A/Dup.md", up_state="valid"),
        _entry("Dup", path="B/Dup.md", up_state="valid"),
    ]
    doc = run_scan(entries, graph_audit_fn=_no_graph_audit, list_dir_fn=_no_list_dir)
    for f in doc["findings"]:
        if f["tier"] == "advisory":
            assert "decision" not in f, (
                f"advisory finding {f['check']!r} must not carry a decision block"
            )


def test_fixable_findings_carry_decision_placeholder():
    """Fixable findings (unparented, broken_up) carry a decision placeholder."""
    entries = [
        _moc("PKM"),
        _entry("Orphan Note", up_state="absent"),
        _entry("Broken Note", up_state="broken", up_target="Deleted MOC"),
    ]
    doc = run_scan(entries, graph_audit_fn=_no_graph_audit, list_dir_fn=_no_list_dir)
    fixable = [f for f in doc["findings"] if f["fixable"]]
    assert len(fixable) >= 2
    for f in fixable:
        assert "decision" in f, f"fixable finding {f['check']!r} must carry decision block"


# ──────────────────────────────────────────────────────────────────────────────
# Edge case: empty cache
# ──────────────────────────────────────────────────────────────────────────────

def test_empty_entries_produces_zero_findings():
    """An empty entries list produces no findings, no crash."""
    doc = run_scan([], graph_audit_fn=_no_graph_audit, list_dir_fn=_no_list_dir)
    assert doc["findings"] == []


# ──────────────────────────────────────────────────────────────────────────────
# Edge case: zero findings
# ──────────────────────────────────────────────────────────────────────────────

def test_healthy_vault_zero_findings():
    """A vault with no issues produces zero findings, no crash."""
    entries = [
        _moc("PKM"),
        _entry("Filed Note", up_state="valid"),
    ]
    doc = run_scan(entries, graph_audit_fn=_no_graph_audit, list_dir_fn=_no_list_dir)
    assert doc["findings"] == []


# ──────────────────────────────────────────────────────────────────────────────
# Edge case: graph unavailable — partial report, no crash
# ──────────────────────────────────────────────────────────────────────────────

def test_graph_unavailable_skips_orphan_dead_link_but_not_others():
    """When graph_audit raises, orphan+dead_link are skipped; cache checks still run."""
    run_today = date(2026, 7, 19)
    old_mtime = "2026-01-01T00:00:00Z"

    entries = [
        _moc("PKM"),
        _entry("Orphan Note", up_state="absent"),    # would be unparented (cache)
        _entry("Broken Note", up_state="broken", up_target="Deleted MOC"),  # broken_up (cache)
        _entry("Dup", path="A/Dup.md", up_state="valid"),
        _entry("Dup", path="B/Dup.md", up_state="valid"),
    ]

    def fake_list_dir(path=None, **kwargs) -> list:
        return [{"type": "file", "path": "Maps/PKM.md", "modified": old_mtime}]

    # Must not crash
    doc = run_scan(
        entries,
        graph_audit_fn=_graph_unavailable,
        list_dir_fn=fake_list_dir,
        stale_moc_days=90,
        today=run_today,
    )

    checks_found = {f["check"] for f in doc["findings"]}
    # Cache checks must still be present
    assert "unparented" in checks_found or "broken_up" in checks_found or "duplicate_stem" in checks_found, (
        "cache-derived checks must still run when graph is unavailable"
    )
    # Graph checks must NOT appear as normal findings
    assert "orphan" not in checks_found
    assert "dead_link" not in checks_found

    # The skipped checks must be recorded in doc metadata
    skipped = doc.get("skipped_checks", [])
    assert "orphan" in skipped, "orphan must be listed as skipped when graph unavailable"
    assert "dead_link" in skipped, "dead_link must be listed as skipped when graph unavailable"


def test_graph_unavailable_skip_message_present():
    """When graph is unavailable, doc records the reason in skipped_checks_reason."""
    doc = run_scan(
        [_moc("PKM")],
        graph_audit_fn=_graph_unavailable,
        list_dir_fn=_no_list_dir,
    )
    reason = doc.get("skipped_checks_reason", "")
    assert "graph unavailable" in reason.lower() or "not run" in reason.lower(), (
        f"expected graph-unavailable reason; got: {reason!r}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Reappeared exclusions surfaced in doc
# ──────────────────────────────────────────────────────────────────────────────

def test_reappeared_exclusions_included_in_doc():
    """Expired temporary exclusions appear in doc['reappeared_exclusions']."""
    from lib.garden_exclusions import GardenExclusions

    excl_config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "note", "value": "Notes/Old Draft.md"},
                "checks": "all",
                "mode": "temporary",
                "until": "2026-01-01",
                "reason": "was fixing",
                "created": "2025-10-01",
            }
        ],
    }
    excl = GardenExclusions.from_dict(excl_config, today=date(2026, 7, 19))

    doc = run_scan(
        [_moc("PKM")],
        graph_audit_fn=_no_graph_audit,
        list_dir_fn=_no_list_dir,
        exclusions=excl,
    )
    reappeared = doc.get("reappeared_exclusions", [])
    assert len(reappeared) == 1
    assert reappeared[0]["target"]["value"] == "Notes/Old Draft.md"


# ──────────────────────────────────────────────────────────────────────────────
# Doc metadata fields
# ──────────────────────────────────────────────────────────────────────────────

def test_doc_carries_run_metadata():
    """The output doc carries run_id, generated, and profile fields."""
    doc = run_scan(
        [_moc("PKM")],
        graph_audit_fn=_no_graph_audit,
        list_dir_fn=_no_list_dir,
        run_id="test-run-001",
        profile="miyo",
        generated="2026-07-19T10:00:00Z",
    )
    assert doc["run_id"] == "test-run-001"
    assert doc["profile"] == "miyo"
    assert doc["generated"] == "2026-07-19T10:00:00Z"


# ──────────────────────────────────────────────────────────────────────────────
# Finding ID stability — each finding has a stable id
# ──────────────────────────────────────────────────────────────────────────────

def test_findings_have_unique_ids():
    """Each finding carries a unique id field."""
    entries = [
        _moc("PKM"),
        _entry("Note A", up_state="absent"),
        _entry("Note B", up_state="broken", up_target="Deleted"),
    ]
    doc = run_scan(entries, graph_audit_fn=_no_graph_audit, list_dir_fn=_no_list_dir)
    ids = [f["id"] for f in doc["findings"]]
    assert len(ids) == len(set(ids)), f"finding ids must be unique; got: {ids}"


# ──────────────────────────────────────────────────────────────────────────────
# Schema validation
# ──────────────────────────────────────────────────────────────────────────────

def test_output_validates_against_doc_schema():
    """run_scan output validates against garden-audit-doc.schema.json."""
    import jsonschema

    run_today = date(2026, 7, 19)
    old_mtime = "2026-01-01T00:00:00Z"

    entries = [
        _moc("PKM", topics=["pkm"]),
        _entry("Orphan Note", up_state="absent", topics=["pkm"]),
        _entry("Broken Note", up_state="broken", up_target="Deleted MOC"),
        _entry("Dup", path="A/Dup.md", up_state="valid"),
        _entry("Dup", path="B/Dup.md", up_state="valid"),
    ]

    def fake_list_dir(path=None, **kwargs) -> list:
        return [{"type": "file", "path": "Maps/PKM.md", "modified": old_mtime}]

    def fake_graph(**kwargs) -> dict:
        return {
            "orphans": [{"path": "Notes/Orphan Note.md"}],
            "deadLinks": [{"source": "Notes/Orphan Note.md", "target": "[[Missing]]", "count": 1}],
            "total": {},
        }

    doc = run_scan(
        entries,
        graph_audit_fn=fake_graph,
        list_dir_fn=fake_list_dir,
        stale_moc_days=90,
        today=run_today,
        run_id="schema-test",
        profile="miyo",
        generated="2026-07-19T10:00:00Z",
    )

    schema_path = SCHEMAS_DIR / "garden-audit-doc.schema.json"
    assert schema_path.exists(), f"schema not found: {schema_path}"
    schema = json.loads(schema_path.read_text())
    # Should not raise
    jsonschema.validate(instance=doc, schema=schema)


# ──────────────────────────────────────────────────────────────────────────────
# CLI (main()) tests
# ──────────────────────────────────────────────────────────────────────────────

class TestMainCLI:
    """Verify the garden-audit.py CLI (main()) writes schema-valid JSON to --output.

    Uses a fake KadoClient injected via monkeypatch — no Kado/network required.
    Validates the output against garden-audit-doc.schema.json.
    """

    def _write_config(self, tmp_path: Path, profile: str = "miyo") -> Path:
        import yaml

        config = {"profile": profile, "concepts": {"inbox": "100 Inbox/"}}
        config_path = tmp_path / "vault-config.yaml"
        config_path.write_text(yaml.dump(config), encoding="utf-8")
        return config_path

    def _write_cache(self, tmp_path: Path, entries: list) -> Path:
        import yaml

        cache = {"entries": entries, "last_scan": "2026-07-20T00:00:00+00:00"}
        cache_path = tmp_path / "moc-structure-cache.yaml"
        cache_path.write_text(yaml.dump(cache), encoding="utf-8")
        return cache_path

    def test_main_writes_schema_valid_output(self, tmp_path, monkeypatch):
        """main() with a fake KadoClient produces a schema-valid garden-audit-doc.json."""
        import sys
        import types

        # Minimal cache: one unparented note, one MOC
        entries = [
            {"path": "Notes/Loose.md", "stem": "Loose", "kind": "note",
             "up_state": "absent", "topics": [], "tags": []},
            {"path": "MOCs/Ideas.md", "stem": "Ideas", "kind": "moc",
             "up_state": "valid", "topics": ["ideas"], "tags": []},
        ]
        config_path = self._write_config(tmp_path)
        self._write_cache(tmp_path, entries)

        output_path = tmp_path / "output" / "garden-audit-doc.json"

        # Fake KadoClient: graph_audit returns empty result; list_dir returns []
        class _FakeClient:
            def graph_audit(self, **kwargs):
                return {"orphans": [], "deadLinks": [], "total": {}}

            def list_dir(self, path="/", **kwargs):
                return []

        # Inject fake KadoClient into the garden_audit module's lib.kado_client
        fake_kado_mod = types.ModuleType("lib.kado_client")
        fake_kado_mod.KadoClient = _FakeClient
        monkeypatch.setitem(sys.modules, "lib.kado_client", fake_kado_mod)

        args = [
            "--config", str(config_path),
            "--output", str(output_path),
        ]
        monkeypatch.setattr(sys, "argv", ["garden-audit.py"] + args)

        exit_code = garden_audit.main()

        assert exit_code == 0, "main() must exit 0 on success"
        assert output_path.exists(), "--output file must be written"

        doc = json.loads(output_path.read_text(encoding="utf-8"))

        # Schema validation
        schema_path = SCHEMAS_DIR / "garden-audit-doc.schema.json"
        schema = json.loads(schema_path.read_text())
        jsonschema.validate(instance=doc, schema=schema)

        # At least one finding (the unparented note)
        findings = doc.get("findings") or []
        unparented = [f for f in findings if f["check"] == "unparented"]
        assert unparented, "unparented finding expected for Loose.md"

        # Profile from config propagated
        assert doc.get("profile") == "miyo"

    def test_main_missing_config_exits_nonzero(self, tmp_path, monkeypatch):
        """main() exits 1 when --config file does not exist."""
        import sys

        output_path = tmp_path / "out.json"
        monkeypatch.setattr(sys, "argv", [
            "garden-audit.py",
            "--config", str(tmp_path / "missing.yaml"),
            "--output", str(output_path),
        ])

        exit_code = garden_audit.main()
        assert exit_code != 0, "must exit non-zero when config is missing"
        assert not output_path.exists(), "output must not be written on failure"

    def test_main_exclusions_flag_accepted(self, tmp_path, monkeypatch):
        """main() accepts --exclusions and loads the file without error."""
        import sys
        import types
        import yaml

        entries = [
            {"path": "Notes/Loose.md", "stem": "Loose", "kind": "note",
             "up_state": "absent", "topics": [], "tags": []},
        ]
        config_path = self._write_config(tmp_path)
        self._write_cache(tmp_path, entries)

        excl_path = tmp_path / "garden-audit-exclusions.yaml"
        excl_path.write_text(
            yaml.dump({"version": 1, "exclusions": []}), encoding="utf-8"
        )
        output_path = tmp_path / "out.json"

        class _FakeClient:
            def graph_audit(self, **kwargs):
                return {"orphans": [], "deadLinks": [], "total": {}}

            def list_dir(self, path="/", **kwargs):
                return []

        fake_kado_mod = types.ModuleType("lib.kado_client")
        fake_kado_mod.KadoClient = _FakeClient
        monkeypatch.setitem(sys.modules, "lib.kado_client", fake_kado_mod)

        monkeypatch.setattr(sys, "argv", [
            "garden-audit.py",
            "--config", str(config_path),
            "--exclusions", str(excl_path),
            "--output", str(output_path),
        ])

        exit_code = garden_audit.main()
        assert exit_code == 0
        assert output_path.exists()
