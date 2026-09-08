#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t6_0c_merge_visibility.py — spec 034 T6.0c, the merge must say what it did.

T6.0c folded `_merge_proposed_mocs_by_name`'s key, which widened what a single
run absorbs. The merge itself stayed mute: no `[warn]`, no needs-attention line,
no audit row. Under CON-2 the user approves on what the document says, so a run
that emits ONE MOC where TWO proposals were approved must say so.

Modelled on the record that already exists — `validate_destinations`' clash
record (`render_actions.py`), which carries `case_only: bool` beside `kind` and
groups its claimants under one `dropped: [...]` list rather than emitting a
record per claimant. The WORDING is deliberately not T5.5's "Not filed":
nothing is withheld here, the MOC IS created, once instead of twice.

What each block pins:

  1. The record is born in the merge and is a GROUP per surviving name —
     survivor plus a list of absorbed spellings, appended in encounter order.
     A case-only pair records `case_only: true`; an exact repeat records
     `case_only: false`.
  2. It survives the JSON round trip on BOTH parser paths (wire and markdown),
     and the internal carrier field is stripped from `confirmed_items` exactly
     like `member_stems` and `topic`.
  3. It is reentrant across the markdown path's DOUBLE merge. The two-stage
     fixture is the only case that exposes both the "one record, not two" and
     the append-order requirements.
  4. It reaches the user. Driven through the real `instruction-render.main()`,
     not `render_instructions_md()` with a hand-built dict — reading the record
     into a local at the read-back site without adding it to the metadata dict
     renders nothing and raises nothing.
  5. A run with no merge renders no such section.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
PARSER = SCRIPTS_DIR / "suggestion-parser.py"

sys.path.insert(0, str(SCRIPTS_DIR))

INBOX = "100 Inbox/"
MOC_FOLDER = "Atlas/200 Maps/"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


parser = _load("parser_t60c_vis", "suggestion-parser.py")


# ──────────────────────────────────────────────────────────────────────
# Fixtures — both parser paths
# ──────────────────────────────────────────────────────────────────────

def _wire(*names: str) -> dict:
    return {
        "schema_version": "1",
        "run_id": "2026-09-08T10-00-00Z-t60c-vis",
        "suggestions": [],
        "proposed_mocs": [
            {"topic": f"T{i}", "name": n, "decision": "approve",
             "parent": "2700 - Art & Recreation", "tags": [f"topic/t{i}"],
             "member_ids": []}
            for i, n in enumerate(names, start=1)
        ],
    }


def _doc(*proposals: tuple[str, str, str]) -> str:
    head = [
        "---", "type: tomo-suggestions", "generated: 2026-09-08T10:00:00Z",
        'tomo_version: "0.1.0"', "profile: miyo", "source_items: 1",
        "run_id: 2026-09-08T10-00-00Z-t60c-vis", "---", "",
        "# Inbox Suggestions — 2026-09-08", "", "- [x] Approved", "",
        "## Proposed MOCs", "",
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
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert r.returncode == 0, f"parser exit {r.returncode}; stderr:\n{r.stderr}"
    return json.loads(r.stdout)


# ──────────────────────────────────────────────────────────────────────
# 1. The record — group per surviving name, case_only per scenario
# ──────────────────────────────────────────────────────────────────────

def test_a_case_only_merge_records_case_only_true():
    out = parser.build_from_wire(_wire("Travel (MOC)", "travel (MOC)"), "")
    records = out["merged_moc_proposals"]
    assert len(records) == 1, records
    assert records[0]["name"] == "Travel (MOC)", records[0]
    assert records[0]["case_only"] is True, records[0]
    assert records[0]["absorbed"] == ["travel (MOC)"], records[0]


def test_an_exact_repeat_records_case_only_false():
    """The record exists for any merge, not only a case-only one — but the
    reader is told which kind it was. An exact repeat is the user naming one
    MOC twice; a case-only pair is the filesystem collapsing two names."""
    out = parser.build_from_wire(_wire("Travel (MOC)", "Travel (MOC)"), "")
    records = out["merged_moc_proposals"]
    assert len(records) == 1, records
    assert records[0]["case_only"] is False, records[0]
    assert records[0]["absorbed"] == ["Travel (MOC)"], records[0]


def test_no_merge_records_nothing():
    out = parser.build_from_wire(_wire("Travel (MOC)", "Cooking (MOC)"), "")
    assert out["merged_moc_proposals"] == [], out["merged_moc_proposals"]


def test_the_internal_carrier_is_stripped_from_confirmed_items():
    """The absorbed-spellings list rides on the survivor across merge calls,
    exactly like `member_stems` and `topic`, and must be lifted out at the same
    two strip sites rather than leaking into a confirmed item."""
    out = parser.build_from_wire(_wire("Travel (MOC)", "travel (MOC)"), "")
    for c in out["confirmed_items"]:
        assert "absorbed_names" not in c, (
            f"internal carrier leaked into a confirmed item: {c}"
        )
        assert "member_stems" not in c and "topic" not in c, c


def test_both_parser_paths_emit_the_record(tmp_path):
    """Three call sites, two paths — the wire merges once, the markdown path
    twice. This spec has already been bitten by the two diverging (T5.1), so
    neither is inferred from the other."""
    primary = tmp_path / "suggestions.md"
    primary.write_text(
        _doc(("Reisen", "Travel (MOC)", "Dresden"), ("Travel", "travel (MOC)", "Kyoto")),
        encoding="utf-8",
    )
    markdown = _run_parser(primary)["merged_moc_proposals"]
    wire = parser.build_from_wire(_wire("Travel (MOC)", "travel (MOC)"), "")[
        "merged_moc_proposals"
    ]
    for label, records in (("markdown", markdown), ("wire", wire)):
        assert len(records) == 1, f"{label}: {records}"
        assert records[0]["name"] == "Travel (MOC)", f"{label}: {records[0]}"
        assert records[0]["case_only"] is True, f"{label}: {records[0]}"
        assert records[0]["absorbed"] == ["travel (MOC)"], f"{label}: {records[0]}"


# ──────────────────────────────────────────────────────────────────────
# 3. Reentrant across the markdown path's double merge
# ──────────────────────────────────────────────────────────────────────

def test_the_record_survives_the_double_merge_as_one_grouped_entry(tmp_path):
    """Two-stage fixture. `Travel (MOC)` + `travel (MOC)` collapse in the
    per-document merge; `TRAVEL (MOC)` arrives from the fan doc and only the
    second merge can see it. The second call has no memory of the first, so a
    record built fresh per call would emit TWO records for one survivor.

    Append order is asserted exactly: `primary_pmocs + fan_pmocs` puts primary
    first, so the encounter order is deterministic — but only while the
    coalescing appends. A `set()` would make it implementation-defined, and
    this is the only fixture that exposes it."""
    primary = tmp_path / "suggestions.md"
    fan = tmp_path / "suggestions-fan.md"
    primary.write_text(
        _doc(("Reisen", "Travel (MOC)", "Dresden"), ("Travel", "travel (MOC)", "Kyoto")),
        encoding="utf-8",
    )
    fan.write_text(_doc(("Fernweh", "TRAVEL (MOC)", "Furano")), encoding="utf-8")

    out = _run_parser(primary, fan)

    mocs = [c for c in out["confirmed_items"] if c.get("action") == "create_moc"]
    assert len(mocs) == 1, [m.get("title") for m in mocs]
    supporting = mocs[0].get("supporting_items") or ""
    for member in ("Dresden", "Kyoto", "Furano"):
        assert member in supporting, f"{member!r} lost; got {supporting!r}"

    records = out["merged_moc_proposals"]
    assert len(records) == 1, (
        f"a three-way collapse is ONE group per surviving name, not one record "
        f"per absorption; got {records}"
    )
    assert records[0]["name"] == "Travel (MOC)", records[0]
    assert records[0]["absorbed"] == ["travel (MOC)", "TRAVEL (MOC)"], (
        f"absorbed spellings must be appended in encounter order (primary "
        f"before fan); got {records[0]['absorbed']}"
    )
    assert records[0]["case_only"] is True, records[0]


def test_an_absorbed_survivor_carries_its_own_group_across(tmp_path):
    """The other half of reentrancy, and the one the three-way fixture above
    cannot reach.

    Above, the already-merged survivor is the one that SEEDS stage 2, so its
    list is extended in place and nothing has to be carried. Here BOTH
    documents merge internally first, so the moc being absorbed in stage 2 is
    itself a survivor carrying its own absorbed list. Without that list being
    carried over, the fan pair's losing spelling vanishes from the report while
    its supporting item is still merged into the MOC — a silent under-report,
    which is the same CON-2 defect this record exists to fix, one level down."""
    primary = tmp_path / "suggestions.md"
    fan = tmp_path / "suggestions-fan.md"
    primary.write_text(
        _doc(("Reisen", "Travel (MOC)", "Dresden"), ("Travel", "travel (MOC)", "Kyoto")),
        encoding="utf-8",
    )
    fan.write_text(
        _doc(("Fernweh", "TRAVEL (MOC)", "Furano"), ("Wandern", "TrAvEl (MOC)", "Zermatt")),
        encoding="utf-8",
    )

    out = _run_parser(primary, fan)

    mocs = [c for c in out["confirmed_items"] if c.get("action") == "create_moc"]
    assert len(mocs) == 1, [m.get("title") for m in mocs]
    supporting = mocs[0].get("supporting_items") or ""
    for member in ("Dresden", "Kyoto", "Furano", "Zermatt"):
        assert member in supporting, f"{member!r} lost; got {supporting!r}"

    records = out["merged_moc_proposals"]
    assert len(records) == 1, records
    assert records[0]["absorbed"] == [
        "travel (MOC)", "TRAVEL (MOC)", "TrAvEl (MOC)",
    ], (
        "every absorbed spelling must be reported, including one absorbed by a "
        "proposal that was itself later absorbed; got "
        f"{records[0]['absorbed']}"
    )


# ──────────────────────────────────────────────────────────────────────
# 4. It reaches the user — through the real render entry point
# ──────────────────────────────────────────────────────────────────────

def _drive_render(monkeypatch, tmp_path, parsed: dict) -> Path:
    """Drive the real `instruction-render.main()` over a parsed-suggestions dict.

    Deliberately not `render_instructions_md()` with a hand-built metadata dict:
    the record crosses a process boundary, and the failure this guards is
    reading it into a local at the read-back site and forgetting to add it to
    the literal dict passed as the renderer's second argument. That omission
    raises nothing and fails no renderer-level unit test — only a run through
    `main()` can see it.
    """
    from unittest.mock import MagicMock

    ir = _load("instruction_render_t60c_vis", "instruction-render.py")
    suggestions_file = tmp_path / "suggestions.json"
    suggestions_file.write_text(json.dumps(parsed), encoding="utf-8")
    cfg_file = tmp_path / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(ir, "load_config", lambda _p: {
        "concepts.inbox": INBOX, "profile": "miyo", "callouts.editable": ["NOTE"],
    })
    monkeypatch.setattr(ir, "KadoClient", lambda: MagicMock())
    monkeypatch.setattr(ir, "build_actions", lambda *_a, **_kw: ([], []))
    monkeypatch.setattr(ir, "resolve_target_moc_paths", lambda _a, _c: 0)
    monkeypatch.setattr(ir, "resolve_section_names", lambda *_a, **_kw: 0)
    monkeypatch.setattr(ir, "_validate_action_paths", lambda _a: [])

    out_dir = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", [
        "instruction-render.py", "--suggestions", str(suggestions_file),
        "--output-dir", str(out_dir), "--config", str(cfg_file),
    ])
    assert isinstance(ir.main(), int)
    return out_dir


def test_the_merge_is_reported_in_the_instructions_document(monkeypatch, tmp_path):
    """Substring assertions, matching how the T5.3 and T5.4 tests check their
    sections — full-paragraph pinning breaks on the next copy edit."""
    parsed = parser.build_from_wire(_wire("Travel (MOC)", "travel (MOC)"), "")
    out_dir = _drive_render(monkeypatch, tmp_path, parsed)
    md = (out_dir / "instructions.md").read_text(encoding="utf-8")

    assert "Travel (MOC)" in md
    assert "travel (MOC)" in md, "the absorbed spelling must be named, not only the survivor"
    assert "Merged" in md, (
        "the document must have a section reporting the merge; without it the "
        "record reached the renderer's metadata dict and rendered nothing"
    )
    assert "differ only in case" in md, (
        "a case-only merge must say the names differ only in case"
    )
    assert "Not filed" not in md, (
        "nothing was withheld — the MOC IS created, once instead of twice. "
        "T5.5's 'Not filed' wording would misdescribe the outcome."
    )


def test_the_merge_reaches_instructions_json_too(monkeypatch, tmp_path):
    """Twin-written, like `destination_clashes` and `attachment_suppressions`.

    The markdown is not the only artefact a reader works from: a workflow driven
    from `instructions.json` would never learn that one MOC was created where
    two proposals were approved. Both siblings land in the `tomo` block for
    exactly this reason, and the record has to follow them.

    Asserted off the file on disk, not an in-process dict — the dict proves the
    value was computed, never that it was written."""
    parsed = parser.build_from_wire(_wire("Travel (MOC)", "travel (MOC)"), "")
    out_dir = _drive_render(monkeypatch, tmp_path, parsed)
    doc = json.loads((out_dir / "instructions.json").read_text(encoding="utf-8"))

    records = doc["tomo"]["merged_moc_proposals"]
    assert len(records) == 1, records
    assert records[0]["name"] == "Travel (MOC)", records[0]
    assert records[0]["absorbed"] == ["travel (MOC)"], records[0]
    assert records[0]["case_only"] is True, records[0]


def test_a_run_with_no_merge_renders_no_such_section(monkeypatch, tmp_path):
    """Both artefacts stay silent, and the `tomo` block gains no key — guarded
    the same way its siblings are, so a clean run's output is unchanged."""
    parsed = parser.build_from_wire(_wire("Travel (MOC)", "Cooking (MOC)"), "")
    out_dir = _drive_render(monkeypatch, tmp_path, parsed)

    md = (out_dir / "instructions.md").read_text(encoding="utf-8")
    assert "Merged" not in md, md

    doc = json.loads((out_dir / "instructions.json").read_text(encoding="utf-8"))
    assert "merged_moc_proposals" not in (doc.get("tomo") or {}), (
        "a run with no merges must add no key — an empty list in the tomo "
        "block would change every clean run's instructions.json"
    )


# ──────────────────────────────────────────────────────────────────────
# The paired-consumer count
# ──────────────────────────────────────────────────────────────────────

def test_every_consumer_of_the_record_is_wired(monkeypatch, tmp_path):
    """The record crosses a process boundary and has four sites, none of them a
    call site of the merge. A count here fails when a second consumer is added
    or forgotten — the read-back at `instruction-render.py` is a LOCAL VARIABLE
    and reaching it proves nothing about the renderer seeing it."""
    sources = {
        "parser": (SCRIPTS_DIR / "suggestion-parser.py").read_text(encoding="utf-8"),
        "render": (SCRIPTS_DIR / "instruction-render.py").read_text(encoding="utf-8"),
        "md": (SCRIPTS_DIR / "lib" / "render_md.py").read_text(encoding="utf-8"),
    }
    assert sources["parser"].count('"merged_moc_proposals"') == 2, (
        "both parser output dicts (wire and markdown) must carry the record"
    )
    assert sources["render"].count('"merged_moc_proposals"') == 3, (
        "instruction-render has THREE sites: the read-back, the `tomo` block "
        "written into instructions.json, and the literal metadata dict passed "
        "to render_instructions_md. The read-back alone is a silent no-op, and "
        "the metadata dict alone reaches only one of the two artefacts."
    )
    assert sources["md"].count('"merged_moc_proposals"') == 1, (
        "render_md must read the record off the metadata dict"
    )
