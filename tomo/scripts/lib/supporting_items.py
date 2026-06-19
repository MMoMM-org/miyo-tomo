"""Shared supporting-items parsing/union — spec 022/023 review H5.

No IO. Single home for the supporting_items union that was previously
duplicated (with divergent signatures) in instruction-render.py and
suggestion-parser.py. Those two are hyphenated top-level scripts and
cannot import each other, so the shared logic lives here.

The union is list-aware: it returns a list when either input is a list
(moc-proposal flow) and a comma-joined string otherwise (suggestion flow),
matching the two emission shapes.
"""
# version: 1.0.0


def parse_supporting_items(raw):
    """Parse supporting_items into a list of stems.

    Accepts two formats:
      - list: ["Thought Collisions", "Map of Content"] (moc-proposal-parser)
      - str:  "S02, S06, S12" (suggestion-parser, SNN IDs only)
    """
    if not raw:
        return []
    if isinstance(raw, list):
        return [s.strip() for s in raw if isinstance(s, str) and s.strip()]
    s = raw.strip().strip("[](){}")
    out = []
    for tok in s.split(","):
        tok = tok.strip().strip("[]()").lstrip("#")
        if tok:
            out.append(tok)
    return out


def union_supporting_items(a, b):
    """Union two supporting_items values (string of SNN IDs or list of stems),
    preserving first-seen order and de-duplicating (#67 defense-in-depth).

    Returns a list when either input is a list, else a comma-joined string —
    matching the shape both flows emit (suggestion = string, moc-proposal = list).
    """
    items = []
    for raw in (a, b):
        for tok in parse_supporting_items(raw):
            if tok not in items:
                items.append(tok)
    if isinstance(a, list) or isinstance(b, list):
        return items
    return ", ".join(items)
