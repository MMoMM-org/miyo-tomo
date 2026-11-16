#!/usr/bin/env python3
# version: 0.1.0
"""Record tests/fixtures/046-t4-3-unmapped-parse-golden/parse.json from the
`review_doc_parse.parse_document` of the source tree passed as --tree.

WHY: without a mapping (no `pass1_sections` in meta.json) the edited review
document must parse exactly as spec 045 parsed it (spec 046 CON-2, T4.3). The
golden was recorded from the branch head before T4.3 taught the parser the
section parts: export it with `git archive <rev> | tar -x -C <dir>` and pass
that dir. The documents are the T4.2 unmapped goldens
(tests/fixtures/046-t4-2-unmapped-doc-golden/{week,month}.md, the renderer's
own output) with the edits in EDITS applied — every spec 045 warning
(`unknown-group`, `duplicate-group`, `item-outside-group`), user items, a
deleted id, a copied id, a done marker, and lines that look like 046's
section grammar (`%%s1%%`, `%%review%%`), which an unmapped parse must not
read as sections.

Legitimate reasons to re-record: EDITS changed for an unrelated reason, or
the unmapped parse changed ON PURPOSE and the change was reviewed. Do NOT
re-record from a branch to make tests/test_046_t4_3_unmapped_parse_golden.py
pass — a disagreement is the regression that test exists to catch.

Usage: python3 record.py --tree <exported source tree>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
DOC_DIR = OUT_DIR.parent / "046-t4-2-unmapped-doc-golden"
DOCS = ("week", "month")


def _replace(old: str, new: str, count: int = 1):
    def edit(text: str) -> str:
        assert old in text, old
        return text.replace(old, new, count)
    return edit


def _after_approved(lines: str):
    return _replace("- [ ] Approved\n", "- [x] Approved\n" + lines)


def _first_heading(text: str) -> str:
    return next(ln for ln in text.splitlines() if ln.startswith("## "))


def _rename_first_heading(text: str) -> str:
    head = _first_heading(text)
    return text.replace(head + "\n", "## Mein eigener Titel\n", 1)


def _duplicate_first_heading(text: str) -> str:
    head = _first_heading(text)
    return text.rstrip("\n") + f"\n\n{head}\n- [x] noch einer\n"


def _untick_first_item(text: str) -> str:
    line = next(ln for ln in text.splitlines() if ln.endswith("%%t1%%"))
    return text.replace(line, "- [ ] " + line[len("- [x] "):], 1)


def _drop_first_id(text: str) -> str:
    return text.replace(" %%t1%%", "", 1)


def _copy_id_line(text: str) -> str:
    line = next(ln for ln in text.splitlines() if ln.endswith("%%t1%%"))
    return text.rstrip("\n") + f"\n{line}\n"


def _done_mark(text: str) -> str:
    return text.replace(" %%t1%%", " %%t1%% ✅ 2026-04-03", 1).replace("- [ ] Approved", "- [x] Approved ✅ 2026-04-03")


def _section_lookalikes(text: str) -> str:
    head = _first_heading(text)
    return text.replace(head + "\n", f"{head}\n- [x] Use this section %%s1%%\n", 1).rstrip("\n") + (
        "\n\n## Goals %%s1%%\n- [ ] Use this section %%s1%%\n*Lands: before \"Goals\" (level 3)*\n"
        "- [x] mine %%s1%%\n\n## Tomo Review %%review%%\n- [x] under the divider\n")


EDITS = {
    "as-rendered": lambda text: text,
    "approved": _replace("- [ ] Approved", "- [x] Approved"),
    "unticked-item": lambda text: _untick_first_item(_replace("- [ ] Approved", "- [x] Approved")(text)),
    "renamed-heading": _rename_first_heading,
    "duplicate-heading": _duplicate_first_heading,
    "item-above-first-heading": _after_approved("- [x] oben ohne Gruppe\n"),
    "approved-missing": _replace("- [ ] Approved\n", ""),
    "id-dropped": _drop_first_id,
    "id-copied": _copy_id_line,
    "done-mark": _done_mark,
    "section-lookalikes": _section_lookalikes,
}


def cases() -> list:
    return [(doc, edit) for doc in DOCS for edit in EDITS]


def inputs(doc: str, edit: str) -> tuple:
    """``(edited text, pass1_links, pass1_total)`` of one case."""
    text = (DOC_DIR / f"{doc}.md").read_text(encoding="utf-8")
    meta = json.loads((DOC_DIR / f"{doc}.json").read_text(encoding="utf-8"))
    return EDITS[edit](text), meta["pass1_links"], sum(meta["pass1_counts"].values())


def capture(tree: Path, doc: str, edit: str) -> dict:
    """Everything spec 045's ParsedDoc exposes for one case, parsed by ``tree``'s parser without a mapping."""
    if str(tree / "tomo/scripts") not in sys.path:
        sys.path.insert(0, str(tree / "tomo/scripts"))
    from lib import review_doc_parse as rdp

    text, links, total = inputs(doc, edit)
    parsed = rdp.parse_document(text, pass1_links=links, pass1_total=total)
    items = [{"group": it.group, "id": it.id, "origin": it.origin, "kept": it.kept, "text": it.text,
              "lines": list(it.lines), "edited": it.edited} for it in parsed.items]
    return json.loads(json.dumps({
        "approved": parsed.approved, "warnings": parsed.warnings, "deleted": parsed.deleted,
        "group_order": parsed.group_order, "items": items, "counts": parsed.counts(),
        "nothing_to_deliver": parsed.nothing_to_deliver(), "public_items": parsed.public_items(),
        "approved_review": parsed.approved_review(), "frontmatter": parsed.frontmatter,
    }, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", required=True, type=Path, help="exported source tree (the pre-T4.3 head)")
    args = parser.parse_args()
    got = {f"{doc}/{edit}": capture(args.tree.resolve(), doc, edit) for doc, edit in cases()}
    (OUT_DIR / "parse.json").write_text(json.dumps(got, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                                        encoding="utf-8")


if __name__ == "__main__":
    main()
