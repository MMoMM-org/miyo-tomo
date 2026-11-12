#!/usr/bin/env python3
# version: 0.3.1
"""test_review_state.py — lib/review_state.py, the one owner of /review's
open-review states (spec 045 T2.3, T4.3, P5; SDD Complex Logic review_state; ADR-6).

- STATES is the canonical six-state list in the SDD's order; review_state
  returns one of them or None (not listed), nothing else
- review_state, in the implemented order: meta.withdrawn → None, BEFORE the
  begun-delivery reading (coordinator 2026-11-12); an emptied set (actions
  == [], what drop writes) → None on a stem whose delivery never began, but
  failed-delivery on a begun stem meta does not call withdrawn (a drop whose
  MD write failed; owner decision P5: listed again, Resume or Drop); a begun
  delivery (ReviewMeta.started(): a step done or in flight) without doc_mark
  → failed-delivery, also with
  steps_done ["note"] and no failed_step; approved without a set JSON →
  failed-delivery; pending without a set → open; every action applied →
  applied; an unapplied move_note whose source (inbox copy) and destination
  (target) both exist → move-refused; an unapplied insert/replace whose
  target is gone → target-missing; otherwise delivered; an unreadable set
  reads delivered; a missing or corrupt meta counts as absent
- stem_state: the one probe-and-classify step both scripts call — reads
  <inbox>/<stem>_instructions.json through Kado only for an approved
  document (a pending one costs no read), probes the move's source first and
  its destination only while the source exists, the insert's target_path,
  nothing for an applied or withdrawn set; "absent" only on
  KadoNotFoundError — an auth error stops as kado-auth, any other Kado error
  as kado-unreachable, never as absent
- safe_stem: the one stem guard (T3.8) — a plain folder name passes; empty,
  whitespace, ".", "..", or anything carrying "/" or "\\" is refused
- read_meta: the content-free meta.json of a stem, None when missing or broken
  AND None for an unsafe stem — "." never reads <root>/meta.json
- open_reviews: one entry per review document found by frontmatter (renamed
  documents included), stem from review_stem or <period>_review, classified
  through stem_state (the fake records the set paths asked for), ordered by
  period start under the configured rule AND name formats, a missing
  review_kind inferred by parsing the period under the configured formats,
  unreadable, period-less and stem-unsafe documents skipped with a reason,
  withdrawn reviews and applied reviews already reported never listed
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from review_fake_vault import ReviewFakeVault  # noqa: E402
from lib import review_state as rs  # noqa: E402
from lib.kado_client import KadoAuthError, KadoConnectionError, KadoToolError  # noqa: E402
from lib.period import WeekRule  # noqa: E402
from lib.review_vault import Stopped, Vault  # noqa: E402

INBOX = "100 Inbox/"
STEM = "2026-W13_review"
SET = INBOX + STEM + "_instructions.json"
TARGET = "Calendar/2026-W13.md"
COPY = INBOX + "2026-W13.md"
PENDING, APPROVED = "pending-approval", "approved"


def _doc(period: str, kind: str, state: str = PENDING, stem: str | None = None) -> dict:
    fm = {"tomo": {"doc_type": "review", "state": state, "run_id": "r1", "updated_at": "2026-11-11T10:00:00"},
          "review_period": period, "review_kind": kind, "review_target": f"Calendar/{period}.md",
          "review_target_exists": True, "review_language": "de"}
    if stem is not None:
        fm["review_stem"] = stem
    return fm


def _meta(root: Path, stem: str, **fields) -> None:
    stage = root / stem
    stage.mkdir(parents=True)
    (stage / "meta.json").write_text(json.dumps({"stem": stem, **fields}), encoding="utf-8")


def _move(applied: bool = False, source: str = COPY, destination: str = TARGET) -> dict:
    return {"id": "I01", "action": "move_note", "source": source, "destination": destination,
            "title": "2026-W13", "rendered_file": "2026-W13.md", "source_inbox_item": None, "applied": applied}


def _insert(applied: bool = False, action: str = "insert_under_marker", target: str = TARGET) -> dict:
    return {"id": "I01", "action": action, "target_path": target, "anchor": {"type": "heading", "value": "X"},
            "placement": "before", "content": "## Tomo Review\n", "applied": applied}


def _set(*actions) -> dict:
    return {"schema_version": "3.0.0", "type": "tomo-instructions", "generated": "2026-11-11T10:00:00Z",
            "profile": "miyo", "md_peer": STEM + "_instructions", "actions": list(actions)}


def _set_bytes(*actions) -> bytes:
    return (json.dumps(_set(*actions)) + "\n").encode("utf-8")


def _vault(files: dict | None = None) -> tuple[Vault, ReviewFakeVault]:
    fake = ReviewFakeVault(files or {})
    return Vault(fake), fake


def _empty_vault() -> Vault:
    return _vault()[0]


def _probes(fake: ReviewFakeVault) -> list:
    return [(m, p) for m, p in fake.events if m in ("read_file", "read_frontmatter", "read_note", "path_exists")]


# ---------------------------------------------------------------- the canonical list

def test_states_are_the_sdd_list_in_order():
    assert rs.STATES == ("open", "failed-delivery", "delivered", "applied", "move-refused", "target-missing")
    assert rs.OPEN == "open" and rs.FAILED_DELIVERY == "failed-delivery" and rs.DELIVERED == "delivered"
    assert rs.APPLIED == "applied" and rs.MOVE_REFUSED == "move-refused" and rs.TARGET_MISSING == "target-missing"


# ---------------------------------------------------------------- safe_stem

@pytest.mark.parametrize("stem", ["2026-W13_review", "2026-03_review", "custom_review", "a.b", "x"])
def test_safe_stem_accepts_a_plain_folder_name(stem):
    assert rs.safe_stem(stem) is True


@pytest.mark.parametrize("stem", ["", " ", "\t", ".", "..", "a/b", "/a", "a\\b", "..\\x", "../x", "a..b", "./a"])
def test_safe_stem_refuses_what_is_not_a_folder_under_the_root(stem):
    assert rs.safe_stem(stem) is False


def test_read_meta_refuses_an_unsafe_stem_and_never_reads_the_root(tmp_path):
    # RED when read_meta joins the stem without the guard: "." resolves to <root>/meta.json and
    # ".." to the parent's, both of which exist here and carry a failed_step
    (tmp_path / "root").mkdir()
    (tmp_path / "root" / "meta.json").write_text(json.dumps({"failed_step": "root-level"}), encoding="utf-8")
    (tmp_path / "meta.json").write_text(json.dumps({"failed_step": "parent-level"}), encoding="utf-8")
    _meta(tmp_path / "root", "2026-W13_review", failed_step="set_md")
    assert rs.read_meta(tmp_path / "root", ".") is None
    assert rs.read_meta(tmp_path / "root", "..") is None
    assert rs.read_meta(tmp_path / "root", "") is None
    assert rs.read_meta(tmp_path / "root", "2026-W13_review/../..") is None
    assert rs.read_meta(tmp_path / "root", "2026-W13_review") == {"stem": "2026-W13_review", "failed_step": "set_md"}


# ---------------------------------------------------------------- review_state: steps 1 and 2

def test_failed_step_in_meta_is_failed_delivery():
    assert rs.review_state(_doc("2026-W13", "week"), {"failed_step": "set_md"}) == "failed-delivery"
    assert rs.review_state(_doc("2026-W13", "week", APPROVED), {"failed_step": "note"}) == "failed-delivery"


def test_approved_without_a_set_json_is_failed_delivery():
    assert rs.review_state(_doc("2026-W13", "week", APPROVED), None) == "failed-delivery"
    assert rs.review_state(_doc("2026-W13", "week", APPROVED), {"steps_done": []}) == "failed-delivery"


def test_pending_approval_without_a_set_json_is_open():
    assert rs.review_state(_doc("2026-W13", "week"), None) == "open"
    assert rs.review_state(_doc("2026-W13", "week"), {"steps_done": [], "failed_step": None}) == "open"
    assert rs.review_state({"review_period": "2026-03"}, None) == "open"      # no tomo block at all


def test_begun_delivery_without_failed_step_is_failed_delivery_not_open():
    """Falsifies step 1 reading `failed_step` alone (the SDD's wording): a kill after `record(note)`
    and before the in-flight mark of set_json leaves steps_done ["note"] and failed_step "" — a
    begun delivery (`ReviewMeta.started()`), coordinator decision 2026-11-12."""
    begun = {"steps_done": ["note"], "failed_step": ""}
    assert rs.review_state(_doc("2026-W13", "week"), begun) == "failed-delivery"
    assert rs.review_state(_doc("2026-W13", "week"), begun, _set(_move())) == "failed-delivery"
    assert rs.review_state(_doc("2026-W13", "week"), begun, _set(_move(True))) == "failed-delivery"
    # a delivery in flight at the mark, the mark landed unrecorded: still failed-delivery
    assert rs.review_state(_doc("2026-W13", "week", APPROVED), {"steps_done": ["set_json", "set_md"],
                                                               "failed_step": "doc_mark"},
                           _set(_move())) == "failed-delivery"
    # a complete delivery (doc_mark recorded) is read from the set, not from the meta
    done = {"steps_done": ["note", "set_json", "set_md", "doc_mark"], "failed_step": ""}
    assert rs.review_state(_doc("2026-W13", "week", APPROVED), done, _set(_move())) == "delivered"
    assert rs.review_state(_doc("2026-W13", "week", APPROVED), done, _set(_move(True))) == "applied"


def test_failed_step_wins_over_a_set_json_that_is_not_withdrawn():
    assert rs.review_state(_doc("2026-W13", "week", APPROVED), {"failed_step": "doc_mark"},
                           _set(_insert(True))) == "failed-delivery"


# ---------------------------------------------------------------- review_state: step 3 first

def test_withdrawn_is_tested_before_the_begun_delivery_reading():
    """Falsifies the SDD's step order (1 before 3): after `drop`, meta keeps steps_done and
    withdrawn: true — read as a begun delivery first, every dropped review would be
    failed-delivery forever. Coordinator decision 2026-11-12: withdrawn first, never listed."""
    dropped = {"steps_done": ["note", "set_json"], "failed_step": "", "withdrawn": True}
    assert rs.review_state(_doc("2026-W13", "week"), dropped) is None
    assert rs.review_state(_doc("2026-W13", "week", APPROVED), dropped) is None
    assert rs.review_state(_doc("2026-W13", "week", APPROVED), dropped, _set()) is None
    # the set Tomo wrote over a delivered one, with no begun record to contradict it: withdrawn
    assert rs.review_state(_doc("2026-W13", "week", APPROVED), None, _set()) is None
    assert rs.review_state(_doc("2026-W13", "week", APPROVED), {}, _set()) is None
    assert rs.review_state(_doc("2026-W13", "week", APPROVED), {"withdrawn": True}, _set(_move(True))) is None
    # withdrawn: false is not withdrawn
    assert rs.review_state(_doc("2026-W13", "week"), {"withdrawn": False}) == "open"


# ---------------------------------------------------------------- review_state: a drop that did not finish

@pytest.mark.parametrize("meta", [
    {"steps_done": ["set_json"], "failed_step": "set_md"},                              # deliver died at set_md
    {"steps_done": ["note"], "failed_step": "set_json", "withdrawn": False},             # the set was in flight
    {"steps_done": ["set_json", "set_md", "doc_mark"], "failed_step": ""},                # a complete delivery
    {"failed_step": "doc_mark"},
], ids=["set_md-failed", "set_json-in-flight", "complete", "doc_mark-failed"])
def test_an_emptied_set_on_a_begun_stem_not_marked_withdrawn_is_failed_delivery(meta):
    """Falsifies `actions == []` alone meaning withdrawn: `drop` writes the empty set first and marks
    meta.json last, so a drop whose MD write failed leaves the set empty, the MD listing the actions and
    the meta unmarked. Owner decision (spec 045 P5): only meta.withdrawn withdraws; such a stem is a
    begun-but-unfinished delivery, listed again so the next /review offers Resume or Drop."""
    assert rs.review_state(_doc("2026-W13", "week", APPROVED), meta, _set()) == "failed-delivery"
    assert rs.review_state(_doc("2026-W13", "week", APPROVED), dict(meta, withdrawn=True), _set()) is None


def test_is_emptied_set_is_the_withdrawal_signature_only():
    assert rs.is_emptied_set(_set()) is True
    assert rs.is_emptied_set({"actions": []}) is True
    for not_emptied in (None, {}, {"actions": None}, {"actions": "nope"}, {"actions": ["nope"]}, _set(_move())):
        assert rs.is_emptied_set(not_emptied) is False


# ---------------------------------------------------------------- review_state: steps 4-7

def test_every_action_applied_is_applied():
    assert rs.review_state(_doc("2026-W13", "week", APPROVED), None, _set(_move(True))) == "applied"
    assert rs.review_state(_doc("2026-W13", "week", APPROVED), {"steps_done": ["set_json", "set_md", "doc_mark"]},
                           _set(_insert(True), _insert(True, "replace_section"))) == "applied"
    # one unapplied action is enough to wait
    assert rs.review_state(_doc("2026-W13", "week", APPROVED), None, _set(_insert(True), _insert(False)),
                           target_exists=True) == "delivered"
    # applied must be exactly True
    assert rs.review_state(_doc("2026-W13", "week", APPROVED), None, _set(dict(_insert(), applied="yes")),
                           target_exists=True) == "delivered"


def test_a_fresh_record_over_a_fully_applied_set_reads_open_and_all_applied_needs_an_action():
    """Owner decision 2026-11-12 (T6.1 fix round): after `replace --confirm` the rerun's fresh meta sits beside
    the first run's applied set; it reads `open`, never `applied`, or the listing would report it once and drop
    the approved document. Only a present record that never began counts: meta None stays `applied` (a cleaned
    stage), a begun or complete record keeps its reading."""
    doc = _doc("2026-W13", "week", APPROVED)
    fresh = {"steps_done": [], "failed_step": "", "withdrawn": False}
    assert rs.review_state(doc, fresh, _set(_move(True))) == "open"
    assert rs.review_state(doc, fresh, _set(_insert(True), _insert(True, "replace_section"))) == "open"
    assert rs.review_state(doc, None, _set(_move(True))) == "applied"
    assert rs.review_state(doc, {"steps_done": ["set_json", "set_md", "doc_mark"]}, _set(_move(True))) == "applied"
    assert rs.review_state(doc, {"steps_done": ["set_json"]}, _set(_move(True))) == "failed-delivery"
    assert rs.review_state(doc, fresh, _set(_insert(True), _insert(False)), target_exists=True) == "delivered"
    assert rs.all_applied(_set(_move(True))) is True and rs.all_applied(_set(_insert(True), _insert(True))) is True
    for not_applied in (None, {}, {"actions": []}, {"actions": ["nope"]}, _set(_move()), _set(_move(True), _move()),
                        _set(dict(_insert(), applied="yes"))):
        assert rs.all_applied(not_applied) is False, not_applied


def test_move_refused_when_the_target_and_the_inbox_copy_both_exist():
    doc = _doc("2026-W13", "week", APPROVED)
    assert rs.review_state(doc, None, _set(_move()), target_exists=True, inbox_copy_exists=True) == "move-refused"
    assert rs.review_state(doc, None, _set(_move()), target_exists=True, inbox_copy_exists=False) == "delivered"
    assert rs.review_state(doc, None, _set(_move()), target_exists=False, inbox_copy_exists=True) == "delivered"
    assert rs.review_state(doc, None, _set(_move()), target_exists=None, inbox_copy_exists=None) == "delivered"
    # an applied move is never refused, whatever the probes say
    assert rs.review_state(doc, None, _set(_move(True)), target_exists=True, inbox_copy_exists=True) == "applied"


def test_target_missing_when_the_insert_or_replace_target_is_gone():
    doc = _doc("2026-W13", "week", APPROVED)
    assert rs.review_state(doc, None, _set(_insert()), target_exists=False) == "target-missing"
    assert rs.review_state(doc, None, _set(_insert(action="replace_section")), target_exists=False) == "target-missing"
    assert rs.review_state(doc, None, _set(_insert()), target_exists=True) == "delivered"
    assert rs.review_state(doc, None, _set(_insert()), target_exists=None) == "delivered"
    # a move whose target is gone is not target-missing (step 6 is for insert and replace)
    assert rs.review_state(doc, None, _set(_move()), target_exists=False, inbox_copy_exists=True) == "delivered"


def test_an_unreadable_set_reads_delivered_never_applied_or_withdrawn():
    doc = _doc("2026-W13", "week", APPROVED)
    assert rs.review_state(doc, None, {"actions": "nope"}) == "delivered"
    assert rs.review_state(doc, None, {"actions": ["nope"]}) == "delivered"
    assert rs.review_state(doc, None, {}) == "delivered"
    assert rs.review_state(doc, None, {"actions": None}) == "delivered"


@pytest.mark.parametrize("doc_state", [PENDING, APPROVED])
@pytest.mark.parametrize("meta", [None, {}, {"steps_done": ["note"]}, {"failed_step": "set_md"}, {"withdrawn": True},
                                  {"steps_done": ["note", "set_json", "set_md", "doc_mark"]}])
@pytest.mark.parametrize("set_json", [None, _set(), _set(_move()), _set(_move(True)), _set(_insert()),
                                      _set(_insert(True)), {"actions": 3}])
@pytest.mark.parametrize("probes", [(None, None), (True, True), (True, False), (False, True), (False, False)])
def test_review_state_returns_a_canonical_state_or_none(doc_state, meta, set_json, probes):
    state = rs.review_state(_doc("2026-W13", "week", doc_state), meta, set_json,
                            target_exists=probes[0], inbox_copy_exists=probes[1])
    assert state is None or state in rs.STATES


# ---------------------------------------------------------------- stem_state: the probes

def test_stem_state_reads_the_set_json_of_an_approved_document_only():
    vault, fake = _vault({SET: _set_bytes(_move(True))})
    assert rs.stem_state(vault, _doc("2026-W13", "week", APPROVED), None, STEM, INBOX) == "applied"
    assert _probes(fake) == [("read_file", SET)]
    fake.events.clear()
    assert rs.stem_state(vault, _doc("2026-W13", "week", PENDING), None, STEM, INBOX) == "open"
    assert _probes(fake) == []                                   # a pending document costs no read
    fake.events.clear()
    begun = {"steps_done": ["note"], "failed_step": ""}
    assert rs.stem_state(vault, _doc("2026-W13", "week", PENDING), begun, STEM, INBOX) == "failed-delivery"
    assert _probes(fake) == []                                   # step 1 from the meta alone


def test_stem_state_absent_set_is_failed_delivery_only_on_not_found():
    vault, fake = _vault({})
    assert rs.stem_state(vault, _doc("2026-W13", "week", APPROVED), None, STEM, INBOX) == "failed-delivery"
    assert _probes(fake) == [("read_file", SET)]

    vault, fake = _vault({})
    fake.fail[("read_file", SET)] = KadoAuthError("401 key refused")
    with pytest.raises(Stopped) as stop:
        rs.stem_state(vault, _doc("2026-W13", "week", APPROVED), None, STEM, INBOX)
    assert stop.value.kind == "kado-auth"

    vault, fake = _vault({})
    fake.fail[("read_file", SET)] = KadoToolError("kado-read returned an error: FORBIDDEN")
    with pytest.raises(Stopped) as stop:
        rs.stem_state(vault, _doc("2026-W13", "week", APPROVED), None, STEM, INBOX)
    assert stop.value.kind == "kado-unreachable"

    vault, fake = _vault({})
    fake.connection_error = KadoConnectionError("Kado unreachable")
    with pytest.raises(Stopped) as stop:
        rs.stem_state(vault, _doc("2026-W13", "week", APPROVED), None, STEM, INBOX)
    assert stop.value.kind == "kado-unreachable"


def test_stem_state_probes_the_move_source_first_and_the_destination_only_while_it_exists():
    doc = _doc("2026-W13", "week", APPROVED)
    # both present: the refusal Hashi leaves behind
    vault, fake = _vault({SET: _set_bytes(_move()), COPY: "# copy\n", TARGET: "# target\n"})
    assert rs.stem_state(vault, doc, None, STEM, INBOX) == "move-refused"
    assert _probes(fake) == [("read_file", SET), ("read_frontmatter", COPY), ("read_frontmatter", TARGET)]
    # the copy is gone: delivered, the destination is not probed
    vault, fake = _vault({SET: _set_bytes(_move()), TARGET: "# target\n"})
    assert rs.stem_state(vault, doc, None, STEM, INBOX) == "delivered"
    assert _probes(fake) == [("read_file", SET), ("read_frontmatter", COPY)]
    # the copy waits, the destination is not there yet: delivered
    vault, fake = _vault({SET: _set_bytes(_move()), COPY: "# copy\n"})
    assert rs.stem_state(vault, doc, None, STEM, INBOX) == "delivered"
    assert _probes(fake) == [("read_file", SET), ("read_frontmatter", COPY), ("read_frontmatter", TARGET)]
    # a denied probe never reads as absent
    vault, fake = _vault({SET: _set_bytes(_move()), COPY: "# copy\n"})
    fake.fail[("read_frontmatter", TARGET)] = KadoAuthError("401")
    with pytest.raises(Stopped) as stop:
        rs.stem_state(vault, doc, None, STEM, INBOX)
    assert stop.value.kind == "kado-auth"


def test_stem_state_probes_the_insert_target_and_nothing_for_an_applied_set():
    doc = _doc("2026-W13", "week", APPROVED)
    vault, fake = _vault({SET: _set_bytes(_insert()), TARGET: "# target\n"})
    assert rs.stem_state(vault, doc, None, STEM, INBOX) == "delivered"
    assert _probes(fake) == [("read_file", SET), ("read_frontmatter", TARGET)]
    vault, fake = _vault({SET: _set_bytes(_insert(action="replace_section"))})
    assert rs.stem_state(vault, doc, None, STEM, INBOX) == "target-missing"
    assert _probes(fake) == [("read_file", SET), ("read_frontmatter", TARGET)]
    vault, fake = _vault({SET: _set_bytes(_insert(True)), TARGET: "# target\n"})
    assert rs.stem_state(vault, doc, None, STEM, INBOX) == "applied"
    assert _probes(fake) == [("read_file", SET)]


def test_stem_state_withdrawn_costs_no_probe_and_an_unreadable_set_is_delivered():
    doc = _doc("2026-W13", "week", APPROVED)
    vault, fake = _vault({SET: _set_bytes(_move(True))})
    assert rs.stem_state(vault, doc, {"withdrawn": True, "steps_done": ["set_json"]}, STEM, INBOX) is None
    assert _probes(fake) == []
    vault, fake = _vault({SET: _set_bytes()})
    assert rs.stem_state(vault, doc, None, STEM, INBOX) is None
    assert _probes(fake) == [("read_file", SET)]
    # the emptied set on a begun stem that meta does not call withdrawn: a drop that did not finish
    vault, fake = _vault({SET: _set_bytes()})
    assert rs.stem_state(vault, doc, {"steps_done": ["set_json", "set_md", "doc_mark"]}, STEM, INBOX) == "failed-delivery"
    assert _probes(fake) == [("read_file", SET)]
    vault, fake = _vault({SET: b"{not json"})
    assert rs.stem_state(vault, doc, None, STEM, INBOX) == "delivered"
    vault, fake = _vault({SET: b"[1, 2]"})
    assert rs.stem_state(vault, doc, None, STEM, INBOX) == "delivered"
    assert _probes(fake) == [("read_file", SET)]


# ---------------------------------------------------------------- read_meta

def test_read_meta_returns_the_meta_or_none(tmp_path):
    _meta(tmp_path, "2026-W13_review", failed_step="set_md", steps_done=["note"])
    assert rs.read_meta(tmp_path, "2026-W13_review") == {"stem": "2026-W13_review", "failed_step": "set_md",
                                                         "steps_done": ["note"]}
    assert rs.read_meta(tmp_path, "2026-W12_review") is None
    (tmp_path / "2026-W11_review").mkdir()
    (tmp_path / "2026-W11_review" / "meta.json").write_text("{not json", encoding="utf-8")
    assert rs.read_meta(tmp_path, "2026-W11_review") is None
    (tmp_path / "2026-W10_review").mkdir()
    (tmp_path / "2026-W10_review" / "meta.json").write_text("[1, 2]", encoding="utf-8")
    assert rs.read_meta(tmp_path, "2026-W10_review") is None


def test_read_meta_refuses_a_stem_that_leaves_the_root(tmp_path):
    assert rs.read_meta(tmp_path, "../etc") is None
    assert rs.read_meta(tmp_path, "a/b") is None
    assert rs.read_meta(tmp_path, "") is None


# ---------------------------------------------------------------- open_reviews

def test_open_reviews_lists_every_document_by_period_with_its_state(tmp_path):
    _meta(tmp_path, "2026-W12_review", failed_step="set_md")
    docs = [
        (INBOX + "2026-W13 Review.md", _doc("2026-W13", "week", stem="2026-W13_review")),
        (INBOX + "My renamed review.md", _doc("2026-W12", "week", APPROVED, stem="2026-W12_review")),
        (INBOX + "2026-03 Review.md", _doc("2026-03", "month", APPROVED, stem="2026-03_review")),
        (INBOX + "2026-W09 Review.md", _doc("2026-W09", "week")),           # no review_stem key
    ]
    reviews, skipped = rs.open_reviews(docs, tmp_path, _empty_vault(), INBOX)
    assert skipped == []
    assert [r.to_dict() for r in reviews] == [
        {"period": "2026-W09", "kind": "week", "doc_path": INBOX + "2026-W09 Review.md",
         "stem": "2026-W09_review", "state": "open"},
        {"period": "2026-03", "kind": "month", "doc_path": INBOX + "2026-03 Review.md",
         "stem": "2026-03_review", "state": "failed-delivery"},
        {"period": "2026-W12", "kind": "week", "doc_path": INBOX + "My renamed review.md",
         "stem": "2026-W12_review", "state": "failed-delivery"},
        {"period": "2026-W13", "kind": "week", "doc_path": INBOX + "2026-W13 Review.md",
         "stem": "2026-W13_review", "state": "open"},
    ]


def test_open_reviews_probes_the_set_of_every_approved_document_and_lists_a_delivered_one(tmp_path):
    """Falsifies a listing that classifies without the probe: the approved, delivered review would
    read failed-delivery, and the fake would record no read of its set."""
    _meta(tmp_path, "2026-W12_review", steps_done=["set_json", "set_md", "doc_mark"], failed_step="")
    vault, fake = _vault({INBOX + "2026-W12_review_instructions.json": _set_bytes(_insert(target="Calendar/2026-W12.md")),
                          "Calendar/2026-W12.md": "# W12\n",
                          INBOX + "2026-W11_review_instructions.json": _set_bytes(_move(True))})
    docs = [
        (INBOX + "2026-W13 Review.md", _doc("2026-W13", "week", PENDING, stem="2026-W13_review")),
        (INBOX + "2026-W12 Review.md", _doc("2026-W12", "week", APPROVED, stem="2026-W12_review")),
        (INBOX + "2026-W11 Review.md", _doc("2026-W11", "week", APPROVED, stem="2026-W11_review")),
        (INBOX + "2026-W10 Review.md", _doc("2026-W10", "week", APPROVED, stem="2026-W10_review")),
    ]
    reviews, skipped = rs.open_reviews(docs, tmp_path, vault, INBOX)
    assert skipped == []
    assert [(r.period, r.state) for r in reviews] == [("2026-W10", "failed-delivery"), ("2026-W11", "applied"),
                                                      ("2026-W12", "delivered"), ("2026-W13", "open")]
    set_reads = [p for m, p in fake.events if m == "read_file"]
    assert sorted(set_reads) == sorted([INBOX + "2026-W12_review_instructions.json",
                                        INBOX + "2026-W11_review_instructions.json",
                                        INBOX + "2026-W10_review_instructions.json"])
    assert INBOX + "2026-W13_review_instructions.json" not in fake.paths_seen      # pending: no probe
    assert "Calendar/2026-W12.md" in fake.paths_seen                                 # the waiting insert's target


def test_open_reviews_never_lists_a_withdrawn_review_nor_an_applied_one_already_reported(tmp_path):
    _meta(tmp_path, "2026-W12_review", steps_done=["note", "set_json"], failed_step="", withdrawn=True)
    _meta(tmp_path, "2026-W11_review", steps_done=["set_json", "set_md", "doc_mark"], applied_reported=True)
    _meta(tmp_path, "2026-W10_review", steps_done=["set_json", "set_md", "doc_mark"])
    vault, fake = _vault({INBOX + "2026-W12_review_instructions.json": _set_bytes(_move()),
                          INBOX + "2026-W11_review_instructions.json": _set_bytes(_insert(True)),
                          INBOX + "2026-W10_review_instructions.json": _set_bytes(_insert(True)),
                          INBOX + "2026-W09_review_instructions.json": _set_bytes()})
    docs = [
        (INBOX + "2026-W12 Review.md", _doc("2026-W12", "week", APPROVED, stem="2026-W12_review")),
        (INBOX + "2026-W11 Review.md", _doc("2026-W11", "week", APPROVED, stem="2026-W11_review")),
        (INBOX + "2026-W10 Review.md", _doc("2026-W10", "week", APPROVED, stem="2026-W10_review")),
        (INBOX + "2026-W09 Review.md", _doc("2026-W09", "week", APPROVED, stem="2026-W09_review")),
    ]
    reviews, skipped = rs.open_reviews(docs, tmp_path, vault, INBOX)
    assert skipped == []
    assert [(r.period, r.state) for r in reviews] == [("2026-W10", "applied")]
    assert INBOX + "2026-W12_review_instructions.json" not in fake.paths_seen      # withdrawn meta: no probe


def test_open_reviews_lists_a_half_withdrawn_stem_as_failed_delivery_until_meta_says_withdrawn(tmp_path):
    """`drop` emptied the set but its MD write failed: the set holds nothing, the MD lists the actions,
    meta.json is not marked. The listing offers it again (Resume or Drop) instead of hiding it."""
    _meta(tmp_path, "2026-W12_review", steps_done=["note", "set_json"], failed_step="set_md", withdrawn=False)
    _meta(tmp_path, "2026-W11_review", steps_done=["note", "set_json"], failed_step="set_md", withdrawn=True)
    vault, fake = _vault({INBOX + "2026-W12_review_instructions.json": _set_bytes(),
                          INBOX + "2026-W11_review_instructions.json": _set_bytes()})
    docs = [
        (INBOX + "2026-W12 Review.md", _doc("2026-W12", "week", APPROVED, stem="2026-W12_review")),
        (INBOX + "2026-W11 Review.md", _doc("2026-W11", "week", APPROVED, stem="2026-W11_review")),
    ]
    reviews, skipped = rs.open_reviews(docs, tmp_path, vault, INBOX)
    assert skipped == []
    assert [(r.period, r.state) for r in reviews] == [("2026-W12", "failed-delivery")]
    assert [p for m, p in fake.events if m == "read_file"] == [INBOX + "2026-W12_review_instructions.json"]


def test_open_reviews_skips_an_unsafe_stem_never_classifying_it_as_meta_absent(tmp_path):
    (tmp_path / "meta.json").write_text(json.dumps({"failed_step": "x"}), encoding="utf-8")
    vault, fake = _vault({})
    docs = [
        (INBOX + "a.md", _doc("2026-W13", "week", stem="../x")),
        (INBOX + "b.md", _doc("2026-W12", "week", APPROVED, stem="..")),
        (INBOX + "c.md", _doc("2026/W11", "week")),                              # no stem key: period unsafe
        (INBOX + "d.md", _doc("2026-W10", "week", stem="2026-W10_review")),
    ]
    reviews, skipped = rs.open_reviews(docs, tmp_path, vault, INBOX)
    assert [r.stem for r in reviews] == ["2026-W10_review"]
    assert skipped == [{"doc_path": INBOX + "a.md", "reason": "stem-unsafe"},
                       {"doc_path": INBOX + "b.md", "reason": "stem-unsafe"},
                       {"doc_path": INBOX + "c.md", "reason": "stem-unsafe"}]
    assert fake.events == []                                                     # nothing probed for them


def test_open_reviews_orders_by_the_configured_rule_and_formats_and_keeps_unparsable_last(tmp_path):
    # 2027-W01 under gggg-[W]ww + (Sunday, 1) starts 2026-12-27, before the month 2027-01
    # (2027-01-01); under the default GGGG-[W]WW the ISO rule applies whatever the rule
    # says and 2027-W01 starts 2027-01-04, after it — so the two orders differ.
    sunday = WeekRule(6, 1)
    docs = [
        (INBOX + "a.md", _doc("2027-W01", "week")),
        (INBOX + "b.md", _doc("2027-01", "month")),
        (INBOX + "c.md", _doc("2026-12", "month")),
        (INBOX + "d.md", _doc("not-a-period", "week")),
    ]
    reviews, skipped = rs.open_reviews(docs, tmp_path, _empty_vault(), INBOX, rule=sunday,
                                       formats={"week": "gggg-[W]ww"})
    assert [r.period for r in reviews] == ["2026-12", "2027-W01", "2027-01", "not-a-period"]
    assert skipped == []
    reviews, _ = rs.open_reviews(docs, tmp_path, _empty_vault(), INBOX)        # the defaults: ISO
    assert [r.period for r in reviews] == ["2026-12", "2027-01", "2027-W01", "not-a-period"]


def test_open_reviews_infers_a_missing_kind_by_parsing_under_the_configured_formats(tmp_path):
    sunday = WeekRule(6, 1)
    week_without_w = _doc("2027.01", "week")
    del week_without_w["review_kind"]
    month = _doc("2027-01", "month")
    del month["review_kind"]
    docs = [(INBOX + "a.md", week_without_w), (INBOX + "b.md", month), (INBOX + "c.md", _doc("2026-12", "month"))]
    reviews, _ = rs.open_reviews(docs, tmp_path, _empty_vault(), INBOX, rule=sunday, formats={"week": "gggg.ww"})
    assert [(r.period, r.kind) for r in reviews] == [("2026-12", "month"), ("2027.01", "week"), ("2027-01", "month")]
    reviews, _ = rs.open_reviews(docs, tmp_path, _empty_vault(), INBOX)        # no W, no format: the letter guess
    assert [(r.period, r.kind) for r in reviews] == [("2026-12", "month"), ("2027-01", "month"), ("2027.01", "month")]


def test_open_reviews_skips_unreadable_and_period_less_documents(tmp_path):
    docs = [
        (INBOX + "broken.md", None),
        (INBOX + "no period.md", {"tomo": {"doc_type": "review", "state": "pending-approval"}}),
        (INBOX + "2026-W13 Review.md", _doc("2026-W13", "week")),
    ]
    reviews, skipped = rs.open_reviews(docs, tmp_path, _empty_vault(), INBOX)
    assert [r.period for r in reviews] == ["2026-W13"]
    assert skipped == [{"doc_path": INBOX + "broken.md", "reason": "frontmatter-unreadable"},
                       {"doc_path": INBOX + "no period.md", "reason": "period-missing"}]
