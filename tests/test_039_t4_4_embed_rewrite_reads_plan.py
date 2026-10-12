#!/usr/bin/env python3
"""test_039_t4_4_embed_rewrite_reads_plan.py — spec 039 T4.4.

`rewrite_attachment_embeds(body, attachments, plan)` (`lib/embed_rewrite.py`)
writes the attachment plan's (K1) embed text and decides nothing itself.
Before this task the rewrite decided on its own: it matched by basename alone
and always wrote a bare name, so an owner's `![[Other/karte.png]]` pointing at
a different file became `![[karte (2).png]]` (research R1 §3, measured), an
ambiguous basename was never qualified (F4-AC2/AC3), and a move withheld for a
run-level `collision` still had its embed rewritten (backlog, spec 038 T4.3).

Matching rule pinned here: an embed belongs to a source only if it resolves to
that source by the resolver's own rule (`narrow_candidates`): a bare basename
matches by basename; a written path matches when the source path equals it or
ends with `/<written path>` (segment boundary) — so `Scans/karte.png` and
`100 Inbox/Scans/karte.png` both reach `100 Inbox/Scans/karte.png`, and
`Other/karte.png` or `cans/karte.png` do not.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from attachment_plan_fakes import FakeVault, plan_from_remedies  # noqa: E402
from lib.embed_rewrite import rewrite_attachment_embeds  # noqa: E402

INBOX = "100 Inbox/"
ASSET = "Atlas/290 Assets/295 Attachments/"
SOURCE = "100 Inbox/Scans/karte.png"
DEFAULT_TARGET = f"{ASSET}karte.png"


def _rename(name, *, source=SOURCE, owner=False, folder=None) -> dict:
    remedy = {
        "source": source, "remedy": "rename", "proposed_name": name,
        "name_is_owner_supplied": owner,
    }
    if folder is not None:
        remedy["proposed_dir"] = folder
        remedy["dir_is_owner_supplied"] = True
    return remedy


def _plan(attachments, remedies=(), *, vault=None):
    return plan_from_remedies(
        [{"attachments": list(attachments)}], list(remedies),
        inbox_path=INBOX, asset_folder=ASSET, vault=vault,
    )


# ---------------------------------------------------------------------------
# F4-AC1 — unique basenames: bare when renamed, untouched when not
# ---------------------------------------------------------------------------

def test_renamed_and_unique_writes_the_bare_new_name_byte_identical_to_037():
    """F4-AC1: today's output exactly. Mutation: always write `plan.embed`
    as a full path — the bare name would be lost."""
    body = "See: ![[Scans/karte.png]]\nAgain ![[karte.png]]\n"
    plan = _plan([SOURCE], [_rename("karte (2).png")])
    assert plan.by_source[SOURCE].embed == "karte (2).png"
    assert rewrite_attachment_embeds(body, [SOURCE], plan) == (
        "See: ![[karte (2).png]]\nAgain ![[karte (2).png]]\n"
    )


def test_unrenamed_and_unique_leaves_the_body_untouched():
    """CON-3: an attachment filed under its own unique name changes no byte."""
    body = "![[Scans/karte.png]] and ![[karte.png|300]]\n"
    plan = _plan([SOURCE])
    decision = plan.by_source[SOURCE]
    assert decision.target == DEFAULT_TARGET and decision.embed is None
    assert rewrite_attachment_embeds(body, [SOURCE], plan) == body


# ---------------------------------------------------------------------------
# F4-AC2 / F4-AC3 — ambiguous basenames are qualified
# ---------------------------------------------------------------------------

def test_ambiguous_unrenamed_default_folder_gets_the_full_path():
    """F4-AC3: no rename, default folder, but another `karte.png` stays in
    the vault after the run. Mutation: ignore `plan.embed` and always write
    the bare final name — the embed would stay `karte.png`, ambiguous."""
    vault = FakeVault([SOURCE, "Archive/karte.png"], existing_folders=[ASSET])
    plan = _plan([SOURCE], vault=vault)
    assert plan.by_source[SOURCE].qualified_reason == "ambiguous"
    body = "![[karte.png]] and ![[Scans/karte.png]]\n"
    assert rewrite_attachment_embeds(body, [SOURCE], plan) == (
        f"![[{DEFAULT_TARGET}]] and ![[{DEFAULT_TARGET}]]\n"
    )


def test_ambiguous_renamed_gets_the_full_new_path():
    """F4-AC2: the new name also exists elsewhere after the run."""
    vault = FakeVault(
        [SOURCE, "Elsewhere/karte (2).png"], existing_folders=[ASSET],
    )
    plan = _plan([SOURCE], [_rename("karte (2).png")], vault=vault)
    body = "![[Scans/karte.png]]"
    assert rewrite_attachment_embeds(body, [SOURCE], plan) == (
        f"![[{ASSET}karte (2).png]]"
    )


def test_suffixes_and_extension_survive_qualification_and_no_alias_is_added():
    """F4-AC5: `|300`, `|alias`, `#heading` kept verbatim; the extension is
    kept; nothing is appended (unlike a note link's `qualified_target`)."""
    vault = FakeVault([SOURCE, "Archive/karte.png"], existing_folders=[ASSET])
    plan = _plan([SOURCE], vault=vault)
    body = (
        "![[Scans/karte.png|300]]\n"
        "![[karte.png|Site Map]]\n"
        "![[karte.png#Legend]]\n"
        "![[karte.png]]\n"
    )
    assert rewrite_attachment_embeds(body, [SOURCE], plan) == (
        f"![[{DEFAULT_TARGET}|300]]\n"
        f"![[{DEFAULT_TARGET}|Site Map]]\n"
        f"![[{DEFAULT_TARGET}#Legend]]\n"
        f"![[{DEFAULT_TARGET}]]\n"
    )


def test_original_name_into_a_new_folder_is_qualified_when_ambiguous():
    """F1-AC10: the owner keeps `karte.png` and changes only the folder; the
    occupier at the default destination still holds the name."""
    vault = FakeVault([SOURCE, DEFAULT_TARGET], existing_folders=["Atlas/296 Maps"])
    plan = _plan([SOURCE], [_rename("karte.png", folder="Atlas/296 Maps")], vault=vault)
    assert plan.by_source[SOURCE].target == "Atlas/296 Maps/karte.png"
    assert rewrite_attachment_embeds("![[karte.png]]", [SOURCE], plan) == (
        "![[Atlas/296 Maps/karte.png]]"
    )


def test_original_name_into_a_new_folder_is_untouched_when_unique():
    """F1-AC10's other polarity: nothing else holds `karte.png` → the bare
    name the note already wrote still resolves; no byte changes."""
    vault = FakeVault([SOURCE], existing_folders=["Atlas/296 Maps"])
    plan = _plan([SOURCE], [_rename("karte.png", folder="Atlas/296 Maps")], vault=vault)
    assert rewrite_attachment_embeds("![[karte.png]]", [SOURCE], plan) == "![[karte.png]]"


# ---------------------------------------------------------------------------
# Matching by path (R1 §3)
# ---------------------------------------------------------------------------

def test_a_written_path_pointing_elsewhere_is_not_rewritten():
    """R1 §3, measured: `![[Other/karte.png]]` names a different file that
    happens to share the basename. Mutation: match by basename alone (the
    0.4.2 rule) — it would become `![[karte (2).png]]`."""
    plan = _plan([SOURCE], [_rename("karte (2).png")])
    body = "![[Other/karte.png]] vs ![[karte.png]]"
    assert rewrite_attachment_embeds(body, [SOURCE], plan) == (
        "![[Other/karte.png]] vs ![[karte (2).png]]"
    )


def test_full_and_partial_paths_to_the_source_are_rewritten():
    """A path matches when the source equals it or ends with `/<path>`."""
    plan = _plan([SOURCE], [_rename("karte (2).png")])
    body = "![[100 Inbox/Scans/karte.png]] ![[Scans/karte.png|300]]"
    assert rewrite_attachment_embeds(body, [SOURCE], plan) == (
        "![[karte (2).png]] ![[karte (2).png|300]]"
    )


def test_a_partial_path_must_end_on_a_folder_boundary():
    """`cans/karte.png` is a string suffix of the source but no path suffix."""
    plan = _plan([SOURCE], [_rename("karte (2).png")])
    body = "![[cans/karte.png]]"
    assert rewrite_attachment_embeds(body, [SOURCE], plan) == body


def test_a_bare_name_shared_by_two_of_the_notes_attachments_is_left_alone():
    """Two of the note's attachments share the basename: a bare embed does
    not resolve to either, so it is not rewritten for either."""
    other = "100 Inbox/Other/karte.png"
    plan = _plan(
        [SOURCE, other],
        [_rename("karte (2).png"), _rename("karte (3).png", source=other)],
    )
    body = "![[karte.png]] ![[Other/karte.png]]"
    assert rewrite_attachment_embeds(body, [SOURCE, other], plan) == (
        "![[karte.png]] ![[karte (3).png]]"
    )


# ---------------------------------------------------------------------------
# F4-AC8 — a withheld move rewrites nothing
# ---------------------------------------------------------------------------

def test_a_run_level_collision_rewrites_nothing():
    """Backlog (spec 038 T4.3): two attachments renamed onto one target —
    the second is withheld `collision`; its note's body stayed rewritten to
    the first's filename. Mutation: rewrite from the remedy instead of from
    the plan's target — `![[B/other.png]]` becomes `![[karte (2).png]]`."""
    first = "100 Inbox/A/karte.png"
    second = "100 Inbox/B/other.png"
    plan = plan_from_remedies(
        [{"attachments": [first]}, {"attachments": [second]}],
        [_rename("karte (2).png", source=first),
         _rename("karte (2).png", source=second)],
        inbox_path=INBOX, asset_folder=ASSET,
    )
    assert plan.by_source[second].withheld["kind"] == "collision"
    body = "![[B/other.png]] ![[other.png|300]]"
    assert rewrite_attachment_embeds(body, [second], plan) == body


def test_a_kept_or_refused_attachment_rewrites_nothing():
    """Withheld for keep-in-inbox or a refused typed name → untouched, even
    when the occupier makes the basename ambiguous."""
    vault = FakeVault([SOURCE, DEFAULT_TARGET], existing_folders=[ASSET])
    body = "![[karte.png]]"
    for remedy in (
        {"source": SOURCE, "remedy": "keep_in_inbox", "proposed_name": "karte (2).png"},
        _rename("karte|1938.png", owner=True),
        _rename("Archive/x.png", owner=True),
    ):
        plan = _plan([SOURCE], [remedy], vault=vault)
        assert plan.by_source[SOURCE].target is None
        assert rewrite_attachment_embeds(body, [SOURCE], plan) == body


def test_a_source_the_plan_does_not_know_is_a_wiring_error():
    """The plan covers every attachment of every rendered note. A miss would
    leave the body untouched while the move renames the file — a broken embed
    with no signal. Mutation: `plan.by_source.get(path)` with a None skip."""
    plan = _plan(["100 Inbox/elsewhere.png"])
    with pytest.raises(ValueError, match="100 Inbox/Scans/karte.png"):
        rewrite_attachment_embeds("![[karte.png]]", [SOURCE], plan)


def test_a_path_embedded_under_two_spellings_is_still_rewritten():
    """Triage dedupes embeds by typed string, so `![[karte.png]]` and
    `![[Scans/karte.png]]` give `attachments == [SOURCE, SOURCE]`. Mutation:
    index each list entry — two candidates, neither embed is rewritten."""
    plan = _plan([SOURCE], [_rename("karte (2).png")])
    body = "![[karte.png]] and ![[Scans/karte.png|300]]"
    assert rewrite_attachment_embeds(body, [SOURCE, SOURCE], plan) == (
        "![[karte (2).png]] and ![[karte (2).png|300]]"
    )


def test_fenced_examples_and_plain_links_are_untouched_when_qualified():
    vault = FakeVault([SOURCE, "Archive/karte.png"], existing_folders=[ASSET])
    plan = _plan([SOURCE], vault=vault)
    body = "```\n![[karte.png]]\n```\n[[karte.png]] ![[karte.png]]\n"
    assert rewrite_attachment_embeds(body, [SOURCE], plan) == (
        f"```\n![[karte.png]]\n```\n[[karte.png]] ![[{DEFAULT_TARGET}]]\n"
    )


def test_the_rewrite_decides_nothing_of_its_own():
    """Phase 4 Key Decision: K1 is the only decision site."""
    source = (SCRIPTS_DIR / "lib" / "embed_rewrite.py").read_text(encoding="utf-8")
    for token in ("check_typed_name", "remedy ==", "claimed"):
        assert token not in source, token


# ---------------------------------------------------------------------------
# The render loop reads the plan — every owning note (F4-AC2, Rule 6)
# ---------------------------------------------------------------------------

_spec = importlib.util.spec_from_file_location(
    "instruction_render_t039_t4_4", SCRIPTS_DIR / "instruction-render.py"
)
ir = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["instruction_render_t039_t4_4"] = ir
_spec.loader.exec_module(ir)

_IR_CFG = {
    "concepts.inbox": INBOX,
    "concepts.asset": ASSET,
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
    "callouts.editable": ["NOTE"],
}


def _run_main(monkeypatch, tmp_path, items, remedies, vault):
    suggestions = {
        "confirmed_items": items, "daily_updates": [], "skipped": [],
        "attachment_conflict_remedies": remedies,
    }
    suggestions_file = tmp_path / "suggestions.json"
    suggestions_file.write_text(json.dumps(suggestions), encoding="utf-8")
    cfg_file = tmp_path / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(ir, "load_config", lambda _path: dict(_IR_CFG))
    monkeypatch.setattr(ir, "KadoClient", lambda: MagicMock())
    monkeypatch.setattr(ir, "VaultFolderLookup", lambda _client: vault.lookup)
    monkeypatch.setattr(ir, "make_basename_census", lambda _client: vault.census)
    monkeypatch.setattr(ir, "read_template", lambda _c, _r: "# {{title}}\n{{body}}\n")
    monkeypatch.setattr(ir, "read_note_body", lambda *_a, **_kw: "")
    monkeypatch.setattr(
        ir, "render_via_script",
        lambda *_a, **_kw: "Map: ![[karte.png|300]]\n",
    )
    out_dir = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", [
        "instruction-render.py", "--suggestions", str(suggestions_file),
        "--output-dir", str(out_dir), "--config", str(cfg_file),
    ])
    assert ir.main() == 0
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    return [
        (out_dir / e["rendered_file"]).read_text(encoding="utf-8") for e in manifest
    ]


def _item(item_id, source_path):
    return {
        "id": item_id, "action": None, "title": item_id,
        "template": "templates/atomic.md", "source_path": source_path,
        "tags": [], "parent_moc": "", "parent_mocs": [],
        "destination": "Atlas/202 Notes/", "summary": "",
        "attachments": [SOURCE], "candidate_mocs": [],
    }


def test_every_owning_note_gets_the_qualified_embed_through_the_render_loop(
    monkeypatch, tmp_path
):
    """Two notes embed one ambiguous attachment: both written files carry
    the full path. Mutation: the render loop keeps the remedy-driven rewrite
    (0.4.2) — both notes stay `![[karte.png|300]]`."""
    vault = FakeVault([SOURCE, "Archive/karte.png"], existing_folders=[ASSET])
    written = _run_main(
        monkeypatch, tmp_path,
        [_item("S01", "kai.md"), _item("S02", "zwei.md")], [], vault,
    )
    assert len(written) == 2
    for text in written:
        assert f"![[{DEFAULT_TARGET}|300]]" in text, text


def test_a_unique_unrenamed_attachment_leaves_the_written_note_untouched(
    monkeypatch, tmp_path
):
    vault = FakeVault([SOURCE], existing_folders=[ASSET])
    written = _run_main(monkeypatch, tmp_path, [_item("S01", "kai.md")], [], vault)
    assert len(written) == 1
    assert "Map: ![[karte.png|300]]\n" in written[0]
    assert DEFAULT_TARGET not in written[0]
