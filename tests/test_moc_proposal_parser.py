"""Tests for moc-proposal-parser.py."""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tomo" / "scripts"))

_mod = importlib.import_module("moc-proposal-parser")
parse_moc_proposal = _mod.parse_moc_proposal


MINIMAL_PROPOSAL = """\
---
tomo:
  doc_type: moc-proposal
  state: pending-accept
---

# MOC Proposal

### MOC01 — Test MOC

- [x] Accept

**Title:** `My Test MOC`
**Location:** `Atlas/200 Maps/`
**Template:** [[t_moc_tomo]]

#### Parent

- [x] up:: `[[Parent MOC]]` (confidence 0.90)
- [ ] kein parent (top-level MOC)

#### Children (3)

- [x] `[[Note A]]` (kein up:: bisher)
- [x] `[[Note B]]` (kein up:: bisher)
- [ ] `[[Note C]]` (kein up:: bisher)

#### up::-Handling Override

- [x] **Bestehende up:: behalten, neue MOC als `related::`** (gilt für alle 3 Children)
"""

REJECTED_MOC = """\
---
tomo:
  doc_type: moc-proposal
---

# MOC Proposal

### MOC01 — Rejected MOC

- [ ] Accept

**Title:** `Should Not Appear`
**Location:** `Atlas/200 Maps/`
**Template:** [[t_moc_tomo]]

#### Children (1)

- [x] `[[Note X]]`
"""

MULTI_MOC = """\
# MOC Proposal

### MOC01 — First

- [x] Accept

**Title:** `First MOC`
**Location:** `Atlas/200 Maps/`
**Template:** [[t_moc_tomo]]

#### Parent

- [x] kein parent (top-level MOC)

#### Children (2)

- [x] `[[Alpha]]`
- [x] `[[Beta]]`

#### up::-Handling Override

- [ ] **Bestehende up:: behalten, neue MOC als `related::`**

### MOC02 — Second

- [ ] Accept

**Title:** `Second MOC`

### MOC03 — Third

- [x] Accept

**Title:** `Third MOC`
**Location:** `Atlas/200 Maps/`
**Template:** [[t_moc_tomo]]

#### Parent

- [x] up:: `[[Some Parent]]`

#### Children (1)

- [x] `[[Gamma]]`

#### up::-Handling Override

- [x] **Bestehende up:: behalten**
"""


def test_accepted_moc_basic_fields():
    result = parse_moc_proposal(MINIMAL_PROPOSAL)
    assert result["total_sections"] == 1
    assert result["total_approved"] == 1
    assert len(result["confirmed_items"]) == 1

    item = result["confirmed_items"][0]
    assert item["id"] == "MOC01"
    assert item["action"] == "create_moc"
    assert item["title"] == "My Test MOC"
    assert item["destination"] == "Atlas/200 Maps/"
    assert item["template"] == "t_moc_tomo"


def test_accepted_moc_parent():
    item = parse_moc_proposal(MINIMAL_PROPOSAL)["confirmed_items"][0]
    assert item["parent_moc"] == "Parent MOC"
    assert item["parent_mocs"] == ["Parent MOC"]


def test_accepted_children_only_checked():
    item = parse_moc_proposal(MINIMAL_PROPOSAL)["confirmed_items"][0]
    stems = item["supporting_items"]
    assert isinstance(stems, list)
    assert "Note A" in stems
    assert "Note B" in stems
    assert "Note C" not in stems


def test_override_preserve_detected():
    item = parse_moc_proposal(MINIMAL_PROPOSAL)["confirmed_items"][0]
    assert item["override_preserve_existing_up"] is True


def test_rejected_moc_goes_to_skipped():
    result = parse_moc_proposal(REJECTED_MOC)
    assert result["total_approved"] == 0
    assert result["total_skipped"] == 1
    assert result["skipped"][0]["id"] == "MOC01"
    assert result["skipped"][0]["disposition"] == "rejected"


def test_multi_moc_mixed_accept():
    result = parse_moc_proposal(MULTI_MOC)
    assert result["total_sections"] == 3
    assert result["total_approved"] == 2
    assert result["total_skipped"] == 1

    ids = [c["id"] for c in result["confirmed_items"]]
    assert "MOC01" in ids
    assert "MOC03" in ids
    assert "MOC02" not in ids


def test_multi_moc_override_false():
    result = parse_moc_proposal(MULTI_MOC)
    first = next(c for c in result["confirmed_items"] if c["id"] == "MOC01")
    assert first["override_preserve_existing_up"] is False


def test_multi_moc_parent_from_wikilink():
    result = parse_moc_proposal(MULTI_MOC)
    third = next(c for c in result["confirmed_items"] if c["id"] == "MOC03")
    assert third["parent_moc"] == "Some Parent"


def test_no_parent_means_empty():
    result = parse_moc_proposal(MULTI_MOC)
    first = next(c for c in result["confirmed_items"] if c["id"] == "MOC01")
    assert first["parent_moc"] == ""
    assert first["parent_mocs"] == []


def test_daily_updates_always_empty():
    result = parse_moc_proposal(MINIMAL_PROPOSAL)
    assert result["daily_updates"] == []


LINK_MEMBER_PROPOSAL = MINIMAL_PROPOSAL.replace(
    "- [ ] `[[Note C]]` (kein up:: bisher)\n",
    "- [ ] `[[Note C]]` (kein up:: bisher)\n"
    "- [x] [[Linked Ticked]] (no up:: yet) — linked with [[Note A]], [[Note B]]\n"
    "- [ ] [[Linked Unticked]] (no up:: yet) — linked with [[Note A]], [[Note B]]\n",
)


def test_ticked_link_line_is_supporting_item():
    assert "Linked Ticked" in LINK_MEMBER_PROPOSAL
    stems = parse_moc_proposal(LINK_MEMBER_PROPOSAL)["confirmed_items"][0]["supporting_items"]
    assert "Linked Ticked" in stems
    assert "Note A" in stems and "Note B" in stems
    # the bridges after the marker are not read as members
    assert stems.count("Note A") == 1


def test_unticked_link_line_is_not_supporting_item():
    stems = parse_moc_proposal(LINK_MEMBER_PROPOSAL)["confirmed_items"][0]["supporting_items"]
    assert "Linked Unticked" not in stems


# ── Extension sections (spec 042 T4.3, SDD ADR-5) ────────────────────────────

EXTEND_SECTION = """\
### MOC01 — Extend [[Health MOC]]
- [{accept}] Accept
**Extends:** [[Health MOC]]
**Trigger:** around:Health MOC
#### Missing members (2)
- [{cold}] [[Cold Showers]] (no up:: yet) — linked with [[Health MOC]]
- [{sleep}] [[Sleep Debt]] (existing up:: [[Psychology MOC]] → becomes `related::`) — linked with [[Health MOC]]
#### up::-Handling Override
- [{override}] **Keep existing up::, add [[Health MOC]] as `related::`** (applies to all ticked members)
#### Why this proposal
2 notes link with [[Health MOC]] but have no up:: to it.
"""

EXTEND_FRONTMATTER = """\
---
type: tomo-proposal
proposal_kind: moc-extension
tomo:
  doc_type: moc-proposal
  state: pending-accept
---

# MOC Proposal

"""


def _extension_doc(accept=" ", cold=" ", sleep=" ", override=" ") -> str:
    return EXTEND_FRONTMATTER + EXTEND_SECTION.format(
        accept=accept, cold=cold, sleep=sleep, override=override,
    )


def test_accepted_extension_is_extend_moc_with_only_its_fields():
    result = parse_moc_proposal(_extension_doc(accept="x", sleep="x", override="x"))

    assert result["confirmed_items"] == [{
        "id": "MOC01",
        "action": "extend_moc",
        "target_moc": "Health MOC",
        "supporting_items": ["Sleep Debt"],
        "override_preserve_existing_up": True,
        "source_path": None,
    }]
    assert result["total_approved"] == 1
    assert result["skipped"] == []


def test_accepted_extension_without_override_keeps_it_false():
    item = parse_moc_proposal(
        _extension_doc(accept="x", cold="x", sleep="x"),
    )["confirmed_items"][0]

    assert item["supporting_items"] == ["Cold Showers", "Sleep Debt"]
    assert item["override_preserve_existing_up"] is False
    assert "template" not in item and "destination" not in item


def test_accepted_extension_with_zero_ticked_members_is_skipped_and_reported():
    result = parse_moc_proposal(_extension_doc(accept="x"))

    assert result["confirmed_items"] == []
    assert result["total_approved"] == 0
    assert result["total_skipped"] == 1
    skipped = result["skipped"][0]
    assert skipped["id"] == "MOC01"
    assert skipped["target_moc"] == "Health MOC"
    assert skipped["disposition"] == "no_ticked_members"
    assert skipped["reason"]


def test_zero_ticked_extension_is_reported_on_stderr(tmp_path, monkeypatch, capsys):
    doc = tmp_path / "2026-10-28_1810_moc-proposal-health-moc.md"
    doc.write_text(_extension_doc(accept="x"), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["moc-proposal-parser.py", "--file", str(doc)])

    assert _mod.main() == 0

    err = capsys.readouterr().err
    assert "MOC01" in err and "Health MOC" in err and "no ticked members" in err


def test_rejected_extension_is_skipped_as_rejected():
    result = parse_moc_proposal(_extension_doc(cold="x", sleep="x"))

    assert result["confirmed_items"] == []
    assert result["skipped"][0]["disposition"] == "rejected"
    assert result["skipped"][0]["target_moc"] == "Health MOC"


def test_extension_followed_by_new_moc_parses_as_two_blocks():
    new_moc = MINIMAL_PROPOSAL.split("# MOC Proposal\n", 1)[1].replace("MOC01", "MOC02")
    doc = _extension_doc(accept="x", cold="x") + "\n" + new_moc

    result = parse_moc_proposal(doc)

    assert result["total_sections"] == 2
    by_id = {c["id"]: c for c in result["confirmed_items"]}
    assert by_id["MOC01"]["action"] == "extend_moc"
    assert by_id["MOC01"]["supporting_items"] == ["Cold Showers"]
    assert by_id["MOC02"]["action"] == "create_moc"
    assert by_id["MOC02"]["supporting_items"] == ["Note A", "Note B"]
