#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t6_4a_fan_doc_identity_join.py — a fan document owns its own identity map.

Spec 034 (recursive inbox discovery), Phase 6 T6.4a. Found by the T6.4 live
run, not by the suite: a note in an inbox subfolder taken through **Force
Atomic Note** reached the renderer with `item_key: null` and could not be
filed.

    suggestions-fan.json   item_key "100 Inbox/Fotos/Kai.md"   correct
    parsed-suggestions.json item_key null, source_path "Kai"
    instruction-render.py  probes "100 Inbox/Kai.md", which does not exist

T5.0b joined the display stem back to an identity by reading
`sections[].item_key` out of the structured document the markdown was rendered
FROM. It resolved that document to `suggestions-doc.json` unconditionally, so a
*fan* document — rendered from `suggestions-fan-doc.json` — was bound against
the primary document's section map, where its own ids do not appear.

What this file pins:

  * a fan document whose item lives in a subfolder keeps its `item_key`,
    driven through the real parser on the MARKDOWN path — the path that
    matters, because the user edited the document and that is what makes it
    authoritative over the wire;
  * the resulting instruction set files that note to its destination instead
    of probing an inbox-root path — a key that never reaches an action is the
    shape this spec has been bitten by repeatedly;
  * both branches of the resolution: the sibling next to the markdown, and the
    cwd-relative `tomo-tmp/` fallback the standalone-fan invocation
    (`synthesis-conductor.md:117`, which passes no `--suggestions-doc`) takes;
  * a PRIMARY document still binds from the primary document, unchanged;
  * a fan document parsed beside a stale primary document does not bind a
    key from it.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

import test_034_t5_0_pass2_reads_item_key as T5  # noqa: E402
from lib.item_key import to_filename  # noqa: E402

# The live-run shape: one force-atomic note at the inbox root, one in a
# subfolder. Only the second can expose the defect, and the first proves the
# fix did not simply hard-code a folder.
FAN_ROOT = "100 Inbox/Kaffee.md"
FAN_DEEP = "100 Inbox/Fotos/Kai.md"

FAN_ITEMS: list[tuple[str, str, str]] = [
    ("Kaffee", FAN_ROOT, "Kaffee als Ritual"),
    ("Kai", FAN_DEEP, "Kai am Strand"),
]


def _force_atomic_result(stem: str, item_key: str, title: str) -> dict:
    """The analyst result the reducer's `--fan-resolve` filter keeps."""
    result = T5._atomic_result(stem, item_key, title)
    result["force_atomic"] = True
    return result


def _drive_fan(work: Path) -> Path:
    """state -> reducer --fan-resolve -> render, leaving doc + approved md.

    Returns the directory holding `suggestions-fan-doc.json` and
    `suggestions-fan-approved.md` side by side, which is how the pipeline
    writes them.
    """
    items_dir = work / "items"
    items_dir.mkdir(exist_ok=True)
    state_path = work / "inbox-state.jsonl"

    for stem, item_key, title in FAN_ITEMS:
        for status in ("pending", "running", "done"):
            T5._run([
                sys.executable, str(SCRIPTS_DIR / "state-update.py"),
                "--state", str(state_path),
                "--item-key", item_key,
                "--stem", stem,
                "--path", item_key,
                "--status", status,
                "--run-id", T5.RUN_ID,
            ])
        (items_dir / to_filename(item_key)).write_text(
            json.dumps(_force_atomic_result(stem, item_key, title),
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    doc_path = work / "suggestions-fan-doc.json"
    T5._run([
        sys.executable, str(SCRIPTS_DIR / "suggestions-reducer.py"),
        "--state", str(state_path),
        "--items-dir", str(items_dir),
        "--run-id", T5.RUN_ID,
        "--profile", "miyo",
        "--output", str(doc_path),
        "--shared-ctx", str(work / "absent-shared-ctx.json"),
        "--resolved-attachments", str(work / "absent-resolved.json"),
        "--tag-handler-groups-dir", str(work / "absent-thg"),
        "--threshold", "1",
        "--no-kado",
        "--fan-resolve",
    ])

    md_path = work / "suggestions-fan.md"
    T5._run([
        sys.executable, str(SCRIPTS_DIR / "suggestions-render.py"),
        "--input", str(doc_path),
        "--output", str(md_path),
        "--json-output", str(work / "suggestions-fan-wire.json"),
    ])

    text = md_path.read_text(encoding="utf-8").replace(
        "- [ ] Accept", "- [x] Accept"
    )
    (work / "suggestions-fan-approved.md").write_text(text, encoding="utf-8")
    return work


def _parse(md_path: Path, *, cwd: Path | None = None) -> dict:
    """The standalone-fan invocation: no --suggestions-doc, markdown only."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "suggestion-parser.py"),
         "--file", str(md_path)],
        capture_output=True, text=True, cwd=str(cwd) if cwd else None,
    )
    assert result.returncode == 0, f"parser failed:\n{result.stderr}"
    return json.loads(result.stdout)


def _keys_by_title(parsed: dict) -> dict[str, str | None]:
    return {c["title"]: c.get("item_key") for c in parsed["confirmed_items"]}


@pytest.fixture(scope="module")
def fan_work(tmp_path_factory) -> Path:
    return _drive_fan(tmp_path_factory.mktemp("t6_4a_fan"))


@pytest.fixture(scope="module")
def fan_doc_type(fan_work) -> str:
    """The provenance the fix dispatches on, read off the rendered document."""
    import importlib.util  # noqa: PLC0415

    spec = importlib.util.spec_from_file_location(
        "_t64a_parser", SCRIPTS_DIR / "suggestion-parser.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._extract_tomo_doc_type(
        (fan_work / "suggestions-fan-approved.md").read_text(encoding="utf-8")
    )


class TestTheFanDocumentDeclaresWhatItIs:
    def test_rendered_fan_markdown_carries_its_own_doc_type(self, fan_doc_type):
        """The fix needs no new plumbing — the provenance is already stamped."""
        assert fan_doc_type == "suggestions-fan"

    def test_the_structured_fan_doc_holds_the_subfolder_key(self, fan_work):
        """Guards the fixture: the key exists upstream, so a null downstream
        is a join failure and not an absent input."""
        doc = json.loads(
            (fan_work / "suggestions-fan-doc.json").read_text(encoding="utf-8")
        )
        assert {s["item_key"] for s in doc["sections"]} == {FAN_ROOT, FAN_DEEP}


class TestFanDocumentBindsItsOwnIdentity:
    """The markdown path — what the user edits, and what makes it authoritative."""

    def test_subfolder_note_keeps_its_key_from_the_sibling_doc(self, fan_work):
        keys = _keys_by_title(_parse(fan_work / "suggestions-fan-approved.md"))
        assert keys["Kai am Strand"] == FAN_DEEP

    def test_root_note_keeps_its_key_too(self, fan_work):
        keys = _keys_by_title(_parse(fan_work / "suggestions-fan-approved.md"))
        assert keys["Kaffee als Ritual"] == FAN_ROOT

    def test_display_stem_is_untouched(self, fan_work):
        """ADR-2: item_key is identity, source_path stays display text."""
        parsed = _parse(fan_work / "suggestions-fan-approved.md")
        assert sorted(c["source_path"] for c in parsed["confirmed_items"]) == [
            "Kaffee", "Kai",
        ]

    def test_subfolder_note_keeps_its_key_via_the_tomo_tmp_fallback(
        self, fan_work, tmp_path
    ):
        """`synthesis-conductor.md:117` runs the parser on a vault CACHE copy
        with no doc beside it, so the cwd-relative fallback is the branch the
        live run actually took."""
        cache = tmp_path / "cache"
        cache.mkdir()
        shutil.copy(
            fan_work / "suggestions-fan-approved.md", cache / "cached-fan.md"
        )
        instance = tmp_path / "instance"
        (instance / "tomo-tmp").mkdir(parents=True)
        shutil.copy(
            fan_work / "suggestions-fan-doc.json",
            instance / "tomo-tmp" / "suggestions-fan-doc.json",
        )
        keys = _keys_by_title(_parse(cache / "cached-fan.md", cwd=instance))
        assert keys["Kai am Strand"] == FAN_DEEP


class TestTheKeyReachesTheInstructionSet:
    """A correct key that never reaches an action is not a fix."""

    def _actions(self, fan_work) -> tuple[list[dict], list[dict]]:
        from lib.render_actions import build_actions  # noqa: PLC0415
        from lib.render_resolve import filter_missing_source_notes  # noqa: PLC0415

        parsed = _parse(fan_work / "suggestions-fan-approved.md")
        client = T5._exact_path_client({FAN_ROOT, FAN_DEEP})
        kept, dropped = filter_missing_source_notes(
            parsed["confirmed_items"], client, T5.INBOX
        )
        manifest = [
            {
                "id": c["id"], "action": "create_note", "title": c["title"],
                "source_path": c.get("source_path"), "item_key": c.get("item_key"),
                "audio_peer": None, "template": c.get("template"),
                "rendered_file": f"2026-09-08_1200_{c['id']}.md",
                "destination": c.get("destination") or "Atlas/202 Notes/",
                "parent_mocs": c.get("parent_mocs") or [], "attachments": [],
                "tags": c.get("tags") or [],
            }
            for c in kept
        ]
        actions, _ = build_actions(
            manifest, kept, parsed.get("daily_updates", []),
            parsed.get("skipped", []), T5.CFG, kado_client=None,
        )
        return kept, actions

    def test_the_subfolder_note_is_not_dropped_as_missing(self, fan_work):
        kept, _ = self._actions(fan_work)
        assert {c.get("item_key") for c in kept} == {FAN_ROOT, FAN_DEEP}

    def test_the_move_origin_is_the_subfolder_path_not_the_inbox_root(
        self, fan_work
    ):
        _kept, actions = self._actions(fan_work)
        origins = {
            a.get("source_inbox_item")
            for a in actions if a.get("action") == "move_note"
        }
        assert origins == {FAN_ROOT, FAN_DEEP}
        assert "100 Inbox/Kai.md" not in origins, (
            "the render reconstructed an inbox-root path that does not exist"
        )


class TestThePrimaryDocumentIsUnchanged:
    """The fix must not redirect the path that already works."""

    @pytest.fixture(scope="class")
    def primary_work(self, tmp_path_factory) -> dict:
        work = tmp_path_factory.mktemp("t6_4a_primary")
        return T5._drive(
            work,
            {key: T5._atomic_result(stem, key, title) for stem, key, title in T5.ITEMS},
            accept_all=True,
        )

    def test_primary_markdown_still_binds_from_the_primary_doc(self, primary_work):
        keys = _keys_by_title(_parse(primary_work["work"] / "suggestions-approved.md"))
        assert keys["Bohnen aus Äthiopien"] == T5.DEEP_1
        assert keys["Sapporo im Februar"] == T5.DEEP_2
        assert keys["Kaffee als Ritual"] == T5.ROOT_NOTE

    def test_a_fan_doc_beside_a_stale_primary_doc_binds_no_primary_key(
        self, fan_work, primary_work, tmp_path
    ):
        """Both documents number their sections independently, so an id can
        collide across them. The stem cross-check must reject the mismatch
        rather than name the wrong note."""
        instance = tmp_path / "stale-instance"
        (instance / "tomo-tmp").mkdir(parents=True)
        shutil.copy(
            primary_work["work"] / "suggestions-doc.json",
            instance / "tomo-tmp" / "suggestions-doc.json",
        )
        cache = tmp_path / "stale-cache"
        cache.mkdir()
        shutil.copy(
            fan_work / "suggestions-fan-approved.md", cache / "cached-fan.md"
        )
        keys = _keys_by_title(_parse(cache / "cached-fan.md", cwd=instance))
        assert set(keys) == {"Kaffee als Ritual", "Kai am Strand"}
        assert T5.DEEP_1 not in keys.values()
        assert T5.DEEP_2 not in keys.values()
        assert keys["Kai am Strand"] != "100 Inbox/Kaffee.md"


# ===========================================================================
# The companion path — `--fan-resolve-file`, the invocation a Force-Atomic run
# with an approved primary actually takes (synthesis-conductor.md:111).
# ===========================================================================

FAN_ANCHOR = {"kind": "heading", "heading": "Fotos", "new_section": False}
STALE_PRIMARY_ANCHOR = {"kind": "heading", "heading": "WRONG — primary doc"}


def _anchor_of(parsed: dict, title: str) -> dict | None:
    for c in parsed["confirmed_items"]:
        if c["title"] == title:
            cands = c.get("candidate_mocs") or []
            return cands[0].get("anchor") if cands else None
    raise AssertionError(f"no confirmed item titled {title!r}")


def _set_candidate_anchor(doc_path: Path, anchor: dict) -> None:
    """Stamp one anchor onto every candidate MOC of a structured doc.

    The reducer leaves `anchor: null` without Kado, and the renderer then emits
    no `**Placement:**` line — so the doc-JSON map is the SOLE source of the
    apply-time anchor here, which is what makes it assertable.
    """
    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    for section in doc["sections"]:
        for action in section.get("actions") or []:
            for cand in action.get("candidate_mocs") or []:
                cand["anchor"] = anchor
    doc_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                        encoding="utf-8")


@pytest.fixture(scope="module")
def companion(tmp_path_factory) -> dict:
    """A primary document with a Force-Atomic tick, plus its fan companion.

    Laid out the way production does it: the parser reads both documents from
    `tomo-tmp/inbox-cache/`, so NEITHER structured doc is a sibling and both
    resolutions go through the cwd-relative fallback.
    """
    root = tmp_path_factory.mktemp("t6_4a_companion")

    fan_work = root / "fan"
    fan_work.mkdir()
    _drive_fan(fan_work)

    primary_work = root / "primary"
    primary_work.mkdir()
    T5._drive(
        primary_work,
        {FAN_DEEP: T5._daily_only_result("Kai", FAN_DEEP)},
        accept_all=True,
    )
    primary_md = primary_work / "suggestions-approved.md"
    ticked = primary_md.read_text(encoding="utf-8").replace(
        "- [ ] Force Atomic Note", "- [x] Force Atomic Note"
    )
    assert "- [x] Force Atomic Note" in ticked, "the FAN checkbox was not rendered"
    primary_md.write_text(ticked, encoding="utf-8")

    # The paired anchor fixture: the fan doc and a COEXISTING stale primary doc
    # both answer for section id S02 and the same MOC, with different values.
    _set_candidate_anchor(fan_work / "suggestions-fan-doc.json", FAN_ANCHOR)
    stale_primary = json.loads(
        (fan_work / "suggestions-fan-doc.json").read_text(encoding="utf-8")
    )
    stale_path = root / "stale-primary.json"
    stale_path.write_text(json.dumps(stale_primary, ensure_ascii=False),
                          encoding="utf-8")
    _set_candidate_anchor(stale_path, STALE_PRIMARY_ANCHOR)

    instance = root / "instance"
    cache = instance / "tomo-tmp" / "inbox-cache"
    cache.mkdir(parents=True)
    shutil.copy(fan_work / "suggestions-fan-doc.json",
                instance / "tomo-tmp" / "suggestions-fan-doc.json")
    shutil.copy(stale_path, instance / "tomo-tmp" / "suggestions-doc.json")
    shutil.copy(primary_md, cache / "primary.md")
    shutil.copy(fan_work / "suggestions-fan-approved.md", cache / "fan.md")

    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "suggestion-parser.py"),
         "--file", str(cache / "primary.md"),
         "--fan-resolve-file", str(cache / "fan.md"),
         "--suggestions-doc", str(primary_work / "suggestions-doc.json")],
        capture_output=True, text=True, cwd=str(instance),
    )
    assert result.returncode == 0, f"parser failed:\n{result.stderr}"
    return {"parsed": json.loads(result.stdout), "root": root}


class TestCompanionResolveSectionsBindTheirOwnIdentity:
    """`_promote_entry` reads `sec["item_key"]`, and nothing ever set it."""

    def test_the_promoted_subfolder_note_carries_its_key(self, companion):
        promoted = [
            c for c in companion["parsed"]["confirmed_items"]
            if c["title"] == "Kai am Strand"
        ]
        assert len(promoted) == 1, "the FAN promotion did not reach confirmed_items"
        assert promoted[0].get("item_key") == FAN_DEEP

    def test_only_the_ticked_source_is_promoted(self, companion):
        """The fan document also holds a Kaffee section; no FAN tick asked for
        it, so a fix that promotes the whole document would show up here."""
        titles = {c["title"] for c in companion["parsed"]["confirmed_items"]}
        assert titles == {"Kai am Strand"}

    def test_the_move_origin_is_the_subfolder_path(self, companion):
        from lib.render_actions import build_actions  # noqa: PLC0415
        from lib.render_resolve import filter_missing_source_notes  # noqa: PLC0415

        parsed = companion["parsed"]
        client = T5._exact_path_client({FAN_ROOT, FAN_DEEP})
        kept, dropped = filter_missing_source_notes(
            parsed["confirmed_items"], client, T5.INBOX
        )
        assert dropped == [], f"a note that exists was still dropped: {dropped}"
        manifest = [
            {
                "id": c["id"], "action": "create_note", "title": c["title"],
                "source_path": c.get("source_path"), "item_key": c.get("item_key"),
                "audio_peer": None, "template": c.get("template"),
                "rendered_file": f"2026-09-08_1200_{c['id']}.md",
                "destination": c.get("destination") or "Atlas/202 Notes/",
                "parent_mocs": c.get("parent_mocs") or [], "attachments": [],
                "tags": c.get("tags") or [],
            }
            for c in kept
        ]
        actions, _ = build_actions(
            manifest, kept, parsed.get("daily_updates", []),
            parsed.get("skipped", []), T5.CFG, kado_client=None,
        )
        origins = {
            a.get("source_inbox_item")
            for a in actions if a.get("action") == "move_note"
        }
        assert origins == {FAN_DEEP}
        assert "100 Inbox/Kai.md" not in origins


class TestCompanionAnchorsComeFromTheFanDocument:
    """`load_doc_anchor_map` has no stem cross-check, so reading the wrong
    document binds a WRONG anchor rather than degrading to none."""

    def test_the_anchor_is_the_fan_documents_not_the_stale_primarys(
        self, companion
    ):
        anchor = _anchor_of(companion["parsed"], "Kai am Strand")
        assert anchor == FAN_ANCHOR
        assert anchor != STALE_PRIMARY_ANCHOR


class TestStandaloneAnchorsComeFromTheFanDocument:
    """The same pairing on the standalone path this task first fixed — an
    anchored fan doc alone would only prove empty-versus-populated."""

    @pytest.fixture(scope="class")
    def standalone_anchor(self, tmp_path_factory) -> dict:
        root = tmp_path_factory.mktemp("t6_4a_anchor")
        fan_work = root / "fan"
        fan_work.mkdir()
        _drive_fan(fan_work)
        _set_candidate_anchor(fan_work / "suggestions-fan-doc.json", FAN_ANCHOR)
        stale = root / "stale.json"
        stale.write_text(
            (fan_work / "suggestions-fan-doc.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        _set_candidate_anchor(stale, STALE_PRIMARY_ANCHOR)

        instance = root / "instance"
        cache = instance / "tomo-tmp" / "inbox-cache"
        cache.mkdir(parents=True)
        shutil.copy(fan_work / "suggestions-fan-doc.json",
                    instance / "tomo-tmp" / "suggestions-fan-doc.json")
        shutil.copy(stale, instance / "tomo-tmp" / "suggestions-doc.json")
        shutil.copy(fan_work / "suggestions-fan-approved.md", cache / "fan.md")
        return _parse(cache / "fan.md", cwd=instance)

    def test_the_anchor_is_the_fan_documents(self, standalone_anchor):
        anchor = _anchor_of(standalone_anchor, "Kai am Strand")
        assert anchor == FAN_ANCHOR
        assert anchor != STALE_PRIMARY_ANCHOR


# ===========================================================================
# An unrecognised doc_type must not fall back silently — a future render type
# whose table entry someone forgets would rejoin against the primary document,
# which is the defect this task exists to fix.
# ===========================================================================

def _parser_module():
    import importlib.util  # noqa: PLC0415

    spec = importlib.util.spec_from_file_location(
        "_t64a_parser_warn", SCRIPTS_DIR / "suggestion-parser.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _frontmatter(doc_type: str | None) -> str:
    tomo = f"tomo:\n  doc_type: {doc_type}\n" if doc_type is not None else ""
    return f"---\ntype: tomo-suggestions\n{tomo}---\n\n# Doc\n"


class TestAnUnknownDocTypeIsLoud:
    def test_it_still_resolves_to_the_primary_document(self, tmp_path, capsys):
        mod = _parser_module()
        path = mod._default_doc_path(
            str(tmp_path / "doc.md"), _frontmatter("suggestions-triage")
        )
        assert path.endswith("suggestions-doc.json")

    def test_it_names_the_type_and_the_document_it_fell_back_to(
        self, tmp_path, capsys
    ):
        mod = _parser_module()
        mod._default_doc_path(
            str(tmp_path / "doc.md"), _frontmatter("suggestions-triage")
        )
        err = capsys.readouterr().err
        assert "[warn]" in err
        assert "suggestions-triage" in err
        assert "suggestions-doc.json" in err

    @pytest.mark.parametrize("doc_type", [None, ""])
    def test_a_legacy_document_stays_silent(self, tmp_path, capsys, doc_type):
        """No doc_type is not a mistake — the primary doc is its right answer."""
        mod = _parser_module()
        mod._default_doc_path(str(tmp_path / "doc.md"), _frontmatter(doc_type))
        assert "[warn]" not in capsys.readouterr().err

    @pytest.mark.parametrize(
        "doc_type", ["suggestions", "suggestions-fan", "moc-proposal"]
    )
    def test_every_type_in_use_today_stays_silent(self, tmp_path, capsys, doc_type):
        mod = _parser_module()
        mod._default_doc_path(str(tmp_path / "doc.md"), _frontmatter(doc_type))
        assert "[warn]" not in capsys.readouterr().err
