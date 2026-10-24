#!/usr/bin/env python3
# version: 0.1.0
"""test_040_relevant_mocs_e2e.py — spec 040 T6.1: build → read → reduce → render.

Runs the real scripts in the order a Pass-1 run does, over one fixture cache
that includes an excluded MOC:

  shared-ctx-builder.py  → the context (excluded MOC not eligible)
  read-shared-ctx.py     → --moc-names (excluded absent), --mocs-from (a nominated subset)
  [analyst]              → a hand-made item result that proposes an existing MOC by name
  suggestions-reducer.py → converts the proposal (duplicate_proposals_converted=1)
  suggestions-render.py  → markdown + C3 wire

and asserts the components agree on one contract: the owner sees the existing
MOC as an unticked link and no Proposed MOC.

RED on `main`: `--moc-names` does not exist there, and nothing converts.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from lib.item_key import to_filename  # noqa: E402

ENV = {**os.environ, "PYTHONPATH": str(SCRIPTS)}
RUN = "e2e-040"
VACATION = "Atlas/200 Maps/Vacation (MOC).md"
WINE = "Atlas/200 Maps/Wine (MOC).md"
INDEX = "Atlas/200 Maps/000 Index.md"
ITEM_KEY = "100 Inbox/Herbstferien.md"


def _moc(path, title, tags=("type/others/moc",)):
    return {"path": path, "title": title, "topics": [title.split(" (")[0].lower()], "tags": list(tags),
            "headings": [{"text": "Trips", "level": 2}], "editable_callouts": ["> [!blocks]- Notes"],
            "has_footer": True}


def _run(*cmd: str) -> subprocess.CompletedProcess:
    out = subprocess.run([sys.executable, *cmd], capture_output=True, text=True, env=ENV)
    assert out.returncode == 0, f"{cmd[0]} failed:\n{out.stderr}"
    return out


def test_an_existing_moc_reaches_the_owner_as_an_unticked_link(tmp_path):
    # ── build ────────────────────────────────────────────────────────────────
    cache = {"map_notes": [
        _moc(VACATION, "Vacation (MOC)"),
        _moc(WINE, "Wine (MOC)"),
        _moc(INDEX, "000 Index", tags=("type/others/moc", "MiYo/Tomo/exclude/moc")),
    ]}
    (tmp_path / "cache.yaml").write_text(yaml.safe_dump(cache), encoding="utf-8")
    (tmp_path / "vault-config.yaml").write_text(yaml.safe_dump({
        "profile": "miyo", "tags": {"prefixes": {}},
        "concepts": {"map_note": {"paths": ["Atlas/200 Maps/"]}},
    }), encoding="utf-8")
    ctx = tmp_path / "shared-ctx.json"
    built = _run(str(SCRIPTS / "shared-ctx-builder.py"), "--cache", str(tmp_path / "cache.yaml"),
                 "--vault-config", str(tmp_path / "vault-config.yaml"),
                 "--profiles-dir", str(REPO_ROOT / "tomo" / "profiles"),
                 "--run-id", RUN, "--output", str(ctx), "--skip-reconcile")
    assert " eligible=2 excluded=1 " in built.stderr

    # ── read: names, then a nominated subset ────────────────────────────────
    names = json.loads(_run(str(SCRIPTS / "read-shared-ctx.py"), "--ctx", str(ctx),
                            "--run-id", RUN, "--moc-names").stdout)
    assert names == ["Vacation (MOC)", "Wine (MOC)"]  # the excluded MOC is not offered
    items = tmp_path / "items"
    items.mkdir()
    stem = to_filename(ITEM_KEY)[: -len(".result.json")]
    nominated = items / f"{stem}.moc-names.txt"
    nominated.write_text("vacation (moc)\n", encoding="utf-8")
    fetched = json.loads(_run(str(SCRIPTS / "read-shared-ctx.py"), "--ctx", str(ctx), "--run-id", RUN,
                              "--mocs-from", str(nominated)).stdout)
    assert [m["path"] for m in fetched["mocs"]] == [VACATION]
    assert fetched["mocs"][0]["headings"] == [{"text": "Trips", "level": 2}]

    # ── analyst: proposes "Vacations" although the MOC exists ───────────────
    action = {
        "kind": "create_atomic_note", "suggested_title": "Herbstferien an der Mosel",
        "atomic_note_worthiness": 0.8, "template": "t_note_tomo", "location": "Atlas/202 Notes/",
        "candidate_mocs": [{"path": WINE, "score": 0.3, "pre_check": False}],
        "needs_new_moc": True, "proposed_moc_topic": "Vacations", "tags_to_add": [],
        "classification": {"category": "900 History & Geography", "confidence": 0.8}, "alternatives": [],
    }
    (items / to_filename(ITEM_KEY)).write_text(json.dumps({
        "schema_version": "1", "stem": "Herbstferien", "path": ITEM_KEY, "item_key": ITEM_KEY,
        "type": "fleeting_note", "type_confidence": 0.9, "force_atomic": False, "actions": [action],
        "candidate_mocs": action["candidate_mocs"], "classification": action["classification"],
        "needs_new_moc": True, "proposed_moc_topic": "Vacations", "tags_to_add": [],
        "atomic_note_worthiness": 0.8, "alternatives": [], "issues": [], "duration_ms": 0,
    }), encoding="utf-8")
    state = tmp_path / "state.jsonl"
    state.write_text(json.dumps({"stem": "Herbstferien", "path": ITEM_KEY, "item_key": ITEM_KEY,
                                 "status": "done", "run_id": RUN, "ts": "2026-10-24T10:00:00Z"}) + "\n",
                     encoding="utf-8")

    # ── reduce ───────────────────────────────────────────────────────────────
    doc = tmp_path / "suggestions-doc.json"
    reduced = _run(str(SCRIPTS / "suggestions-reducer.py"), "--state", str(state), "--items-dir", str(items),
                   "--run-id", RUN, "--profile", "miyo", "--shared-ctx", str(ctx),
                   "--output", str(doc), "--no-kado")
    assert "duplicate_proposals_converted=1 proposed_mocs=0 " in reduced.stderr

    # ── render ───────────────────────────────────────────────────────────────
    md, wire = tmp_path / "suggestions.md", tmp_path / "suggestions-wire.json"
    _run(str(SCRIPTS / "suggestions-render.py"), "--input", str(doc), "--output", str(md),
         "--json-output", str(wire))
    text = md.read_text(encoding="utf-8")
    assert "- [ ] [[Atlas/200 Maps/Vacation (MOC)]]" in text
    assert "No good thematic MOC matched" not in text
    assert "## Proposed MOCs" not in text and "### Proposed MOC:" not in text
    assert "- Proposed MOCs: 0" in text

    wire_doc = json.loads(wire.read_text(encoding="utf-8"))
    (suggestion,) = [s for s in wire_doc["suggestions"] if s.get("candidate_mocs")]
    by_path = {c["path"]: c for c in suggestion["candidate_mocs"]}
    assert list(by_path) == [WINE, VACATION]  # the analyst's own first, the existing MOC appended
    assert by_path[VACATION]["selected"] is False and by_path[VACATION]["source"] == "tomo"
    assert INDEX not in by_path
    assert not wire_doc.get("proposed_mocs")
