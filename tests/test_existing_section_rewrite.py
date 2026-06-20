"""#73: _rewrite_existing_section_anchors — when a link_to_moc's top-level
new_section already exists as a heading in the target MOC, rewrite to a heading
anchor (placement=after) and drop new_section, so apply lands the bullet(s)
under the existing section instead of emitting a duplicate `## <name>` heading.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "instruction-render.py"

sys.path.insert(0, str(SCRIPTS_DIR))

spec = importlib.util.spec_from_file_location("instruction_render", SCRIPT_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

_rewrite_existing_section_anchors = mod._rewrite_existing_section_anchors
_serialize_new_sections = mod._serialize_new_sections


# ── Helpers ──────────────────────────────────────────────────────────────────

def _link_action(new_section: str, target_path: str) -> dict:
    return {
        "id": "I01",
        "action": "link_to_moc",
        "target_moc": "Japan (MOC)",
        "target_moc_path": target_path,
        "anchor": {"type": "callout", "value": None},
        "placement": "after",
        "new_section": new_section,
        "line_to_add": "- [[Asakusa]]",
    }


class _MocClient:
    """Returns a fixed MOC body for any read_note call."""

    def __init__(self, body: str):
        self._body = body
        self.reads = 0

    def read_note(self, path: str) -> dict:
        self.reads += 1
        return {"content": self._body}


_MOC_WITH_SECTION = (
    "# Japan (MOC)\n\n## Japanische Städte\n\n- [[Tokyo]]\n\n## Content\n\n- x\n"
)


# ── Tests ────────────────────────────────────────────────────────────────────

def test_existing_heading_rewrites_to_heading_anchor():
    actions = [_link_action("Japanische Städte", "100 Inbox/Japan (MOC).md")]
    client = _MocClient(_MOC_WITH_SECTION)

    rewritten = _rewrite_existing_section_anchors(actions, client)

    assert rewritten == 1
    a = actions[0]
    assert a["anchor"] == {"type": "heading", "value": "Japanische Städte"}
    assert a["placement"] == "after"
    assert a["new_section"] is None


def test_absent_heading_leaves_new_section_intact():
    actions = [_link_action("Brand New Section", "100 Inbox/Japan (MOC).md")]
    client = _MocClient(_MOC_WITH_SECTION)

    rewritten = _rewrite_existing_section_anchors(actions, client)

    assert rewritten == 0
    assert actions[0]["new_section"] == "Brand New Section"
    assert actions[0]["anchor"]["type"] == "callout"


def test_case_insensitive_match_uses_actual_moc_text():
    actions = [_link_action("japanische städte", "100 Inbox/Japan (MOC).md")]
    client = _MocClient(_MOC_WITH_SECTION)

    _rewrite_existing_section_anchors(actions, client)

    assert actions[0]["anchor"]["value"] == "Japanische Städte"


def test_offline_client_is_noop():
    actions = [_link_action("Japanische Städte", "100 Inbox/Japan (MOC).md")]

    rewritten = _rewrite_existing_section_anchors(actions, None)

    assert rewritten == 0
    assert actions[0]["new_section"] == "Japanische Städte"


def test_rewrite_then_serialize_emits_no_duplicate_heading():
    """End-to-end: after rewrite, _serialize_new_sections must NOT prepend a
    second `## Japanische Städte` — the bullet stays bare and lands under the
    existing heading via the heading anchor."""
    actions = [_link_action("Japanische Städte", "100 Inbox/Japan (MOC).md")]
    client = _MocClient(_MOC_WITH_SECTION)

    _rewrite_existing_section_anchors(actions, client)
    serialized = _serialize_new_sections(actions)

    assert serialized == 0
    assert not actions[0]["line_to_add"].startswith("## ")
    assert actions[0]["line_to_add"] == "- [[Asakusa]]"


def test_reads_each_moc_once():
    actions = [
        _link_action("Japanische Städte", "100 Inbox/Japan (MOC).md"),
        _link_action("Japanische Städte", "100 Inbox/Japan (MOC).md"),
    ]
    actions[1]["id"] = "I02"
    actions[1]["line_to_add"] = "- [[Kyoto]]"
    client = _MocClient(_MOC_WITH_SECTION)

    rewritten = _rewrite_existing_section_anchors(actions, client)

    assert rewritten == 2
    assert client.reads == 1  # cached per target_moc_path
