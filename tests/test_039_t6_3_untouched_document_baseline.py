#!/usr/bin/env python3
"""test_039_t6_3_untouched_document_baseline.py — spec 039 T6.3 close-out (F1-AC7).

PRD F1-AC7: an untouched suggestions document, read by Pass 2, gives today's
output byte for byte — provided every basename it files is unique in the vault,
every target is free and Kado answers. No test compared Pass 2's whole output
for such a document with the output of the code before spec 039; the
close-out's trace found that gap, and this file closes it.

One harness (`run_untouched`) drives the real Pass-1 conflict block, the real
markdown parser join and the real `instruction-render.py main()` over one
source tree. `tests/fixtures/039-t6-3-untouched-baseline/record.py` ran it on
the merge-base `d583cd31` (spec 038 as merged, before any 039 commit) and
froze the result in `expected.json`; the test replays it on this tree.

The document: three notes, each with one attachment. `karte.png` is a conflict
left on its pre-ticked Rename (computed name, default folder), `plan.png` has
no conflict, `foto.png` is a conflict with no free name, left on Keep in inbox.
Every basename the run files is unique and every target free.

The output is byte-identical to the baseline except in two places, and the
test pins both exactly, so a third difference fails it:

1. Each origin's `delete_source.depends_on` also names the `move_asset` of the
   attachment its note embeds (F6-AC1, ADR-10, Kokoro ADR-029 section 7). The
   PRD's F1-AC7 proviso names it (amended by the owner 2026-10-13).
2. The Keep-in-inbox bullet's remedy reads as the T5.4 owner ruling worded it
   (2026-10-12/13: one remedy per withheld kind, `--pass2 --force` before
   apply). CON-5 names the T5.4 supersessions; this sentence is one of them.

Mechanism falsified: "an untouched document changes Pass 2's output". Mutation
proven RED in an isolated `git archive` copy: drop the subtraction of this
run's moved inbox copies from the basename census (`lib/attachment_plan.py`),
so `plan.png` counts its own inbox copy, reads as ambiguous, and its owning
note's bare embed is written with a path.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
FIXTURE = TESTS_DIR / "fixtures" / "039-t6-3-untouched-baseline" / "expected.json"

INBOX = "100 Inbox/"
ASSET = "Atlas/290 Assets/295 Attachments/"
NOTES = "Atlas/202 Notes"
RENAMED = "100 Inbox/Scans/karte.png"
PLAIN = "100 Inbox/Scans/plan.png"
KEPT = "100 Inbox/Scans/foto.png"
OCCUPIERS = [f"{ASSET}karte.png", f"{ASSET}foto.png"]
FROZEN_NOW = "2026-10-12T09:00:00Z"

CONFLICTS = [
    {"source": RENAMED, "destination": f"{ASSET}karte.png", "same_file": False,
     "owner_source_items": [f"{INBOX}Eins.md"], "proposed_name": "karte (2).png",
     "proposed_dir": None},
    {"source": KEPT, "destination": f"{ASSET}foto.png", "same_file": False,
     "owner_source_items": [f"{INBOX}Drei.md"], "proposed_name": None,
     "proposed_dir": None},
]

_CFG = {
    "concepts.inbox": INBOX, "concepts.asset": ASSET,
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log", "daily_log.heading_level": 2,
    "profile": "miyo", "callouts.editable": ["NOTE"],
}


class _Frozen(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 12, 9, 0, 0, tzinfo=tz or timezone.utc)


def _parent(path: str) -> str:
    return path.rstrip("/").rpartition("/")[0]


def _item(idx: int, title: str, attachment: str) -> dict:
    return {
        "id": f"S{idx:02d}", "action": "create_note", "title": title,
        "template": "templates/atomic.md", "source_path": f"{title}.md",
        "item_key": f"{INBOX}{title}.md", "tags": [], "parent_moc": "",
        "parent_mocs": [], "destination": NOTES + "/", "summary": "",
        "attachments": [attachment], "candidate_mocs": [],
    }


def _load(scripts_dir: Path, name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, scripts_dir / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def run_untouched(scripts_dir: Path, tmp_path: Path, monkeypatch) -> dict:
    """Pass 1 block → markdown parse → Pass 2 `main()` on `scripts_dir`'s tree.

    Returns `{"rc", "remedies", "files"}`; `files` maps each written file to
    its text. Shared by the test and by the fixture's `record.py`, so the
    recording and the replay are one harness.
    """
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from lib import doc_frontmatter
    from lib.kado_client import KadoNotFoundError

    reducer = _load(scripts_dir, "suggestions_reducer_t039_t6_3_b", "suggestions-reducer.py")
    parser = _load(scripts_dir, "suggestion_parser_t039_t6_3_b", "suggestion-parser.py")
    ir = _load(scripts_dir, "instruction_render_t039_t6_3_b", "instruction-render.py")

    files_in_vault = [RENAMED, PLAIN, KEPT, *OCCUPIERS]
    folders = {ASSET.rstrip("/"), NOTES}
    for path in files_in_vault:
        parts = path.split("/")
        folders.update("/".join(parts[:i]) for i in range(1, len(parts)))

    class Kado:
        def list_dir(self, folder, depth=1):
            name = folder.rstrip("/")
            if name not in folders:
                raise KadoNotFoundError(f"Path not found: {folder}")
            return ([{"path": p, "type": "file"} for p in files_in_vault
                     if _parent(p) == name]
                    + [{"path": f, "type": "folder"} for f in sorted(folders)
                       if f and _parent(f) == name])

        def _call_tool(self, tool, args):
            if tool == "kado-search" and args.get("operation") == "byName":
                query = args["query"]
                return {"items": [{"path": p} for p in files_in_vault
                                  if query in p.rsplit("/", 1)[-1].lower()]}
            return {"items": []}

        def search_by_name(self, stem):
            return []

        def read_note(self, path):
            return {"content": ""}

        def note_exists(self, path):
            return True

        def resolve_stem_to_path(self, stem):
            return None

    block = reducer.render_attachment_conflicts_block(CONFLICTS, ASSET)
    remedies = parser._join_attachment_conflict_remedies(
        parser.parse_attachment_conflict_remedies(block),
        {"attachment_conflicts": CONFLICTS},
    )
    suggestions = {
        "confirmed_items": [_item(1, "Eins", RENAMED), _item(2, "Zwei", PLAIN),
                            _item(3, "Drei", KEPT)],
        "daily_updates": [], "skipped": [], "attachment_conflict_remedies": remedies,
    }
    suggestions_file = tmp_path / "parsed-suggestions.json"
    suggestions_file.write_text(json.dumps(suggestions), encoding="utf-8")
    cfg_file = tmp_path / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")
    body_file = tmp_path / "upstream-body.md"
    body_file.write_text("# upstream\n", encoding="utf-8")

    monkeypatch.delenv("TOMO_VERSION", raising=False)
    monkeypatch.setattr(ir, "datetime", _Frozen)
    monkeypatch.setattr(doc_frontmatter, "_utc_now", lambda: FROZEN_NOW)
    monkeypatch.setattr(ir, "load_config", lambda _p: dict(_CFG))
    monkeypatch.setattr(ir, "load_tracker_fields", lambda _p: {})
    monkeypatch.setattr(ir, "KadoClient", Kado)
    monkeypatch.setattr(ir, "read_template", lambda _c, _r: "# {{title}}\n{{body}}\n")
    monkeypatch.setattr(ir, "read_note_body", lambda *_a, **_kw: "")
    monkeypatch.setattr(ir, "render_via_script",
                        lambda *_a, **_kw: "Map: ![[karte.png]] ![[plan.png]] ![[foto.png]]\n")
    out_dir = tmp_path / "rendered"
    monkeypatch.setattr(sys, "argv", [
        "instruction-render.py",
        "--suggestions", str(suggestions_file),
        "--output-dir", str(out_dir),
        "--config", str(cfg_file),
        "--upstream-type", "suggestions",
        "--upstream-path", "100 Inbox/2026-10-12_0900_suggestions.md",
        "--upstream-body", str(body_file),
        "--run-id", "2026-10-12-090000-t63",
        "--tag-handler-groups-dir", str(tmp_path / "no-groups"),
        "--shared-ctx", str(tmp_path / "no-shared-ctx.json"),
    ])
    rc = ir.main()
    files = {
        str(p.relative_to(out_dir)):
            p.read_text(encoding="utf-8").replace(str(out_dir), "<out>")
        for p in sorted(out_dir.rglob("*")) if p.is_file()
    }
    return {"rc": rc, "remedies": remedies, "files": files}


KEEP_IN_INBOX_LINE = (
    "- ⚠️ **Attachment not filed:** `100 Inbox/Scans/foto.png` — kept in inbox: "
    "the owner chose not to file it over the occupied destination "
    "`Atlas/290 Assets/295 Attachments/foto.png`. No action needed unless you "
    "change your mind. To file it after all, tick Rename in the suggestions "
    "document and run `/inbox --pass2 --force` before you apply. If you have "
    "already applied, rename the attachment in the inbox and run `/inbox` again."
)


def test_an_untouched_document_renders_todays_output_apart_from_two_sanctioned_changes(
    monkeypatch, tmp_path
):
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    actual = run_untouched(REPO_ROOT / "tomo" / "scripts", tmp_path, monkeypatch)
    assert actual["rc"] == expected["rc"] == 0
    assert sorted(actual["files"]) == sorted(expected["files"])

    # Every rendered note and the manifest: byte-identical (bare embeds, no path).
    for name in expected["files"]:
        if name not in ("instructions.json", "instructions.md"):
            assert actual["files"][name] == expected["files"][name], name

    # instructions.json: identical once each origin's delete is read without
    # the `move_asset` ids F6-AC1 appends — and those must be exactly the move
    # of the attachment that origin's note embeds.
    before = json.loads(expected["files"]["instructions.json"])
    after = json.loads(actual["files"]["instructions.json"])
    move_id = {a["source"]: a["id"] for a in after["actions"] if a["action"] == "move_asset"}
    assert sorted(move_id) == [RENAMED, PLAIN]
    embeds = {f"{INBOX}Eins.md": [move_id[RENAMED]], f"{INBOX}Zwei.md": [move_id[PLAIN]],
              f"{INBOX}Drei.md": []}
    old_deps = {a["source_path"]: a["depends_on"] for a in before["actions"]
                if a["action"] == "delete_source"}
    assert sorted(old_deps) == sorted(embeds)
    for action in after["actions"]:
        if action["action"] == "delete_source":
            origin = action["source_path"]
            assert action["depends_on"] == old_deps[origin] + embeds[origin], action
            action["depends_on"] = old_deps[origin]
    assert after == before

    # instructions.md: exactly one line differs — the Keep-in-inbox remedy.
    old_lines = expected["files"]["instructions.md"].splitlines()
    new_lines = actual["files"]["instructions.md"].splitlines()
    assert len(new_lines) == len(old_lines)
    changed = [i for i, (o, n) in enumerate(zip(old_lines, new_lines)) if o != n]
    assert len(changed) == 1, [(old_lines[i], new_lines[i]) for i in changed]
    assert new_lines[changed[0]] == KEEP_IN_INBOX_LINE
