#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t6_0c_merge_proposed_mocs_case_folded.py — spec 034 T6.0c.

`_merge_proposed_mocs_by_name` collapses approved Proposed MOCs that resolve to
one Name (#67, decision 2026-06-17: merge on Name only, first occurrence's
parent kept). It keyed `merged[name]` on the EXACT title, so `Travel (MOC)` and
`travel (MOC)` survived it as two confirmed items — while T6.0's folded
`by_dest` downstream emits ONE create_moc for the pair.

That mismatch is what this module pins. `derive_expected` counts one expected
create_moc per confirmed item with no destination comparison, so the audit read
`expected=2 actual=1 [DIFF]` plus a `[MISSING]` per-item row, both of which set
`hard_fail` — and `synthesis-conductor.md` step 3e is STRICT about stopping on a
diff. Folding the merge key removes the case-only pair before any consumer sees
it, so `by_dest`'s fold becomes the defence-in-depth its own comment claims and
the audit completes.

What each block pins:

  1. The merge itself — a case-only pair collapses to one entry whose
     `supporting_items`, `tags` and `member_stems` are the UNION of the group.
     Same semantics the exact-name merge already has: a merge, not a drop.
  2. The survivor keeps the spelling its author wrote. Nothing folded is
     written back into `title`, `destination`, or any rendered field.
  3. `derive_expected` over the merged confirmation counts `create_moc == 1`
     AND `run_diff` completes — exit 0, no `[DIFF]`, no `[MISSING]`.
  4. The up-bullet. `resolve_target_moc_paths`' `in_set` is keyed by the EXACT
     `_moc_stem(title)` and stays that way (`b9d34e1` measured folding it as
     redirecting one MOC's bullets into a different folder's MOC). A
     `link_to_moc` minted from the LOSING spelling therefore misses the
     survivor's key and keeps `target_moc_path: null`. Asserted hard-coded,
     never as a branch that passes either way.
  5. Both parser paths. Three call sites: the wire path merges once (`:411`);
     the markdown path merges twice — per-document inside `parse_proposed_mocs`
     (`:1111`) and again over primary + fan (`:2282`). The fold must be
     idempotent across that double merge, and the covered path is the one
     `derive_expected` consumes: `confirmed_items` from parsed-suggestions.json,
     post-merge.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
PARSER = SCRIPTS_DIR / "suggestion-parser.py"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


parser = _load("parser_t60c", "suggestion-parser.py")
diff = _load("instructions_diff_t60c", "instructions-diff.py")

from lib.render_actions import build_actions  # noqa: E402
from lib.render_resolve import resolve_target_moc_paths  # noqa: E402

MOC_FOLDER = "Atlas/200 Maps/"
INBOX = "100 Inbox/"

CFG = {
    "concepts.inbox": INBOX,
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
}


class StubClient:
    """Kado-shaped stub whose vault is empty: nothing resolves by name, so the
    in-set tier is the only route a link_to_moc has."""

    def read_note(self, path: str) -> dict:
        raise FileNotFoundError(f"stub: not found: {path}")

    def search_by_name(self, stem: str) -> list[dict]:
        return []


def _proposal(
    title: str, *, supporting: str, tags: list[str], members: list[str], parent: str = "",
) -> dict:
    """A confirmed-item-shaped Proposed MOC, as both parser paths build them."""
    return {
        "id": "MOC01",
        "source_path": None,
        "type": "moc",
        "approved": True,
        "delete_source": False,
        "action": "create_moc",
        "title": title,
        "tags": list(tags),
        "parent_moc": parent,
        "parent_mocs": [parent] if parent else [],
        "destination": MOC_FOLDER,
        "template": "t_moc_tomo.md",
        "summary": None,
        "classification": None,
        "supporting_items": supporting,
        "topic": title,
        "member_stems": list(members),
    }


# ──────────────────────────────────────────────────────────────────────
# 1. The merge — a case-only pair collapses, with unions
# ──────────────────────────────────────────────────────────────────────

def test_case_only_proposed_mocs_merge_into_one_with_unions():
    """`Travel (MOC)` and `travel (MOC)` are one file on this filesystem
    (CON-6). They must collapse to ONE create_moc whose supporting_items, tags
    and member_stems are the union of the group — the same semantics the
    exact-name merge already has (see
    test_fan_and_primary_proposed_mocs_merge_by_name), so this is a merge and
    not a drop of the second proposal's children."""
    merged = parser._merge_proposed_mocs_by_name([
        _proposal(
            "Travel (MOC)", supporting="S01", tags=["topic/travel"], members=["Dresden"],
        ),
        _proposal(
            "travel (MOC)", supporting="S02", tags=["topic/reisen"], members=["Kyoto"],
        ),
    ])

    assert len(merged) == 1, (
        f"expected ONE merged create_moc, got {len(merged)}: "
        f"{[m.get('title') for m in merged]}"
    )
    survivor = merged[0]
    supporting = survivor.get("supporting_items") or ""
    assert "S01" in supporting and "S02" in supporting, (
        f"merged MOC must union supporting_items; got {supporting!r}"
    )
    assert sorted(survivor["tags"]) == ["topic/reisen", "topic/travel"], survivor["tags"]
    assert sorted(survivor["member_stems"]) == ["Dresden", "Kyoto"], (
        f"merged MOC must union member_stems so the down-link binding pass keeps "
        f"every member; got {survivor['member_stems']}"
    )


def test_two_genuinely_different_names_still_do_not_merge():
    """The fold is a case fold, not a loose match — distinct names stay
    distinct."""
    merged = parser._merge_proposed_mocs_by_name([
        _proposal("Travel (MOC)", supporting="S01", tags=[], members=[]),
        _proposal("Travelling (MOC)", supporting="S02", tags=[], members=[]),
    ])
    assert [m["title"] for m in merged] == ["Travel (MOC)", "Travelling (MOC)"]


def test_eszett_folds_to_ss_not_lowercased():
    """`casefold()`, never `.lower()`: these are German notes and `ß` folds to
    `ss`, which `.lower()` leaves alone `[ref: SDD/CON-6, ADR-4]`."""
    merged = parser._merge_proposed_mocs_by_name([
        _proposal("Straße (MOC)", supporting="S01", tags=[], members=[]),
        _proposal("STRASSE (MOC)", supporting="S02", tags=[], members=[]),
    ])
    assert len(merged) == 1, (
        f"ß folds to ss under casefold(); .lower() would keep these apart: "
        f"{[m['title'] for m in merged]}"
    )
    assert merged[0]["title"] == "Straße (MOC)"


# ──────────────────────────────────────────────────────────────────────
# 2. The survivor keeps its author's spelling
# ──────────────────────────────────────────────────────────────────────

def test_survivor_keeps_the_spelling_its_author_wrote():
    """The fold is a comparison key only. No casefolded string may reach
    `title`, `destination`, or any other rendered field — the user always reads
    back the name they typed."""
    merged = parser._merge_proposed_mocs_by_name([
        _proposal("Travel (MOC)", supporting="S01", tags=[], members=[]),
        _proposal("travel (MOC)", supporting="S02", tags=[], members=[]),
    ])
    survivor = merged[0]
    assert survivor["title"] == "Travel (MOC)", (
        "the first occurrence's spelling survives, unfolded"
    )
    assert survivor["destination"] == MOC_FOLDER
    assert survivor["topic"] == "Travel (MOC)"
    folded = "travel (moc)"
    for key, value in survivor.items():
        if isinstance(value, str):
            assert value != folded, f"{key} carries the folded key, not a real name"


# ──────────────────────────────────────────────────────────────────────
# 5. Both parser paths — wire merges once, markdown merges twice
# ──────────────────────────────────────────────────────────────────────

def _wire_with_two_proposed_mocs(first: str, second: str) -> dict:
    return {
        "schema_version": "1",
        "run_id": "2026-09-08T10-00-00Z-t60c",
        "suggestions": [],
        "proposed_mocs": [
            {"topic": "Reisen", "name": first, "decision": "approve",
             "parent": "2700 - Art & Recreation", "tags": ["topic/reisen"],
             "member_ids": []},
            {"topic": "Travel", "name": second, "decision": "approve",
             "parent": "2700 - Art & Recreation", "tags": ["topic/travel"],
             "member_ids": []},
        ],
    }


def test_wire_path_merges_a_case_only_pair():
    """Call site `:411` — the wire path merges once."""
    out = parser.build_from_wire(
        _wire_with_two_proposed_mocs("Travel (MOC)", "travel (MOC)"), ""
    )
    mocs = [c for c in out["confirmed_items"] if c.get("action") == "create_moc"]
    assert len(mocs) == 1, [m.get("title") for m in mocs]
    assert mocs[0]["title"] == "Travel (MOC)"
    assert sorted(mocs[0]["tags"]) == ["topic/reisen", "topic/travel"]


def _doc_with_proposed_mocs(*proposals: tuple[str, str, str]) -> str:
    """Suggestions doc carrying one approved Proposed MOC per (topic, name,
    supporting) triple."""
    head = [
        "---",
        "type: tomo-suggestions",
        "generated: 2026-09-08T10:00:00Z",
        'tomo_version: "0.1.0"',
        "profile: miyo",
        "source_items: 1",
        "run_id: 2026-09-08T10-00-00Z-t60c",
        "---",
        "",
        "# Inbox Suggestions — 2026-09-08",
        "",
        "- [x] Approved",
        "",
        "## Proposed MOCs",
        "",
    ]
    for topic, name, supporting in proposals:
        head += [
            f"### Proposed MOC: {topic}",
            f"- **Name:** {name}",
            "- **Parent:** [[2700 - Art & Recreation]]",
            f"- **Supporting items:** {supporting}",
            "- **Decision:**",
            "  - [x] Approve (create this MOC with the Name above)",
            "  - [ ] Skip",
            "",
        ]
    return "\n".join(head)


def _run_parser(primary: Path, fan: Path | None = None) -> dict:
    cmd = [sys.executable, str(PARSER), "--file", str(primary)]
    if fan is not None:
        cmd += ["--fan-resolve-file", str(fan)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, (
        f"parser exit {result.returncode}; stderr:\n{result.stderr}"
    )
    return json.loads(result.stdout)


def test_markdown_path_merges_a_case_only_pair_across_the_double_merge(tmp_path):
    """Call sites `:1111` (per-document, inside parse_proposed_mocs) and `:2282`
    (primary + fan). The fold must be idempotent across BOTH: the primary doc
    carries a case-only pair that the per-document merge collapses, and the fan
    doc carries a THIRD spelling that only the second merge can see. One
    create_moc, all three supporting items."""
    primary = tmp_path / "suggestions.md"
    fan = tmp_path / "suggestions-fan.md"
    primary.write_text(
        _doc_with_proposed_mocs(
            ("Reisen", "Travel (MOC)", "Dresden"),
            ("Travel", "travel (MOC)", "Kyoto"),
        ),
        encoding="utf-8",
    )
    fan.write_text(
        _doc_with_proposed_mocs(("Fernweh", "TRAVEL (MOC)", "Furano")),
        encoding="utf-8",
    )

    out = _run_parser(primary, fan)

    mocs = [c for c in out["confirmed_items"] if c.get("action") == "create_moc"]
    assert len(mocs) == 1, (
        f"the double merge must be idempotent — expected ONE create_moc, got "
        f"{[m.get('title') for m in mocs]}"
    )
    assert mocs[0]["title"] == "Travel (MOC)", mocs[0].get("title")
    supporting = mocs[0].get("supporting_items") or ""
    for member in ("Dresden", "Kyoto", "Furano"):
        assert member in supporting, (
            f"{member!r} lost across the double merge; got {supporting!r}"
        )


# ──────────────────────────────────────────────────────────────────────
# 3. The audit completes
# ──────────────────────────────────────────────────────────────────────

def _manifest_for(confirmed: list[dict]) -> list[dict]:
    """A render manifest mirroring the confirmed create_moc items."""
    return [
        {
            "id": c["id"],
            "action": "create_moc",
            "title": c["title"],
            "rendered_file": f"{c['title']}.md",
            "destination": c.get("destination") or MOC_FOLDER,
            "parent_moc": c.get("parent_moc") or "",
            "template": c.get("template"),
            "tags": c.get("tags") or [],
            "supporting_items": c.get("supporting_items"),
        }
        for c in confirmed
        if c.get("action") == "create_moc"
    ]


def test_derive_expected_counts_one_create_moc_and_the_audit_completes(tmp_path):
    """`derive_expected` (instructions-diff.py:278) counts one expected
    create_moc per confirmed item with no destination comparison of its own.
    With the merge folded, the confirmation carries ONE item, so the count
    matches what T6.0's folded `by_dest` emits — and the audit's own outcome is
    a clean exit, not merely a matching number."""
    primary = tmp_path / "suggestions.md"
    primary.write_text(
        _doc_with_proposed_mocs(
            ("Reisen", "Travel (MOC)", "Dresden"),
            ("Travel", "travel (MOC)", "Kyoto"),
        ),
        encoding="utf-8",
    )
    parsed = _run_parser(primary)

    expected = diff.derive_expected(parsed)
    assert expected["counts"]["create_moc"] == 1, (
        f"a folded merge yields one confirmed create_moc, so derive_expected "
        f"must expect one; got {expected['counts']['create_moc']}"
    )

    actions, _skipped_assets = build_actions(
        _manifest_for(parsed["confirmed_items"]),
        parsed["confirmed_items"],
        parsed.get("daily_updates") or [],
        parsed.get("skipped") or [],
        CFG,
    )
    instrs = {"actions": actions, "action_count": len(actions)}

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc, _observations = diff.run_diff(parsed, instrs)
    report = buf.getvalue()

    assert rc == 0, (
        "the audit must complete, not hard-fail — synthesis-conductor step 3e "
        f"is STRICT about stopping on a diff.\n{report}"
    )
    assert "[DIFF]" not in report, report
    assert "[MISSING]" not in report, report


# ──────────────────────────────────────────────────────────────────────
# 4. The up-bullet — traced, not assumed
# ──────────────────────────────────────────────────────────────────────

def test_up_bullet_minted_from_the_losing_spelling_stays_unresolved():
    """FINDING (T6.0c, traced at HEAD): folding the merge does NOT recover the
    losing spelling's up-bullet.

    `resolve_target_moc_paths`' `in_set` is keyed by the EXACT `_moc_stem(title)`
    and must stay that way — `b9d34e1` measured folding it as redirecting one
    MOC's bullets into a different folder's MOC and reverted it, and
    test_two_in_set_mocs_differing_only_in_case_keep_their_own_links guards
    against re-folding. So the survivor is indexed under `Travel (MOC)` only,
    and a link_to_moc minted from a note whose author wrote the parent as
    `travel (MOC)` misses that key. Tier 2 (Kado byName) cannot help either:
    the MOC does not exist in the vault yet. The action keeps
    `target_moc_path: null` and reaches the wire with no target.

    Hard-coded deliberately — a branch that accepts either outcome would record
    nothing."""
    client = StubClient()
    actions = [
        {
            "id": "I01",
            "action": "create_moc",
            "title": "Travel (MOC)",
            "destination": f"{MOC_FOLDER}Travel (MOC).md",
        },
        {
            "id": "I02",
            "action": "link_to_moc",
            "target_moc": "travel (MOC)",
            "target_moc_path": None,
            "line_to_add": "- [[Kyoto]]",
        },
    ]

    assert resolve_target_moc_paths(actions, client) == 0
    assert actions[1]["target_moc_path"] is None, (
        "the losing spelling's up-bullet is NOT recovered by the upstream merge "
        "fold; in_set stays exact by measurement (b9d34e1)"
    )
