"""Every Agent() dispatch template in the runtime tree names a subagent_type.

`name` labels the agent that gets spawned; `subagent_type` chooses which
definition it runs. A template carrying only `name` dispatches
general-purpose under an alias — the tool reports success, the transcript
shows an agent called "inbox-analyst", and none of that agent's contract,
tools or skills are in play.

The live run on 2026-09-14 did exactly this for all twelve fan-out items.
It produced a correct suggestions doc, so nothing surfaced as an error; what
it produced along the way was twelve agents reconstructing the pipeline from
the filesystem, three of them brute-forcing a result filename with md5sum
through cksum, and one shared state-file rewritten wholesale mid-fan-out.

These templates are markdown read by an LLM, so no import or type checker
can see them. This test is the only thing that does.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RUNTIME_ROOT = Path(__file__).resolve().parent.parent / "tomo" / "dot_claude"

# An `Agent(` opener followed by everything up to the closing `)` on its own
# line. Templates are fenced blocks written for a reader, not valid syntax, so
# this is deliberately shape-based rather than a parse.
DISPATCH_BLOCK = re.compile(r"^Agent\(\s*\n(.*?)^\)", re.MULTILINE | re.DOTALL)


def _runtime_files() -> list[Path]:
    return sorted(
        p
        for p in RUNTIME_ROOT.rglob("*.md")
        if DISPATCH_BLOCK.search(p.read_text(encoding="utf-8"))
    )


def _dispatch_blocks() -> list[tuple[Path, str]]:
    blocks = []
    for path in _runtime_files():
        for match in DISPATCH_BLOCK.finditer(path.read_text(encoding="utf-8")):
            blocks.append((path, match.group(1)))
    return blocks


def test_the_runtime_tree_still_contains_dispatch_templates():
    """Guards the guard: a regex that matches nothing passes every test below."""
    blocks = _dispatch_blocks()
    assert blocks, (
        "no Agent( ... ) blocks found under tomo/dot_claude — either the "
        "dispatch templates moved or DISPATCH_BLOCK stopped matching them, "
        "and every assertion in this file has gone vacuous"
    )
    assert len(blocks) >= 4, f"expected at least 4 templates, found {len(blocks)}"


@pytest.mark.parametrize(
    "path,block",
    _dispatch_blocks(),
    ids=lambda v: v.name if isinstance(v, Path) else "",
)
def test_every_dispatch_template_names_a_subagent_type(path: Path, block: str):
    rel = path.relative_to(RUNTIME_ROOT.parent.parent)
    assert "subagent_type:" in block, (
        f"{rel} has an Agent() template without subagent_type — it would "
        f"dispatch general-purpose:\n{block.strip()[:300]}"
    )


@pytest.mark.parametrize(
    "path,block",
    _dispatch_blocks(),
    ids=lambda v: v.name if isinstance(v, Path) else "",
)
def test_no_template_uses_name_as_the_selector(path: Path, block: str):
    """`name` alongside `subagent_type` is legal; `name` as the only key is the bug.

    Asserted separately from the presence check so a template that grows a
    `name` back without a `subagent_type` fails on both, naming the cause
    twice rather than leaving the reader to infer it.
    """
    rel = path.relative_to(RUNTIME_ROOT.parent.parent)
    if re.search(r"^\s*name:", block, re.MULTILINE):
        assert "subagent_type:" in block, (
            f"{rel} selects a dispatch target with `name:` alone. `name` is a "
            f"label; only `subagent_type` chooses the agent definition."
        )


def test_every_named_subagent_type_has_an_agent_definition():
    """A typo in subagent_type fails the same way a missing one does — silently."""
    available = {p.stem for p in (RUNTIME_ROOT / "agents").glob("*.md")}
    assert available, "no agent definitions found — the path assumption broke"

    for path, block in _dispatch_blocks():
        for name in re.findall(r'subagent_type:\s*"([^"]+)"', block):
            assert name in available, (
                f"{path.name} dispatches subagent_type {name!r}, which has no "
                f"definition in tomo/dot_claude/agents/. Known: "
                f"{sorted(available)}"
            )
