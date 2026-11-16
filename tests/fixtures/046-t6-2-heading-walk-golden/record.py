#!/usr/bin/env python3
# version: 0.1.0
"""Record tests/fixtures/046-t6-2-heading-walk-golden/walk.json from the heading walks of the source tree passed
as --tree.

Spec 046 T6.2: `review_mapping._tree` (the template analysis) and `review_section_plan._Note.read` (the note
planner) each walked the heading tree. Before they share one walk, this records what both produced on the T1.2
template fixtures (`tests/test_review_mapping.TEMPLATES`) and on the note texts below (`NOTES`): per text the
template headings (key, line, ancestors, body kind), the level-1 lines and the planner's keyed headings (key, line,
ancestors). The golden was recorded from the commit before the change: export it with
`git archive <sha> | tar -x -C <dir>` and pass that dir; the fixtures come from the same tree.

Legitimate reasons to re-record: a template fixture was edited for an unrelated reason, or a walk's result changed
ON PURPOSE and the change was reviewed. Do NOT re-record to make tests/test_046_t6_2_heading_walk.py pass — a
disagreement is the drift that test exists to catch.

Usage: python3 record.py --tree <exported source tree>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# notes the planner reads: level-1 headings, repeats under one and under several parents, closing hashes,
# a fenced heading, a skipped level, CRLF, a Templater span and frontmatter (synthetic)
NOTES = {
    "repeats": "# 2026-W13\n## A\n### X\n### X\n## B\n### X\n# Second\n## A\ntext\n",
    "closing-hashes": "## Notes ##\nn\n### Sub ###\n#### Deep\n## Notes\n",
    "fenced": "## A\n```\n## not a heading\n```\n### B\n~~~\n# no\n~~~\n## C\n",
    "skipped-level": "#### Deep first\n## Two\n###### Six\n### Three\n",
    "crlf": "## A\r\n### B\r\n## C\n",
    "templater": "---\ntags: x\n---\n# <% tp.file.title %>\n<%*\n## inside\n%>\n## Real\n### <% x %>\n",
    "empty": "",
}


def walk(text: str, rm, rsp) -> dict:
    heads = rm.heading_tree(text)
    return {
        "template": [[list(h.key), h.line, [list(a) for a in h.ancestors], h.body_kind] for h in heads],
        "top": rm.outline(text)["top"],
        "note": [[list(h.key), h.line, [list(a) for a in h.ancestors]] for h in rsp._Note.read(text).keyed],
    }


def record(tree: Path) -> dict:
    sys.path.insert(0, str(tree / "tomo" / "scripts"))
    sys.path.insert(0, str(tree / "tests"))
    from lib import review_mapping as rm
    from lib import review_section_plan as rsp
    from test_review_mapping import TEMPLATES
    texts = {**{f"template:{k}": v for k, v in TEMPLATES.items()}, **{f"note:{k}": v for k, v in NOTES.items()}}
    return {name: walk(text, rm, rsp) for name, text in sorted(texts.items())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--tree", required=True, type=Path, help="exported source tree to record from")
    args = parser.parse_args()
    data = record(args.tree.resolve())
    (HERE / "walk.json").write_text(json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                                    encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
