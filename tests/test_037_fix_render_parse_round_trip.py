#!/usr/bin/env python3
# version: 0.1.0
"""test_037_fix_render_parse_round_trip.py — fix/037 round trip.

`suggestions-reducer.py`'s `render_attachment_conflicts_block` and
`suggestion-parser.py`'s `parse_attachment_conflict_remedies` agree on one
document state — "no free name was available, so rename is impossible" —
that used to be communicated through a bare English string duplicated in
both files (`"no free name available"`). `lib/attachment_conflict_states.py`
now holds that marker as a single shared constant, so a reword of the
rendered line can no longer drift out of step with the parser's detection
of it (that specific mutation is now hard to write — the reducer and the
parser both read the same Python name).

The constant only pins the WORDING. It says nothing about the SEMANTIC
mapping from a rendered document state to a remedy — the actual business
rule (owner decision 2026-09-23, ADR-4 exception) that a ticked-but-
impossible rename must resolve to `ignore`, never fall through to `rename`
with a null destination (Rule 6). That mapping lives in
`_resolve_attachment_remedy`, entirely independent of the marker constant,
and a change there would pass with the constant fully intact. This test
exists to pin THAT mapping, by running real renderer output through the
real parser — nothing hand-typed — so both the wording-drift class of bug
(now constant-guarded) and the semantic-mapping class of bug (not
constant-guarded) are covered by something.

`test_037_t2_4_parse_remedy.py` already pins `_resolve_attachment_remedy`
exhaustively over hand-written fixture text (its own header says so). This
file does not duplicate that exhaustive coverage — it adds the one thing
that file explicitly does not do: prove the mapping holds when the input
text is the renderer's actual output, not a hand-copied reproduction of it.

Mutation: delete the ADR-4 exception in `_resolve_attachment_remedy` —
change `return REMEDY_IGNORE if rename_impossible else REMEDY_RENAME` to
unconditionally `return REMEDY_RENAME` — so a ticked-but-impossible rename
resolves as `rename` instead of `ignore`. Verified red by applying this
exact edit to a disposable copy of `suggestion-parser.py` (never the
tracked file) and re-running this file; reverted before commit. The shared
constant does not catch this mutation — both files still agree on the
wording, and the wording never changes. Only the round trip does.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


REDUCER = _load_module("suggestions_reducer_t037_fix_rt", "suggestions-reducer.py")
PARSER = _load_module("suggestion_parser_t037_fix_rt", "suggestion-parser.py")

SOURCE = "100 Inbox/Scans/karte.png"
ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"


def _conflict(**overrides) -> dict:
    base = {
        "source": SOURCE,
        "destination": f"{ASSET_FOLDER}karte.png",
        "same_file": None,
        "owner_source_items": ["100 Inbox/Scans/karte.md"],
        "proposed_name": "karte (2).png",
    }
    base.update(overrides)
    return base


def _tick(line: str) -> str:
    assert line.strip().startswith("- [ ] "), line
    return line.replace("- [ ] ", "- [x] ", 1)


def _untick(line: str) -> str:
    assert line.strip().startswith("- [x] "), line
    return line.replace("- [x] ", "- [ ] ", 1)


def _toggle(md: str, *, tick_contains: str, untick_contains: str) -> str:
    """Flip exactly one checkbox marker on and one off, leaving every other
    character — including the renderer's own wording — untouched. Models an
    owner editing the actual rendered document, not a hand-typed fixture."""
    out = []
    for line in md.splitlines():
        if tick_contains in line:
            line = _tick(line)
        elif untick_contains in line:
            line = _untick(line)
        out.append(line)
    return "\n".join(out) + "\n"


def test_render_parse_round_trip_pins_semantic_mapping():
    # Case 1: proposed_name is None (ADR-4 exception path). The renderer
    # pre-ticks "Keep in inbox" and ships "Rename — <marker>" unticked; here
    # the owner instead ticks the impossible rename and clears keep-in-inbox
    # — the exact state Rule 6 must never resolve to a bare rename.
    null_conflict = _conflict(proposed_name=None)
    rendered_null = REDUCER.render_attachment_conflicts_block(
        [null_conflict], ASSET_FOLDER
    )
    assert "no free name available" in rendered_null
    owner_edited = _toggle(
        rendered_null,
        tick_contains="Rename —",
        untick_contains="Keep in inbox",
    )
    resolved = PARSER.parse_attachment_conflict_remedies(owner_edited)
    assert len(resolved) == 1, resolved
    assert resolved[0]["source"] == SOURCE
    assert resolved[0]["remedy"] == "ignore", resolved[0]

    # Case 2: an ordinary entry — a free name IS available, rename ships
    # ticked, the owner leaves it alone. Proves the round trip resolves the
    # common path too, not only the exception.
    free_conflict = _conflict(proposed_name="karte (2).png")
    rendered_free = REDUCER.render_attachment_conflicts_block(
        [free_conflict], ASSET_FOLDER
    )
    resolved_free = PARSER.parse_attachment_conflict_remedies(rendered_free)
    assert len(resolved_free) == 1, resolved_free
    assert resolved_free[0]["source"] == SOURCE
    assert resolved_free[0]["remedy"] == "rename", resolved_free[0]
