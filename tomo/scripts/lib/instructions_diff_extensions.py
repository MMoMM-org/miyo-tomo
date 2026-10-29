# version: 0.1.0
"""instructions_diff_extensions.py — per-member check of extend_moc items.

Extracted from instructions-diff.py (#216). An extend_moc item has no file
action, so the per-item move/create check does not apply; each member is
checked instead against the renderer's tomo.extensions record (spec 042 T4.4).
"""
from __future__ import annotations

from lib.instructions_diff_keys import _bullet_titles, _moc_stem, _stem


def _reconcile_extensions(
    expected: dict, instrs: dict, unresolvable: list[dict],
) -> tuple[list[str], list[str], bool]:
    """Check each extend_moc member against the renderer's tomo.extensions record.

    Per member: an add_relationship naming [[MOC]] unless the record lists the
    member in no_relationship; exactly one link_to_moc into the MOC unless
    already linked (or withheld as unresolvable), else none. Subtracts the
    links not owed from expected link_to_moc. Returns (lines, notes, hard_fail).
    """
    tomo_block = instrs.get("tomo") or {}
    records = {r.get("id"): r for r in tomo_block.get("extensions") or []}
    withheld = {w.get("id"): w for w in tomo_block.get("withheld_extensions") or []}
    actions = instrs.get("actions") or []
    lines: list[str] = []
    notes: list[str] = []
    hard_fail = False
    for ext in expected.get("extensions") or []:
        moc, members = ext["target_moc"], ext["members"]
        if ext["id"] in withheld:
            expected["counts"]["link_to_moc"] -= len(members)
            w = withheld[ext["id"]]
            notes.append(
                f"extension of [[{moc}]] ({ext['id']}) withheld — "
                f"{w.get('reason', '?')}; {len(members)} member(s) not applied, "
                "see \"MOC extension not applied\" in instructions.md"
            )
            lines.append(f"    {ext['id']:<6s} extend_moc  [[{moc}]] withheld")
            continue
        record = records.get(ext["id"])
        if record is None:
            hard_fail = True
            lines.append(f"    {ext['id']:<6s} extend_moc  [[{moc}]] [MISSING — not rendered]")
            continue
        already = {m.casefold() for m in record.get("already_linked") or []}
        no_rel = {(n.get("member") or "").casefold()
                  for n in record.get("no_relationship") or []}
        withheld_links = {
            r.get("source_note_title") for r in unresolvable
            if _moc_stem(r.get("target_moc")) == moc
        }
        for member in members:
            owes_link = (member.casefold() not in already
                         and member not in withheld_links)
            if not owes_link:
                expected["counts"]["link_to_moc"] -= 1
            has_rel = any(
                a["action"] == "add_relationship"
                and _stem(a.get("target_moc_path")) == member
                and f"[[{moc}]]" in (a.get("line") or "")
                for a in actions
            )
            n_links = sum(
                1 for a in actions
                if a["action"] == "link_to_moc" and _moc_stem(a.get("target_moc")) == moc
                and (a.get("source_note_title") == member
                     or member in _bullet_titles(a.get("line_to_add")))
            )
            rel_ok = has_rel == (member.casefold() not in no_rel)
            link_ok = n_links == (1 if owes_link else 0)
            if not (rel_ok and link_ok):
                hard_fail = True
            lines.append(
                f"    {ext['id']:<6s} extend_moc  {member[:40]:<40s} "
                f"rel={'[OK]' if rel_ok else '[DIFF]'} "
                f"link={'[OK]' if link_ok else f'[DIFF want={int(owes_link)} got={n_links}]'}"
            )
        if not record.get("outgoing_checked", True):
            notes.append(
                f"extension of [[{moc}]] ({ext['id']}): already-linked check "
                "unavailable at render — a line was emitted for every member"
            )
    return lines, notes, hard_fail
