#!/usr/bin/env python3
"""test_039_t6_3_qualified_embeds_are_recognised.py — spec 039 T6.3 (F4-AC7).

A note this run filed with a qualified embed (`![[<folder>/<name>]]`) must
still be recognised as an attachment embed when a later run reads that note.
Triage's reader is `inbox-triage.py::resolve_inbox_attachments`: Kado's
`listNotes(fields=["links"])` supplies the embed targets, and the function
strips alias/anchor, filters to file targets and resolves them against the
inbox index (`narrow_candidates`). The two `test_triage_*` tests below are the
F4-AC7 trace: they hand that function, through a fake client's `list_notes`,
the embeds of a body Pass 2's `main()` and the plan-reading rewrite actually
wrote.

The two older tests feed the same bodies to
`attachment_index.extract_attachment_embeds`. Production triage does not call
that extractor (the metadataCache replaced it); they stay because they cover
the extractor, not because they trace F4-AC7.

Mechanism each test falsifies:
- `test_triage_resolves_the_qualified_embed_past_a_namesake`: triage dropping
  a path-qualified target before resolution, or `narrow_candidates` failing to
  narrow a qualified target by path suffix (the namesake would make it
  ambiguous). Proven RED by adding `if "/" in target: continue` after the
  `_strip_alias_and_anchor` line in `resolve_inbox_attachments`: both triage
  tests fail, the note is absent from the result.
- `test_triage_reports_an_unindexed_qualified_embed_as_unresolved`: the same
  mutation — the note silently reads as attachment-free instead of carrying
  an unresolved embed naming the qualified target.
- `test_a_note_rendered_by_pass_2_with_a_qualified_embed_is_recognised`: the
  rewrite emitting a non-qualified embed, or the extractor's pattern rejecting
  a `/` in the target.
- `test_alias_and_fragment_suffixes_survive_the_round_trip`: the rewrite
  dropping `|alias` / `#fragment` (F4-AC5) or the extractor failing to strip
  them from a qualified target.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from attachment_plan_fakes import FakeVault, plan_from_remedies  # noqa: E402
from lib.attachment_index import extract_attachment_embeds  # noqa: E402
from lib.embed_rewrite import rewrite_attachment_embeds  # noqa: E402

import pass2_harness as H  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "inbox_triage_t6_3_f4_ac7", SCRIPTS_DIR / "inbox-triage.py"
)
triage = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = triage
_spec.loader.exec_module(triage)

INBOX = "100 Inbox/"
ASSET = "Atlas/290 Assets/295 Attachments/"
SOURCE = "100 Inbox/Scans/karte.png"
QUALIFIED = f"{ASSET}karte.png"
NAMESAKE = "Archive/karte.png"
LATER_NOTE = f"{INBOX}2026-10-12_0900_eins.md"
VARIANTS_BEFORE_REWRITE = (
    "![[karte.png|300]]\n![[Scans/karte.png|Karte]]\n![[karte.png#p2]]\n"
)

# Test-side stand-in for Kado's metadataCache: one `kind: embed` link per
# `![[...]]`, carrying the bracket's inner text as `target`.
_EMBED = re.compile(r"!\[\[([^\[\]]+)\]\]")


def _variant_plan():
    vault = FakeVault([SOURCE, NAMESAKE], existing_folders=[ASSET])
    return plan_from_remedies(
        [{"attachments": [SOURCE]}], [],
        inbox_path=INBOX, asset_folder=ASSET, vault=vault,
    )


def _body_pass_2_wrote(monkeypatch, tmp_path) -> str:
    """Real `instruction-render.py main()` (another `karte.png` stays in the
    vault, so the plan qualifies the embed), plus the `|300`, `|Karte` and
    `#p2` variants through the same plan-reading rewrite."""
    client = H.CountingKado(
        [SOURCE, NAMESAKE], existing_folders=[H.ASSET, H.NOTES]
    )
    rc, out_dir = H._run_main(
        monkeypatch, tmp_path,
        H._suggestions([H._item("S01", "Eins", attachments=[SOURCE])]),
        client,
    )
    assert rc == 0
    body = (out_dir / "2026-10-12_0900_eins.md").read_text(encoding="utf-8")
    assert f"![[{QUALIFIED}]]" in body, body
    variants = rewrite_attachment_embeds(
        VARIANTS_BEFORE_REWRITE, [SOURCE], _variant_plan()
    )
    return body + "\n" + variants


class _LaterRunKado:
    """Only what `resolve_inbox_attachments` calls: one `list_notes`."""

    def __init__(self, notes: list[dict]):
        self.notes = notes
        self.calls: list[tuple[str, dict]] = []

    def list_notes(self, path, *, fields=None, depth=None, limit=500):
        self.calls.append(("list_notes", {"path": path, "fields": fields}))
        return self.notes


def _later_run(body: str, indexed_paths: list[str]) -> dict:
    links = [{"kind": "embed", "target": t} for t in _EMBED.findall(body)]
    assert {link["target"] for link in links} == {
        QUALIFIED, f"{QUALIFIED}|300", f"{QUALIFIED}|Karte", f"{QUALIFIED}#p2",
    }, links
    client = _LaterRunKado([{"path": LATER_NOTE, "links": links}])
    index = triage.build_attachment_index(
        [{"path": p, "type": "file"} for p in indexed_paths]
    )
    result = triage.resolve_inbox_attachments(client, INBOX, index)
    assert client.calls == [("list_notes", {"path": INBOX, "fields": ["links"]})]
    return result


def test_triage_resolves_the_qualified_embed_past_a_namesake(
    monkeypatch, tmp_path
):
    """Index holds the qualified path and a namesake: the qualified target
    narrows to exactly one candidate, so the note's attachment is that path
    (once, for all four embeds) and nothing is reported unresolved."""
    body = _body_pass_2_wrote(monkeypatch, tmp_path)
    result = _later_run(body, [QUALIFIED, NAMESAKE])
    assert result == {
        LATER_NOTE: {"attachments": [QUALIFIED], "unresolved_embeds": []},
    }, result


def test_triage_reports_an_unindexed_qualified_embed_as_unresolved(
    monkeypatch, tmp_path
):
    """Index lacks the path: the note is still present, carrying one
    unresolved embed naming the qualified target — never attachment-free."""
    body = _body_pass_2_wrote(monkeypatch, tmp_path)
    result = _later_run(body, [NAMESAKE])
    assert result == {
        LATER_NOTE: {
            "attachments": [],
            "unresolved_embeds": [
                {"embed_target": QUALIFIED, "status": "unresolved"},
            ],
        },
    }, result


def test_a_note_rendered_by_pass_2_with_a_qualified_embed_is_recognised(
    monkeypatch, tmp_path
):
    """Real `instruction-render.py main()` and real plan and embed rewrite
    (the pre-rewrite note body is a stub from `render_via_script`): another
    `karte.png` stays in the vault, so the plan qualifies the embed. The
    rendered note body, fed to the extractor, yields the qualified path."""
    client = H.CountingKado(
        [SOURCE, NAMESAKE], existing_folders=[H.ASSET, H.NOTES]
    )
    rc, out_dir = H._run_main(
        monkeypatch, tmp_path,
        H._suggestions([H._item("S01", "Eins", attachments=[SOURCE])]),
        client,
    )
    assert rc == 0
    body = (out_dir / "2026-10-12_0900_eins.md").read_text(encoding="utf-8")
    assert f"![[{QUALIFIED}]]" in body, body
    assert extract_attachment_embeds(body) == [QUALIFIED], body


def test_alias_and_fragment_suffixes_survive_the_round_trip():
    """F4-AC5: the qualified embed keeps `|alias` and `#fragment`, and the
    extractor still returns the bare qualified path for each."""
    plan = _variant_plan()
    assert plan.by_source[SOURCE].qualified_reason == "ambiguous"
    written = rewrite_attachment_embeds(VARIANTS_BEFORE_REWRITE, [SOURCE], plan)
    assert written == (
        f"![[{QUALIFIED}|300]]\n![[{QUALIFIED}|Karte]]\n![[{QUALIFIED}#p2]]\n"
    ), written
    assert extract_attachment_embeds(written) == [QUALIFIED], written
