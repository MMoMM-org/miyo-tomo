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
    stems = item["supporting_items"].split(", ")
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
