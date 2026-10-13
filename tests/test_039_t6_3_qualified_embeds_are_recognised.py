#!/usr/bin/env python3
"""test_039_t6_3_qualified_embeds_are_recognised.py — spec 039 T6.3 (F4-AC7).

A note this run filed with a qualified embed (`![[<folder>/<name>]]`) must
still be recognised as an attachment embed when a later run reads that note:
triage's extractor is `attachment_index.extract_attachment_embeds`. Existing
extractor tests (`test_attachment_index.py`) feed it hand-written bodies; none
feeds it what Pass 2 actually wrote. These do.

Mechanism each test falsifies:
- `test_a_note_rendered_by_pass_2_with_a_qualified_embed_is_recognised`: the
  rewrite emitting a bare (or otherwise non-qualified) embed, or the
  extractor's pattern rejecting a `/` in the target — the qualified path would
  not come back out of the extractor.
- `test_alias_and_fragment_suffixes_survive_the_round_trip`: the rewrite
  dropping `|alias` / `#fragment` (F4-AC5) or the extractor failing to strip
  them from a qualified target.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

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

INBOX = "100 Inbox/"
ASSET = "Atlas/290 Assets/295 Attachments/"
SOURCE = "100 Inbox/Scans/karte.png"
QUALIFIED = f"{ASSET}karte.png"


def test_a_note_rendered_by_pass_2_with_a_qualified_embed_is_recognised(
    monkeypatch, tmp_path
):
    """Real `instruction-render.py main()` and real plan and embed rewrite
    (the pre-rewrite note body is a stub from `render_via_script`): another
    `karte.png` stays in the vault, so the plan qualifies the embed. The
    rendered note body, fed to the extractor, yields the qualified path."""
    client = H.CountingKado(
        [SOURCE, "Archive/karte.png"], existing_folders=[H.ASSET, H.NOTES]
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
    """F4-AC5 + F4-AC7: the qualified embed keeps `|alias` and `#fragment`, and
    the extractor still returns the bare qualified path for each."""
    vault = FakeVault([SOURCE, "Archive/karte.png"], existing_folders=[ASSET])
    plan = plan_from_remedies(
        [{"attachments": [SOURCE]}], [],
        inbox_path=INBOX, asset_folder=ASSET, vault=vault,
    )
    assert plan.by_source[SOURCE].qualified_reason == "ambiguous"
    body = "![[karte.png|300]]\n![[Scans/karte.png|Karte]]\n![[karte.png#p2]]\n"
    written = rewrite_attachment_embeds(body, [SOURCE], plan)
    assert written == (
        f"![[{QUALIFIED}|300]]\n![[{QUALIFIED}|Karte]]\n![[{QUALIFIED}#p2]]\n"
    ), written
    assert extract_attachment_embeds(written) == [QUALIFIED], written
