#!/usr/bin/env python3
# version: 0.1.2
"""test_note_meta.py — Behavioural tests for lib.note_meta (spec 044 T1.3).

Covers the draft state owner for tomo-tmp/note/<stem>/meta.json:
- meta.json round trip and the derived names (destination_file, instructions_stem)
- steps_done updates (order, idempotence, unknown step rejected) and failed_step
- title and destination frozen once steps_done is non-empty, keep_source once
  instructions_json is done (SDD stage Rule)
- stage listing splits started deliveries (kept_drafts: failed_step set or
  steps_done non-empty) from stale stages
- read_meta rejects fields of the wrong type or shape (stale in the listing)
- error messages never echo the offending value
- stem validation guards every path built from a stem
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import note_meta  # noqa: E402
from lib.note_meta import NoteDraftMeta  # noqa: E402

STEM = "2026-11-04_101500"


def _meta(**overrides) -> NoteDraftMeta:
    fields = dict(
        stem=STEM,
        run_id="2026-11-04T10-15-00Z-abc123",
        created="2026-11-04T10:15:00Z",
        generated="2026-11-04T10:15:00Z",
        template="Templates/Meeting Notes.md",
        template_stem="Meeting Notes",
        source_path="100 Inbox/raw.md",
        inbox="100 Inbox",
        title="Weekly: sync",
        destination="Atlas/Notes/",
        default_destination="Atlas/Notes/",
    )
    fields.update(overrides)
    return note_meta.new_meta(**fields)


def _stage_with(root: Path, meta: NoteDraftMeta) -> Path:
    stage = note_meta.stage_dir(root, meta.stem)
    stage.mkdir(parents=True)
    note_meta.write_meta(stage, meta)
    return stage


# ── Round trip and derived names ─────────────────────────────────────────────


def test_meta_json_round_trip_keeps_every_field(tmp_path):
    meta = _meta()
    stage = _stage_with(tmp_path, meta)

    loaded = note_meta.read_meta(stage)

    assert loaded == meta
    raw = json.loads((stage / "meta.json").read_text(encoding="utf-8"))
    assert set(raw) == {
        "stem", "run_id", "created", "generated", "template", "template_stem",
        "source_path", "title", "inbox_file", "destination",
        "default_destination", "profile", "keep_source", "steps_done", "failed_step",
    }


def test_new_meta_defaults_keep_source_false_and_no_steps():
    meta = _meta()

    assert meta.keep_source is False
    assert meta.steps_done == []
    assert meta.failed_step == ""


def test_inbox_file_and_destination_file_use_the_sanitised_title():
    meta = _meta(title="Weekly: sync")

    assert meta.inbox_file == f"100 Inbox/{STEM}_Weekly- sync.md"
    assert meta.destination_file() == "Atlas/Notes/Weekly- sync.md"
    assert meta.instructions_stem() == f"{STEM}_instructions"


def test_destination_without_trailing_slash_is_normalised():
    meta = _meta(destination="Atlas/Notes", default_destination="Atlas/Notes")

    assert meta.destination == "Atlas/Notes/"
    assert meta.destination_file() == "Atlas/Notes/Weekly- sync.md"


def test_text_in_call_source_is_null_in_meta_json(tmp_path):
    stage = _stage_with(tmp_path, _meta(source_path=None))

    raw = json.loads((stage / "meta.json").read_text(encoding="utf-8"))

    assert raw["source_path"] is None
    assert note_meta.read_meta(stage).source_path is None


def test_read_meta_raises_on_broken_json(tmp_path):
    stage = note_meta.stage_dir(tmp_path, STEM)
    stage.mkdir(parents=True)
    (stage / "meta.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(note_meta.MetaError):
        note_meta.read_meta(stage)


# ── steps_done and failed_step ───────────────────────────────────────────────


def test_mark_step_done_records_steps_once_in_order():
    meta = _meta()

    note_meta.mark_step_done(meta, "note")
    note_meta.mark_step_done(meta, "instructions_json")
    note_meta.mark_step_done(meta, "note")

    assert meta.steps_done == ["note", "instructions_json"]


def test_mark_step_done_clears_a_failed_step_it_completes():
    meta = _meta()
    note_meta.mark_step_failed(meta, "instructions_json")

    note_meta.mark_step_done(meta, "instructions_json")

    assert meta.failed_step == ""


def test_unknown_step_is_rejected():
    meta = _meta()

    with pytest.raises(ValueError):
        note_meta.mark_step_done(meta, "upload")
    with pytest.raises(ValueError):
        note_meta.mark_step_failed(meta, "upload")


def test_steps_done_survive_a_round_trip(tmp_path):
    meta = _meta()
    note_meta.mark_step_done(meta, "note")
    note_meta.mark_step_failed(meta, "instructions_json")
    stage = _stage_with(tmp_path, meta)

    loaded = note_meta.read_meta(stage)

    assert loaded.steps_done == ["note"]
    assert loaded.failed_step == "instructions_json"


# ── Frozen title and destination ─────────────────────────────────────────────


def test_title_and_destination_change_freely_before_any_step():
    meta = _meta()

    frozen = note_meta.apply_stage_update(
        meta, title="Renamed", destination="Efforts/"
    )

    assert frozen is False
    assert meta.title == "Renamed"
    assert meta.destination == "Efforts/"
    assert meta.inbox_file == f"100 Inbox/{STEM}_Renamed.md"


def test_title_change_is_refused_once_a_step_is_done():
    meta = _meta()
    note_meta.mark_step_done(meta, "note")

    frozen = note_meta.apply_stage_update(meta, title="Renamed")

    assert frozen is True
    assert meta.title == "Weekly: sync"
    assert meta.inbox_file == f"100 Inbox/{STEM}_Weekly- sync.md"


def test_destination_change_is_refused_once_a_step_is_done():
    meta = _meta()
    note_meta.mark_step_done(meta, "note")

    frozen = note_meta.apply_stage_update(
        meta, destination="Efforts/", keep_source=True
    )

    assert frozen is True
    assert meta.destination == "Atlas/Notes/"
    assert meta.keep_source is False


def test_restating_the_frozen_values_is_not_a_change():
    meta = _meta()
    note_meta.mark_step_done(meta, "note")

    frozen = note_meta.apply_stage_update(
        meta, title="Weekly: sync", destination="Atlas/Notes"
    )

    assert frozen is False


def test_keep_source_changes_before_any_step():
    meta = _meta()

    note_meta.apply_stage_update(meta, keep_source=True)

    assert meta.keep_source is True


def test_keep_source_change_is_refused_once_the_instruction_set_landed():
    meta = _meta()
    note_meta.mark_step_done(meta, "note")
    note_meta.mark_step_done(meta, "instructions_json")
    before = NoteDraftMeta(**vars(meta) | {"steps_done": list(meta.steps_done)})

    frozen = note_meta.apply_stage_update(meta, keep_source=True)

    assert frozen is True
    assert meta == before


def test_keep_source_change_is_accepted_after_only_the_note_landed():
    meta = _meta()
    note_meta.mark_step_done(meta, "note")

    frozen = note_meta.apply_stage_update(meta, keep_source=True)

    assert frozen is False
    assert meta.keep_source is True


def test_restating_keep_source_after_the_instruction_set_is_not_a_change():
    meta = _meta()
    note_meta.mark_step_done(meta, "note")
    note_meta.mark_step_done(meta, "instructions_json")

    frozen = note_meta.apply_stage_update(
        meta, title="Weekly: sync", destination="Atlas/Notes/", keep_source=False
    )

    assert frozen is False
    assert meta.keep_source is False


def test_refused_title_change_leaves_keep_source_unchanged():
    meta = _meta()
    note_meta.mark_step_done(meta, "note")

    frozen = note_meta.apply_stage_update(meta, title="Renamed", keep_source=True)

    assert frozen is True
    assert meta.title == "Weekly: sync"
    assert meta.keep_source is False


# ── Stage listing ────────────────────────────────────────────────────────────


def test_listing_splits_failed_deliveries_from_stale_stages(tmp_path):
    failed = _meta(stem="2026-11-04_090000")
    note_meta.mark_step_done(failed, "note")
    note_meta.mark_step_failed(failed, "instructions_json")
    _stage_with(tmp_path, failed)
    _stage_with(tmp_path, _meta(stem="2026-11-04_100000"))

    listing = note_meta.list_stages(tmp_path)

    assert listing.kept_drafts == [{
        "stem": "2026-11-04_090000",
        "title": "Weekly: sync",
        "template": "Templates/Meeting Notes.md",
        "created": "2026-11-04T10:15:00Z",
        "failed_step": "instructions_json",
    }]
    assert listing.stale_stages == ["2026-11-04_100000"]


def test_stage_without_readable_meta_is_stale(tmp_path):
    (note_meta.stage_dir(tmp_path, "2026-11-04_080000")).mkdir(parents=True)
    broken = note_meta.stage_dir(tmp_path, "2026-11-04_081000")
    broken.mkdir(parents=True)
    (broken / "meta.json").write_text("{", encoding="utf-8")

    listing = note_meta.list_stages(tmp_path)

    assert listing.kept_drafts == []
    assert listing.stale_stages == ["2026-11-04_080000", "2026-11-04_081000"]


def test_listing_ignores_files_and_foreign_dirs(tmp_path):
    root = note_meta.stage_root(tmp_path)
    root.mkdir(parents=True)
    (root / "process-outline.json").write_text("{}", encoding="utf-8")
    (root / "not-a-stem").mkdir()

    listing = note_meta.list_stages(tmp_path)

    assert listing.kept_drafts == []
    assert listing.stale_stages == []


def test_listing_without_a_stage_root_is_empty(tmp_path):
    listing = note_meta.list_stages(tmp_path)

    assert listing.kept_drafts == []
    assert listing.stale_stages == []


# ── Stem drawing, validation and drop ────────────────────────────────────────


def test_draw_stem_has_seconds():
    assert note_meta.draw_stem(datetime(2026, 11, 4, 9, 5, 7)) == "2026-11-04_090507"


@pytest.mark.parametrize("bad", ["", "../x", "2026-11-04_1015", "2026-11-04_101500/..", "a/b"])
def test_stage_dir_rejects_a_malformed_stem(tmp_path, bad):
    with pytest.raises(ValueError):
        note_meta.stage_dir(tmp_path, bad)


def test_remove_stage_deletes_the_directory(tmp_path):
    stage = _stage_with(tmp_path, _meta())
    (stage / "draft.md").write_text("x", encoding="utf-8")

    assert note_meta.remove_stage(tmp_path, STEM) is True
    assert not stage.exists()


def test_remove_stage_on_a_missing_stem_reports_false(tmp_path):
    assert note_meta.remove_stage(tmp_path, STEM) is False


# ── Interrupted delivery (SDD Error Handling) ────────────────────────────────


def test_delivery_killed_between_steps_is_a_kept_draft_not_stale(tmp_path):
    interrupted = _meta(stem="2026-11-04_090000")
    note_meta.mark_step_done(interrupted, "note")
    _stage_with(tmp_path, interrupted)

    listing = note_meta.list_stages(tmp_path)

    assert listing.kept_drafts == [{
        "stem": "2026-11-04_090000",
        "title": "Weekly: sync",
        "template": "Templates/Meeting Notes.md",
        "created": "2026-11-04T10:15:00Z",
        "failed_step": "",
    }]
    assert listing.stale_stages == []


# ── read_meta type checks ────────────────────────────────────────────────────


def _raw_stage(root: Path, **overrides) -> Path:
    stage = note_meta.stage_dir(root, STEM)
    stage.mkdir(parents=True)
    raw = asdict(_meta()) | overrides
    (stage / "meta.json").write_text(json.dumps(raw), encoding="utf-8")
    return stage


@pytest.mark.parametrize("overrides", [
    {"steps_done": "instructions_json"},
    {"steps_done": ["note", "upload"]},
    {"steps_done": ["note", "note"]},
    {"steps_done": [1]},
    {"keep_source": "false"},
    {"keep_source": 0},
    {"failed_step": None},
    {"failed_step": "upload"},
    {"title": 42},
    {"destination": None},
    {"run_id": ["x"]},
    {"source_path": 7},
    {"stem": "2026-11-04_111111"},
])
def test_read_meta_rejects_a_field_of_the_wrong_shape(tmp_path, overrides):
    stage = _raw_stage(tmp_path, **overrides)

    with pytest.raises(note_meta.MetaError):
        note_meta.read_meta(stage)
    assert note_meta.list_stages(tmp_path).stale_stages == [STEM]


@pytest.mark.parametrize("steps_done", ["instructions_json", "", {"note": 1}])
def test_steps_done_that_is_not_a_list_is_rejected(tmp_path, steps_done):
    # "" and {"note": 1} pass the per-element check; only the list check rejects them.
    stage = _raw_stage(tmp_path, steps_done=steps_done)

    with pytest.raises(note_meta.MetaError):
        note_meta.read_meta(stage)
    assert note_meta.list_stages(tmp_path).kept_drafts == []


def _raw_stage_without(root: Path, *keys: str, **overrides) -> Path:
    stage = note_meta.stage_dir(root, STEM)
    stage.mkdir(parents=True)
    raw = asdict(_meta()) | overrides
    for key in keys:
        raw.pop(key)
    (stage / "meta.json").write_text(json.dumps(raw), encoding="utf-8")
    return stage


def test_meta_without_the_defaulted_fields_reads_with_defaults(tmp_path):
    stage = _raw_stage_without(tmp_path, "keep_source", "steps_done", "failed_step", "profile")

    meta = note_meta.read_meta(stage)

    assert (meta.keep_source, meta.steps_done, meta.failed_step) == (False, [], "")
    assert meta.profile is None


def test_profile_round_trips(tmp_path):
    stage = _stage_with(tmp_path, _meta(profile="miyo"))

    assert note_meta.read_meta(stage).profile == "miyo"


@pytest.mark.parametrize("bad", [3, True, ["miyo"], {"name": "miyo"}])
def test_present_profile_of_wrong_type_is_rejected(tmp_path, bad):
    stage = _raw_stage_without(tmp_path, profile=bad)

    with pytest.raises(note_meta.MetaError, match="profile"):
        note_meta.read_meta(stage)


def test_null_profile_is_accepted(tmp_path):
    stage = _raw_stage_without(tmp_path, profile=None)

    assert note_meta.read_meta(stage).profile is None


def test_meta_without_failed_step_but_with_a_done_step_is_a_kept_draft(tmp_path):
    _raw_stage_without(tmp_path, "failed_step", steps_done=["note"])

    listing = note_meta.list_stages(tmp_path)

    assert [d["stem"] for d in listing.kept_drafts] == [STEM]
    assert listing.kept_drafts[0]["failed_step"] == ""
    assert listing.stale_stages == []


# ── Error messages carry no offending value ──────────────────────────────────

MARKER = "SECRETMARKER"


def test_malformed_stem_error_does_not_echo_the_stem(tmp_path):
    with pytest.raises(ValueError) as exc:
        note_meta.stage_dir(tmp_path, f"../{MARKER}")

    assert MARKER not in str(exc.value)


def test_unknown_step_error_does_not_echo_the_step():
    meta = _meta()

    with pytest.raises(ValueError) as done:
        note_meta.mark_step_done(meta, MARKER)
    with pytest.raises(ValueError) as failed:
        note_meta.mark_step_failed(meta, MARKER)

    assert MARKER not in str(done.value)
    assert MARKER not in str(failed.value)


def test_meta_error_carries_neither_stem_nor_file_text(tmp_path):
    stage = _raw_stage(tmp_path, title=[MARKER], template=MARKER)

    with pytest.raises(note_meta.MetaError) as exc:
        note_meta.read_meta(stage)

    assert MARKER not in str(exc.value)
    assert STEM not in str(exc.value)


def test_meta_error_on_broken_json_does_not_name_the_stem(tmp_path):
    stage = note_meta.stage_dir(tmp_path, STEM)
    stage.mkdir(parents=True)
    (stage / "meta.json").write_text("{" + MARKER, encoding="utf-8")

    with pytest.raises(note_meta.MetaError) as exc:
        note_meta.read_meta(stage)

    assert MARKER not in str(exc.value)
    assert STEM not in str(exc.value)


# ── new_meta signature ───────────────────────────────────────────────────────


def test_new_meta_without_stem_raises_a_type_error_naming_stem():
    fields = dict(inbox="100 Inbox", title="T", destination="A/", default_destination="A/")

    with pytest.raises(TypeError, match="stem"):
        note_meta.new_meta(**fields)
