#!/usr/bin/env python3
# version: 0.2.0
"""test_035_t4_2b_daily_source_identity.py — spec 035 Phase 4, T4.2b: the
daily side gains its source identity.

PRD Feature 9 (out-of-sequence — see requirements.md's F9 note): every
daily-side entry (trackers, log_entries, log_links) must carry the source
note's identity as a required field, closing the one bucket — log_links —
that never carried any (F9-AC1/AC2). The display field (source_stem /
target_stem) stays untouched (F9-AC3), and the lossy round-trip recovery
that used to reconstruct the key after a wire edit is retired (F9-AC4).

**The design question this file exists to prove, not just assert:**
`suggestions-render.build_wire_payload` builds its daily buckets by parsing
its OWN rendered markdown (parity with build_from_wire — see
`_parser_mod`'s docstring), and that markdown never carried an item key. The
naive fix — reuse the existing discriminator-match recovery
(`enrich_daily_updates_with_item_keys`) on the producer side — cannot
satisfy "required": that recovery's own docstring says a discriminator
mapping to more than one distinct key is left UNSET rather than guessed.
The actual fix (`_join_daily_source_item_keys`, suggestions-render.py) joins
POSITIONALLY against the structured `daily_notes_updates` block the
markdown was rendered from, which `render_daily_notes_updates_block`
produces in the same order `parse_daily_updates` recovers — so two entries
sharing an identical discriminating value (content/field/target) in the
same bucket on the same day still resolve correctly. Every test below that
exercises `build_wire_payload` uses exactly that ambiguous shape, not a
convenience fixture with unique values that would pass for the wrong
reason.

**A second, unplanned finding surfaces here too.** Proving the ambiguous
case for `log_links` required first discovering that `log_links` entries
never survived `parse_daily_updates` at all: the renderer emits a bare
wikilink line (`- [[target]]`) for a log_link, with no em dash, while
`RE_DAILY_LOG_LINE` — the only line-matcher log_links shared with
log_entries — requires one. `build_wire_payload`'s log_links bucket was
therefore silently empty on every real wire, on every run, since the
bucket was introduced (a pre-existing defect, unrelated to schema
versioning, but one F9-AC2 cannot be satisfied around). Fixed in
`parse_daily_updates` by giving log_links their own line-matcher
(`RE_DAILY_LOG_LINK_LINE`) and a "- Position:" sub-field handler; guarded
here (see the "log_links survive markdown round-trip" test) so it cannot
regress silently a second time.

**Follow-up (review round 1):** the first cut of `_join_daily_source_item_keys`
silently wrote `source_item_key=None` when the structured source could not
supply one (e.g. a `suggestions-doc.json` predating the reducer's
2026-09-06 change) — producing an invalid-but-unvalidated wire with no
signal at all until Hashi's editor rejected it downstream, with nothing
pointing back at the cause. It now raises `ValueError` at render time
instead, naming the day, bucket, discriminating value, and the likely
cause — see the "fails loudly" tests below.

Spec: docs/XDD/specs/035-wire-schema-versioning/
Ref:  PRD Feature 9 (F9-AC1..AC5), ADR-5 (schema_version read via
      wire_schema_version, never a renderer literal), ADR-3 (wire_gate.py:
      any shape change fails; regeneration is always explicit)
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"
SHAPES_DIR = SCHEMAS_DIR / "shapes"
WIRE_SCHEMA_PATH = SCHEMAS_DIR / "suggestions-wire.schema.json"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.wire_gate import (  # noqa: E402
    ACTION_HANDOVER,
    ACTION_MOVE_VERSION,
    ACTION_REGENERATE_MANIFEST,
    ACTIONS,
    gate_one_wire,
)
from lib.wire_shape import (  # noqa: E402
    PUBLISHED_WIRES,
    build_manifest,
    manifest_filename,
    serialize_manifest,
)


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


reducer = _load("reducer_t42b", "suggestions-reducer.py")
render = _load("render_t42b", "suggestions-render.py")
parser = _load("parser_t42b", "suggestion-parser.py")

WIRE_SCHEMA = json.loads(WIRE_SCHEMA_PATH.read_text(encoding="utf-8"))
_DAILY_BUCKET_NODE = WIRE_SCHEMA["properties"]["daily_updates"]["items"]["properties"]


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

def _doc(daily: list[dict]) -> dict:
    """A minimal suggestions-doc.json carrying only daily content — everything
    `build_wire_payload` dereferences directly (KeyError otherwise) plus the
    structured/rendered daily pair it joins source_item_key from."""
    return {
        "schema_version": "1", "generated": "2026-09-11T10:00:00Z", "run_id": "r-t42b",
        "profile": "miyo", "source_items": 0,
        "conventions": {"parent_marker": "up::", "peer_marker": "related::", "moc_suffix": " MOC"},
        "sections": [], "proposed_mocs": [], "needs_attention": [],
        "daily_notes_updates": daily,
        "rendered_daily_updates_md": reducer.render_daily_notes_updates_block(daily),
    }


def _ambiguous_daily() -> list[dict]:
    """One day, all three buckets, each carrying TWO entries that share the
    bucket's own discriminating value (tracker field / log content / link
    target) but originate from two DIFFERENT source notes. This is exactly
    the shape `enrich_daily_updates_with_item_keys`'s discriminator-match
    would refuse to resolve (its docstring: "left unset rather than
    guessed") — proving the join is positional, not content-matched.
    """
    return [{
        "daily_note_stem": "2026-09-11", "exists": True,
        "trackers": [
            {"field": "Sport", "value": True, "reason": "ran 5k",
             "source_stem": "Dresden", "source_item_key": "100 Inbox/Places/Dresden.md",
             "source_section": "S01"},
            {"field": "Sport", "value": False, "reason": "rest day",
             "source_stem": "Dresden", "source_item_key": "100 Inbox/Reise/Dresden.md",
             "source_section": "S02"},
        ],
        "log_entries": [
            {"time": None, "position": "after_last_line", "content": "same wording",
             "reason": "r1", "source_stem": "Dresden",
             "source_item_key": "100 Inbox/Projects/Dresden.md", "source_section": "S03"},
            {"time": None, "position": "after_last_line", "content": "same wording",
             "reason": "r2", "source_stem": "Dresden",
             "source_item_key": "100 Inbox/Travel/Dresden.md", "source_section": "S04"},
        ],
        "log_links": [
            {"target_stem": "Frauenkirche", "time": None, "position": "after_last_line",
             "reason": "r3", "source_stem": "Dresden",
             "source_item_key": "100 Inbox/Places/Dresden.md", "source_section": "S05"},
            {"target_stem": "Frauenkirche", "time": "10:00", "position": "at_time",
             "reason": "r4", "source_stem": "Dresden",
             "source_item_key": "100 Inbox/Reise/Dresden.md", "source_section": "S06"},
        ],
    }]


# ──────────────────────────────────────────────────────────────────────────────
# F9-AC1 — all three buckets declare source_item_key, required on each
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bucket", ["trackers", "log_entries", "log_links"])
def test_bucket_declares_source_item_key_required(bucket):
    node = _DAILY_BUCKET_NODE[bucket]["items"]
    assert "source_item_key" in node["required"], (
        f"{bucket}: source_item_key must be required (F9-AC1)"
    )
    prop = node["properties"]["source_item_key"]
    assert prop["type"] == "string"
    assert prop["minLength"] == 1


def test_schema_version_moved_to_2():
    assert WIRE_SCHEMA["properties"]["schema_version"]["const"] == "2"


# ──────────────────────────────────────────────────────────────────────────────
# F9-AC2 — log_links specifically: the bucket that never carried any identity
# ──────────────────────────────────────────────────────────────────────────────

def test_log_links_carries_source_item_key_when_emitted():
    daily = [{
        "daily_note_stem": "2026-09-11", "exists": True,
        "trackers": [], "log_entries": [],
        "log_links": [{
            "target_stem": "Frauenkirche", "time": None, "position": "after_last_line",
            "reason": "atomic derived from this log", "source_stem": "Dresden",
            "source_item_key": "100 Inbox/Places/Dresden.md", "source_section": "S01",
        }],
    }]
    wire = render.build_wire_payload(_doc(daily))
    ll = wire["daily_updates"][0]["log_links"][0]
    assert ll["source_item_key"] == "100 Inbox/Places/Dresden.md"
    jsonschema.validate(instance=wire, schema=WIRE_SCHEMA)


def test_log_links_survive_markdown_round_trip():
    """Guards the pre-existing defect this file's docstring describes: a
    log_link's own rendered line (`- [[target]]`, no em dash) must actually
    come back out of `parse_daily_updates` — it silently didn't before this
    fix, which made this whole bucket appear correct against an
    always-empty list."""
    daily = [{
        "daily_note_stem": "2026-09-11", "exists": True,
        "trackers": [], "log_entries": [],
        "log_links": [{
            "target_stem": "Frauenkirche", "time": "10:00", "position": "at_time",
            "reason": "r", "source_stem": "Dresden",
            "source_item_key": "100 Inbox/Places/Dresden.md", "source_section": "S01",
        }],
    }]
    md = reducer.render_daily_notes_updates_block(daily)
    parsed = parser.parse_daily_updates(md)
    assert len(parsed[0]["log_links"]) == 1, (
        f"log_link entry lost in the markdown round-trip: {parsed}"
    )
    entry = parsed[0]["log_links"][0]
    assert entry["target_stem"] == "Frauenkirche"
    assert entry["time"] == "10:00"
    assert entry["position"] == "at_time"
    assert entry["reason"] == "r"


# ──────────────────────────────────────────────────────────────────────────────
# The populated-by-construction test (RED test 3): every entry in every
# bucket carries source_item_key, including the ambiguous-discriminator case
# a re-derivation from content could not resolve.
# ──────────────────────────────────────────────────────────────────────────────

def test_ambiguous_entries_still_resolve_to_their_own_key_by_construction():
    wire = render.build_wire_payload(_doc(_ambiguous_daily()))
    day = wire["daily_updates"][0]

    tracker_keys = [t["source_item_key"] for t in day["trackers"]]
    assert tracker_keys == [
        "100 Inbox/Places/Dresden.md", "100 Inbox/Reise/Dresden.md",
    ], tracker_keys

    log_entry_keys = [e["source_item_key"] for e in day["log_entries"]]
    assert log_entry_keys == [
        "100 Inbox/Projects/Dresden.md", "100 Inbox/Travel/Dresden.md",
    ], log_entry_keys

    log_link_keys = [ll["source_item_key"] for ll in day["log_links"]]
    assert log_link_keys == [
        "100 Inbox/Places/Dresden.md", "100 Inbox/Reise/Dresden.md",
    ], log_link_keys

    jsonschema.validate(instance=wire, schema=WIRE_SCHEMA)


# ──────────────────────────────────────────────────────────────────────────────
# Fails loudly when the field cannot be populated (review round 1). A
# suggestions-doc.json from a reducer older than 2026-09-06 carries no
# source_item_key on daily_notes_updates at all — the join must raise, never
# write None, fall back to source_stem, or silently drop the entry.
# ──────────────────────────────────────────────────────────────────────────────

def _stale_daily(bucket: str) -> list[dict]:
    """One day, one entry in `bucket`, with NO `source_item_key` on the
    structured side — exactly what a pre-2026-09-06 reducer would emit."""
    base = {
        "daily_note_stem": "2026-09-11", "exists": True,
        "trackers": [], "log_entries": [], "log_links": [],
    }
    if bucket == "trackers":
        base["trackers"] = [{"field": "Sport", "value": True, "reason": "ran",
                              "source_stem": "Dresden", "source_section": "S01"}]
    elif bucket == "log_entries":
        base["log_entries"] = [{"time": None, "position": "after_last_line",
                                 "content": "wrote about Dresden", "reason": "r",
                                 "source_stem": "Dresden", "source_section": "S01"}]
    else:
        base["log_links"] = [{"target_stem": "Frauenkirche", "time": None,
                               "position": "after_last_line", "reason": "r",
                               "source_stem": "Dresden", "source_section": "S01"}]
    return [base]


@pytest.mark.parametrize("bucket,discriminator_value", [
    ("trackers", "field='Sport'"),
    ("log_entries", "content='wrote about Dresden'"),
    ("log_links", "target_stem='Frauenkirche'"),
])
def test_missing_source_item_key_raises_naming_bucket_and_stem(bucket, discriminator_value):
    with pytest.raises(ValueError) as excinfo:
        render.build_wire_payload(_doc(_stale_daily(bucket)))
    message = str(excinfo.value)
    assert bucket in message, message
    assert "2026-09-11" in message, message
    assert discriminator_value in message, message
    assert "2026-09-06" in message, (
        "the message must name the reducer-change date, so a maintainer can "
        f"tell a stale doc from any other cause: {message}"
    )
    assert "re-run" in message.lower() and "reducer" in message.lower(), (
        f"the message must say what to do: {message}"
    )


def test_missing_source_item_key_never_falls_back_to_source_stem():
    """The failure mode this guards is specifically a document that LIES
    about its own provenance — a silent fallback to source_stem (a
    non-unique display name) would do exactly that."""
    with pytest.raises(ValueError):
        render.build_wire_payload(_doc(_stale_daily("trackers")))
    # No wire is returned at all on this path — nothing to inspect for a
    # smuggled-in source_stem value. The raise itself is the guarantee.


def test_day_entirely_absent_from_structured_also_raises():
    """Not just a falsy source_item_key on a matched entry — a day (or
    bucket) missing from `structured` altogether must raise too, not
    silently leave the field unset."""
    daily = _stale_daily("log_entries")
    doc = _doc(daily)
    doc["daily_notes_updates"] = []  # structured side has nothing at all
    with pytest.raises(ValueError) as excinfo:
        render.build_wire_payload(doc)
    assert "log_entries" in str(excinfo.value)


# ──────────────────────────────────────────────────────────────────────────────
# F9-AC3 — the display fields are untouched
# ──────────────────────────────────────────────────────────────────────────────

def test_display_fields_unchanged_alongside_the_new_identity():
    wire = render.build_wire_payload(_doc(_ambiguous_daily()))
    day = wire["daily_updates"][0]

    assert [t["source_stem"] for t in day["trackers"]] == ["Dresden", "Dresden"]
    assert [e["source_stem"] for e in day["log_entries"]] == ["Dresden", "Dresden"]
    assert [ll["target_stem"] for ll in day["log_links"]] == ["Frauenkirche", "Frauenkirche"]

    du = _DAILY_BUCKET_NODE
    assert du["trackers"]["items"]["properties"]["source_stem"]["type"] == "string"
    assert du["log_entries"]["items"]["properties"]["source_stem"]["type"] == "string"
    assert du["log_links"]["items"]["properties"]["target_stem"]["type"] == "string"


# ──────────────────────────────────────────────────────────────────────────────
# F9-AC4 — the lossy round-trip recovery is retired
# ──────────────────────────────────────────────────────────────────────────────

def test_restore_daily_item_keys_no_longer_exists():
    """A cheap tripwire, not the real guard — a re-derived key under a
    different name would still pass this. The ambiguous-fixture test above
    is the real guard: any re-derivation from content, by any name, fails it
    the same way `enrich_daily_updates_with_item_keys` documents its own
    discriminator match failing."""
    assert not hasattr(parser, "_restore_daily_item_keys")


def test_nothing_calls_restore_daily_item_keys():
    for path in SCRIPTS_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "_restore_daily_item_keys(" not in text, (
            f"{path} still calls the retired recovery"
        )


def test_build_from_wire_needs_no_restore_step():
    """The wire itself now carries the key — build_from_wire's verbatim
    passthrough reproduces it with no post-hoc join."""
    wire = {
        "schema_version": "2", "suggestions": [], "proposed_mocs": [],
        "tag_handler_groups": [],
        "daily_updates": [{
            "date": "2026-09-11", "trackers": [], "log_links": [],
            "log_entries": [{
                "time": None, "position": "after_last_line", "content": "x",
                "reason": "r", "source_stem": "Dresden",
                "source_item_key": "100 Inbox/Places/Dresden.md",
                "accepted": True, "force_atomic_note": False,
            }],
        }],
    }
    out = parser.build_from_wire(wire, "")
    assert out["daily_updates"][0]["log_entries"][0]["source_item_key"] == (
        "100 Inbox/Places/Dresden.md"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Gate behaviour — scratch trees only, mirroring the F9 change shape
# (widen daily_updates.log_links, the one bucket that had no identity field)
# ──────────────────────────────────────────────────────────────────────────────

def _make_scratch_wires(tmp_path: Path) -> tuple[Path, Path]:
    schemas_dir = tmp_path / "schemas"
    shapes_dir = schemas_dir / "shapes"
    shapes_dir.mkdir(parents=True)
    for document in PUBLISHED_WIRES:
        shutil.copy(SCHEMAS_DIR / document, schemas_dir / document)
        manifest_name = manifest_filename(document)
        shutil.copy(SHAPES_DIR / manifest_name, shapes_dir / manifest_name)
    return schemas_dir, shapes_dir


def _rewrite_json(path: Path, mutate) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


def test_widened_log_links_unmoved_version_fails_and_demands_move(tmp_path):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)
    document = "suggestions-wire.schema.json"
    pointer = "/properties/daily_updates/items/properties/log_links/items"

    # log_links is closed (additionalProperties: false), so widening it is
    # consumer-affecting — the shape F9 actually makes. Manifest left
    # untouched (stale) and schema_version left unmoved.
    _rewrite_json(
        schemas_dir / document,
        lambda schema: schema["properties"]["daily_updates"]["items"]["properties"][
            "log_links"
        ]["items"]["properties"].__setitem__(
            "scratch_source_item_key_probe", {"type": "string"},
        ),
    )

    result = gate_one_wire(document, schemas_dir / document, shapes_dir / manifest_filename(document))

    assert result["passed"] is False
    assert result["affecting"] is True
    assert result["version_moved"] is False
    assert result["actions"] == [ACTION_MOVE_VERSION, ACTION_HANDOVER]
    matching = [c for c in result["changes"] if c["pointer"] == pointer]
    assert any(
        c["kind"] == "added_property" and "scratch_source_item_key_probe" in c["detail"]
        for c in matching
    )
    assert ACTION_REGENERATE_MANIFEST not in result["actions"], (
        "regeneration alone is not enough for an affecting change — a version "
        "move must still be demanded (PRD/F7-AC1)"
    )


def test_widened_log_links_moved_version_and_regenerated_manifest_passes(tmp_path):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)
    document = "suggestions-wire.schema.json"

    schema = _rewrite_json(
        schemas_dir / document,
        lambda schema: (
            schema["properties"]["daily_updates"]["items"]["properties"]["log_links"][
                "items"
            ]["properties"].__setitem__(
                "scratch_source_item_key_probe", {"type": "string"},
            ),
            schema["properties"]["schema_version"].__setitem__("const", "3"),
        ),
    )

    manifest_path = shapes_dir / manifest_filename(document)
    manifest_path.write_text(
        serialize_manifest(build_manifest(schema, source=f"tomo/schemas/{document}")),
        encoding="utf-8",
    )

    result = gate_one_wire(document, schemas_dir / document, manifest_path)

    assert result["passed"] is True
    assert result["changes"] == []
    assert result["actions"] == []
    assert result["schema_version"] == "3"
    assert result["manifest_version"] == "3"


def test_all_actions_are_registered_identities():
    """Sanity pin: the gate constants this file asserts against are the same
    identities `_result` validates — a typo here would silently compare
    against a value the gate could never actually emit."""
    for action in (ACTION_MOVE_VERSION, ACTION_HANDOVER, ACTION_REGENERATE_MANIFEST):
        assert action in ACTIONS
