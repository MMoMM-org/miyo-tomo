#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t6_4c_withheld_clash_staging_residue.py — spec 034 T6.4c.

Pass 2 renders each approved atomic to a local staging file and lists it in
`manifest.json`; a second process, `upload-rendered.py`, writes one vault note
per manifest entry. When a guard withholds a move, no `move_note` reaches
Hashi — but the manifest still names the staging note, so the upload writes a
file into the inbox that nothing will ever move. Observed live on 2026-09-09:
two `2026-09-08_1813_elbe-schifffahrt-*` files, one per withheld claimant.

The assertions below are taken at the **vault write surface** — the targets
`upload-rendered.py` hands to Kado — not at any internal list. A fix that only
trims an in-memory structure while the upload still writes the file would pass
an internal-list assertion and leave the residue exactly where it is.

What each block pins:

  1. A destination clash withholds both claimants -> neither staging note is
     written to the vault. Both were still rendered to disk: the run refused
     to upload them, it did not fail to produce them.
  2. The same for `suppress_moves_for_unfiled_attachments`. It withholds a
     move through the same helper and leaves the same residue; the task text
     names only the clash, the shape has two sites.
  3. A run with no withholding writes every staging note, and its manifest is
     byte-identical to the pre-fix artefact — the common path must not move.
  4. Renaming one item and re-running does not accumulate: the clash run
     uploads nothing, the corrected run uploads both, so the vault never holds
     a pair nobody will move.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ir = _load("instruction_render", "instruction-render.py")
up = _load("upload_rendered", "upload-rendered.py")

INBOX = "100 Inbox"
NOTES = "200 Notes/"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _item(item_id: str, title: str, *, source: str, attachments=None) -> dict:
    return {
        "id": item_id,
        "action": "create_note",
        "title": title,
        "template": "templates/atomic.md",
        "source_path": source,
        "item_key": f"{INBOX}/{source}",
        "tags": [],
        "parent_moc": "",
        "parent_mocs": [],
        "destination": NOTES,
        "summary": "",
        "attachments": attachments or [],
    }


CLASHING = [
    _item("item-1", "Elbe Schifffahrt", source="Reise/Dresden.md"),
    _item("item-2", "Elbe Schifffahrt", source="Places/Dresden.md"),
]

DISTINCT = [
    _item("item-1", "Elbe Schifffahrt", source="Reise/Dresden.md"),
    _item("item-2", "Elbe Radweg", source="Places/Dresden.md"),
]

# Two notes embedding a same-basename attachment from different folders: the
# second attachment is refused as a destination collision, which keeps its
# owning note in the inbox (T5.4) and withholds that note's move.
ATTACHMENT_COLLISION = [
    _item(
        "item-1", "Elbe Schifffahrt", source="Reise/Dresden.md",
        attachments=[f"{INBOX}/Reise/photo.png"],
    ),
    _item(
        "item-2", "Elbe Radweg", source="Places/Dresden.md",
        attachments=[f"{INBOX}/Places/photo.png"],
    ),
]


# ---------------------------------------------------------------------------
# Harness — real build_actions and real guards; only the Kado seams are faked
# ---------------------------------------------------------------------------


def _run_render(monkeypatch, tmp_path: Path, items: list[dict], out_name: str) -> Path:
    """Run instruction-render end-to-end with both guards live. Returns out_dir."""
    suggestions_file = tmp_path / f"{out_name}_suggestions.json"
    suggestions_file.write_text(
        json.dumps({"confirmed_items": items, "daily_updates": [], "skipped": []}),
        encoding="utf-8",
    )
    cfg_file = tmp_path / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        ir, "load_config",
        lambda _path: {
            "concepts.inbox": INBOX,
            "concepts.asset": "Atlas/290 Assets/295 Attachments/",
            "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
            "daily_log.heading": "Daily Log",
            "daily_log.heading_level": 2,
            "profile": "miyo",
            "callouts.editable": ["NOTE", "IDEAS"],
        },
    )
    monkeypatch.setattr(ir, "KadoClient", lambda: MagicMock())
    monkeypatch.setattr(ir, "read_template", lambda _client, _ref: "# {{title}}\n")
    monkeypatch.setattr(ir, "read_note_body", lambda _client, _path: "body\n")
    monkeypatch.setattr(
        ir, "render_via_script",
        lambda _tmpl, _tokens, _cfg: "---\ntags: []\n---\n# Rendered\nbody\n",
    )
    # #116 drops items whose source note cannot be read; every item here is
    # present by construction.
    monkeypatch.setattr(
        ir, "filter_missing_source_notes", lambda confirmed, _c, _i: (confirmed, [])
    )
    # The vault half of the clash guard reads folders; this run has no vault.
    # The run-internal half — the half under test — stays live.
    monkeypatch.setattr(ir, "make_folder_listing", lambda _client: (lambda _folder: {}))
    monkeypatch.setattr(ir, "resolve_target_moc_paths", lambda _actions, _client: 0)
    monkeypatch.setattr(ir, "resolve_section_names", lambda *_a, **_kw: 0)
    monkeypatch.setattr(ir, "_rewrite_existing_section_anchors", lambda _a, _c: 0)
    monkeypatch.setattr(ir, "filter_missing_daily_notes", lambda actions, _c: (actions, []))
    monkeypatch.setattr(ir, "_validate_action_paths", lambda _actions: [])
    monkeypatch.setattr(ir, "backfill_supporting_items_parents", lambda _items: None)

    out_dir = tmp_path / out_name
    monkeypatch.setattr(
        sys, "argv",
        [
            "instruction-render.py",
            "--suggestions", str(suggestions_file),
            "--output-dir", str(out_dir),
            "--config", str(cfg_file),
            "--run-id", "2026-09-09-101500-t64c",
        ],
    )
    rc = ir.main()
    assert isinstance(rc, int)
    return out_dir


def _upload(monkeypatch, out_dir: Path) -> list[str]:
    """Run upload-rendered against out_dir. Returns the vault targets written."""
    written: list[str] = []

    class _FakeClient:
        def write_note(self, target, body):  # noqa: D102
            written.append(target)

        def write_file(self, target, payload):  # noqa: D102
            written.append(target)

    monkeypatch.setattr(up, "KadoClient", lambda: _FakeClient())
    monkeypatch.setattr(
        sys, "argv",
        [
            "upload-rendered.py",
            "--rendered-dir", str(out_dir),
            "--inbox", f"{INBOX}/",
            "--upload-delay", "0",
        ],
    )
    assert up.main() == 0
    return written


def _staging_targets(written: list[str]) -> list[str]:
    """The uploaded staging notes — everything that is not an instruction artefact."""
    return [
        t for t in written
        if not t.endswith("_instructions.md") and not t.endswith("_instructions.json")
    ]


def _rendered_on_disk(out_dir: Path) -> list[str]:
    return sorted(
        p.name for p in out_dir.glob("*.md") if p.name != "instructions.md"
    )


# ---------------------------------------------------------------------------
# 1. A withheld destination clash uploads no staging note
# ---------------------------------------------------------------------------


def test_withheld_clash_uploads_no_staging_note(monkeypatch, tmp_path):
    """Both claimants are withheld, so neither staging note reaches the vault.

    Asserted at the write surface: the targets upload-rendered hands to Kado.
    """
    out_dir = _run_render(monkeypatch, tmp_path, CLASHING, "clash")

    instructions = json.loads((out_dir / "instructions.json").read_text(encoding="utf-8"))
    clashes = (instructions.get("tomo") or {}).get("destination_clashes") or []
    assert clashes, "fixture must produce a destination clash"
    assert sum(len(c["dropped"]) for c in clashes) == 2

    written = _upload(monkeypatch, out_dir)
    assert _staging_targets(written) == []

    # The notes WERE rendered — the run refused to upload them, it did not
    # fail to produce them. Without this the assertion above passes for a
    # renderer that simply crashed.
    assert len(_rendered_on_disk(out_dir)) == 2


# ---------------------------------------------------------------------------
# 2. The same for an attachment suppression — the second site of the shape
# ---------------------------------------------------------------------------


def test_withheld_attachment_suppression_uploads_no_staging_note(monkeypatch, tmp_path):
    """A note kept in the inbox for an unfiled attachment leaves no staging note.

    `suppress_moves_for_unfiled_attachments` withholds its move through the same
    helper as the clash guard and produces the same `dropped` record, so it
    leaves the same residue.
    """
    out_dir = _run_render(monkeypatch, tmp_path, ATTACHMENT_COLLISION, "attach")

    instructions = json.loads((out_dir / "instructions.json").read_text(encoding="utf-8"))
    suppressions = (instructions.get("tomo") or {}).get("attachment_suppressions") or []
    assert suppressions, "fixture must produce an attachment suppression"
    withheld = sum(len(s["dropped"]) for s in suppressions)
    assert withheld == 1

    written = _upload(monkeypatch, out_dir)
    # Exactly the note whose move survived is uploaded; the suppressed one is not.
    assert len(_staging_targets(written)) == 2 - withheld
    assert len(_rendered_on_disk(out_dir)) == 2


# ---------------------------------------------------------------------------
# 3. A run with no withholding is unchanged
# ---------------------------------------------------------------------------


def test_no_clash_run_uploads_every_staging_note(monkeypatch, tmp_path):
    """Nothing withheld -> every rendered note is uploaded, manifest untouched."""
    out_dir = _run_render(monkeypatch, tmp_path, DISTINCT, "clean")

    instructions = json.loads((out_dir / "instructions.json").read_text(encoding="utf-8"))
    tomo_block = instructions.get("tomo") or {}
    assert not tomo_block.get("destination_clashes")
    assert not tomo_block.get("attachment_suppressions")

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 2

    written = _upload(monkeypatch, out_dir)
    assert sorted(_staging_targets(written)) == sorted(
        f"{INBOX}/{e['rendered_file']}" for e in manifest
    )
    assert len(_staging_targets(written)) == 2


# ---------------------------------------------------------------------------
# 4. Re-running after the user renames one item does not accumulate a pair
# ---------------------------------------------------------------------------


def test_rerun_after_rename_does_not_accumulate(monkeypatch, tmp_path):
    """The clash run leaves nothing behind, so the corrected re-run is the only
    thing that ever writes a staging note. The remedy the document prints
    ("give one of them a different name and re-run Pass 2") must not deposit a
    fresh orphaned pair on every attempt.
    """
    clash_dir = _run_render(monkeypatch, tmp_path, CLASHING, "run1")
    first = _staging_targets(_upload(monkeypatch, clash_dir))
    assert first == []

    fixed_dir = _run_render(monkeypatch, tmp_path, DISTINCT, "run2")
    second = _staging_targets(_upload(monkeypatch, fixed_dir))
    assert len(second) == 2

    # Nothing from the clash run is still claiming an inbox path.
    assert not set(first) & set(second)
    assert len(first) + len(second) == 2


# ---------------------------------------------------------------------------
# 5. A claim that was never built is not a withheld claim
# ---------------------------------------------------------------------------


def test_entry_never_claimed_by_an_action_is_kept():
    """An entry no action ever claimed is kept — nothing withheld it.

    Without the pre-guard claim set, "no surviving action" and "no action was
    ever built" are the same observation here, and a run whose action building
    produced nothing would have its whole manifest emptied.
    """
    from lib.render_actions import manifest_without_withheld_staging

    manifest = [{"rendered_file": "a.md"}, {"rendered_file": "b.md"}]

    kept, withheld = manifest_without_withheld_staging(manifest, [], set())
    assert kept == manifest
    assert withheld == []

    # Same input, but `a.md` did have a claim before the guards ran.
    kept, withheld = manifest_without_withheld_staging(manifest, [], {"a.md"})
    assert withheld == ["a.md"]
    assert kept == [{"rendered_file": "b.md"}]
