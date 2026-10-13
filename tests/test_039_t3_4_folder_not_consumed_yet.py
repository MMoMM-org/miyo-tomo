#!/usr/bin/env python3
# version: 0.2.1
"""test_039_t3_4_folder_not_consumed_yet.py — spec 039 T3.4, retargeted in T4.3.

Phase 3 put an editable folder on both surfaces (Pass 1 renders a
`  - Folder: \\`<dir>\\`` line, the wire v4 carries `proposed_dir`, the parser
records `proposed_dir` + `dir_is_owner_supplied`). Phase 3 pinned that Pass 2
ignored it; T4.3 made Pass 2 honour it through the attachment plan (K1), so
this file now pins the real folder outcome, running the real
`instruction-render.py` `main()`: untouched folder → the rename lands in the
configured asset folder; folder edited (markdown line) or a `proposed_dir`
string (wire) → the move lands in that folder; both surfaces agree byte for
byte.

Mechanism falsified: "Pass 2 drops the owner's folder" — revert K1's
`_typed_folder` to always return None and both edited-folder tests fail.

The "038 baseline" this phase must leave untouched is the captured fixture
`tests/fixtures/038-wire-baseline/` pinned by
`tests/test_038_t2_4_wire_baseline_diff.py` (conflict-free wire payload) and
the markdown/wire convergence pinned by
`tests/test_038_t4_4_the_two_paths_converge.py`; both are run green unchanged
rather than duplicated here. CON-7: fixtures and fakes only.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ir = _load("instruction_render_t039_t3_4", "instruction-render.py")
PARSER = _load("suggestion_parser_t039_t3_4", "suggestion-parser.py")
REDUCER = _load("suggestions_reducer_t039_t3_4", "suggestions-reducer.py")

from lib import doc_frontmatter  # noqa: E402

_CFG = {
    "concepts.inbox": "100 Inbox/",
    "concepts.asset": "Atlas/290 Assets/295 Attachments/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
    "callouts.editable": ["NOTE"],
}
ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"
SOURCE = "100 Inbox/Scans/karte.png"
OCCUPIED = f"{ASSET_FOLDER}karte.png"
OTHER_FOLDER = "Atlas/Other Folder"

CONFLICT = {
    "source": SOURCE,
    "destination": OCCUPIED,
    "same_file": False,
    "owner_source_items": ["100 Inbox/karte.md"],
    "proposed_name": "karte (2).png",
    "proposed_dir": None,
}


def _item(item_id, title, source_path, attachments):
    return {
        "id": item_id, "action": None, "title": title,
        "template": "templates/atomic.md", "source_path": source_path,
        "tags": [], "parent_moc": "", "parent_mocs": [],
        "destination": "Atlas/202 Notes/", "summary": "",
        "attachments": attachments, "candidate_mocs": [],
    }


def _markdown_remedies(folder_line: str | None) -> list[dict]:
    """Remedy records from the real Pass-1 block, folder line optionally edited."""
    md = REDUCER.render_attachment_conflicts_block([CONFLICT], ASSET_FOLDER)
    if folder_line is not None:
        lines = md.splitlines()
        idx = [i for i, ln in enumerate(lines) if ln.startswith("  - Folder:")]
        assert len(idx) == 1, lines
        lines[idx[0]] = folder_line
        md = "\n".join(lines) + "\n"
    records = PARSER._join_attachment_conflict_remedies(
        PARSER.parse_attachment_conflict_remedies(md),
        {"attachment_conflicts": [CONFLICT]},
    )
    assert len(records) == 1 and records[0]["remedy"] == "rename", records
    return records


def _wire_remedies(proposed_dir: str | None) -> list[dict]:
    return [{
        "source": SOURCE, "remedy": "rename", "proposed_name": "karte (2).png",
        "name_is_owner_supplied": False,
        "proposed_dir": proposed_dir,
        "dir_is_owner_supplied": proposed_dir is not None,
    }]


def _run_pass_2(monkeypatch, tmp_path: Path, remedies: list[dict]) -> dict[str, bytes]:
    suggestions = {
        "confirmed_items": [_item("S01", "Karte", "karte.md", [SOURCE])],
        "daily_updates": [],
        "skipped": [],
        "attachment_conflict_remedies": remedies,
    }
    tmp_path.mkdir(parents=True, exist_ok=True)
    sf = tmp_path / "suggestions.json"
    sf.write_text(json.dumps(suggestions), encoding="utf-8")
    cf = tmp_path / "vault-config.yaml"
    cf.write_text("", encoding="utf-8")
    monkeypatch.setattr(ir, "load_config", lambda _p: dict(_CFG))
    monkeypatch.setattr(ir, "KadoClient", lambda: MagicMock())
    monkeypatch.setattr(ir, "read_template", lambda _c, _r: "# {{title}}\n{{body}}\n")
    monkeypatch.setattr(ir, "read_note_body", lambda *_a, **_kw: "")
    monkeypatch.setattr(ir, "render_via_script",
                        lambda *_a, **_kw: "See ![[Scans/karte.png]]\n")
    # `updated_at` comes from the tomo-block builder's own clock: frozen, or
    # two runs compared byte for byte differ across a second boundary.
    monkeypatch.setattr(doc_frontmatter, "_utc_now", lambda: "2026-10-12T09:00:00Z")
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["instruction-render.py", "--suggestions", str(sf),
                                      "--output-dir", str(out), "--config", str(cf)])
    assert ir.main() == 0
    # The manifest records absolute paths under the per-run output dir; that
    # is the only legitimate difference between two runs, so it is masked.
    return {str(p.relative_to(out)): p.read_bytes().replace(str(out).encode(), b"<OUT>")
            for p in sorted(out.rglob("*")) if p.is_file()}


def _moves(files: dict[str, bytes]) -> list[str]:
    instr = json.loads(files["instructions.json"])
    return [a["destination"] for a in instr["actions"]
            if a["action"] == "move_asset" and a["source"] == SOURCE]


def test_markdown_edited_folder_line_moves_into_that_folder(monkeypatch, tmp_path):
    base = _run_pass_2(monkeypatch, tmp_path / "a", _markdown_remedies(None))
    edited_remedies = _markdown_remedies(f"  - Folder: `{OTHER_FOLDER}`")
    # The edit is real and reached the parser: owner-supplied, verbatim.
    assert (edited_remedies[0]["proposed_dir"],
            edited_remedies[0]["dir_is_owner_supplied"]) == (OTHER_FOLDER, True)
    edited = _run_pass_2(monkeypatch, tmp_path / "b", edited_remedies)
    assert _moves(base) == [f"{ASSET_FOLDER}karte (2).png"]
    assert _moves(edited) == [f"{OTHER_FOLDER}/karte (2).png"]


def test_wire_proposed_dir_string_moves_into_that_folder(monkeypatch, tmp_path):
    base = _run_pass_2(monkeypatch, tmp_path / "a", _wire_remedies(None))
    edited = _run_pass_2(monkeypatch, tmp_path / "b", _wire_remedies(OTHER_FOLDER))
    assert _moves(base) == [f"{ASSET_FOLDER}karte (2).png"]
    assert _moves(edited) == [f"{OTHER_FOLDER}/karte (2).png"]


def test_both_surfaces_agree_with_each_other(monkeypatch, tmp_path):
    md = _run_pass_2(monkeypatch, tmp_path / "a",
                     _markdown_remedies(f"  - Folder: `{OTHER_FOLDER}`"))
    wire = _run_pass_2(monkeypatch, tmp_path / "b", _wire_remedies(OTHER_FOLDER))
    assert md == wire
