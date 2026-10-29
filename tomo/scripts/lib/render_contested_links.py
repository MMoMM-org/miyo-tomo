# version: 0.1.0
"""render_contested_links.py — qualify MOC bullets for a filename two notes claim.

Split out of render_actions.py (#216, Constitution L2 file size). Finds the
note names this run files at more than one destination (taken before the
guards run) and rewrites each surviving link_to_moc bullet to name its note
by path (spec 034 T5.5), so a bullet written into a MOC keeps resolving after
the run.
"""
from __future__ import annotations

import re

from lib.obsidian_filename import sanitize_stem
from lib.source_link import colliding_names, qualified_target


_BULLET_LINK_RE = re.compile(r"^(\s*-\s*)\[\[([^\]]+)\]\](.*)$")


def contested_note_names(actions: list[dict]) -> set[str]:
    """The note filenames this run claims for more than one destination.

    Taken over the action list **as built** — before `validate_destinations`
    or `suppress_moves_for_unfiled_attachments` withhold anything. That timing
    is the whole point: the withheld twin is exactly the note that comes back.
    The user renames one claimant, re-runs Pass 2, and the other files as
    `Dresden.md`; a bullet this run wrote into a MOC then stops resolving, in a
    note nobody revisits. A set taken from the survivors would see one Dresden
    and render the bare link that the guard's own outcome invalidates.

    Keyed on the sanitised filename, because that is what the vault resolves
    by. Distinct **destinations**, not claimant count: two items claiming one
    path are both withheld and leave no bullet behind, so they are not what
    makes a name ambiguous — two items landing at two paths are.
    """
    return colliding_names(
        (sanitize_stem(a["title"]), a["destination"])
        for a in actions
        if a.get("action") in ("move_note", "create_moc")
        and a.get("title") and a.get("destination")
    )


def qualify_contested_moc_links(actions: list[dict], contested: set[str]) -> int:
    """Make every MOC bullet for a contested filename name its note by path.

    A `link_to_moc` bullet is written into a MOC and stays there, so unlike a
    line in the instruction document it has to survive the run that wrote it
    (spec 034 T5.5). `[[Dresden]]` resolves by name; once a second `Dresden`
    exists anywhere in the vault it resolves to whichever the vault picks.

    Runs **after** both withholding passes, over their output, because the
    path it writes must be one that will exist: the destination of the move
    that survived, never a withheld claimant's. `contested` is the claim set
    from before those passes (`contested_note_names`) — the two halves need
    opposite timings, which is why this is a pass and not an emit-time choice.

    Must run BEFORE `_merge_new_section_links` and `_serialize_new_sections`,
    while `line_to_add` is still one bare bullet. The display text is taken
    from the bullet itself rather than from `source_note_title`, so a title
    that was sanitised keeps the original as its alias.

    A contested name with no surviving move is left alone: there is no path to
    name it by, and the bullet is withdrawn by the withholding pass anyway.

    Returns the count of bullets rewritten.
    """
    if not contested:
        return 0
    survivors: dict[str, str] = {}
    for action in actions:
        if action.get("action") not in ("move_note", "create_moc"):
            continue
        title, destination = action.get("title"), action.get("destination")
        if title and destination:
            survivors.setdefault(sanitize_stem(title), destination)

    rewritten = 0
    for action in actions:
        if action.get("action") != "link_to_moc":
            continue
        name = action.get("source_note_stem") or ""
        destination = survivors.get(name) if name in contested else None
        if not destination:
            continue
        match = _BULLET_LINK_RE.match(action.get("line_to_add") or "")
        if not match:
            continue
        prefix, ref, suffix = match.groups()
        display = ref.split("|", 1)[1] if "|" in ref else ref
        if "|" in ref and ref.split("|", 1)[0] == _drop_md(destination):
            continue  # already qualified
        action["line_to_add"] = (
            f"{prefix}[[{qualified_target(destination, display)}]]{suffix}"
        )
        rewritten += 1
    return rewritten


def _drop_md(path: str) -> str:
    return path[:-3] if path.endswith(".md") else path
