#!/usr/bin/env python3
# version: 0.2.1
"""attachment_index.py — Detect and normalise attachment embeds in note bodies."""
from __future__ import annotations

import re
from dataclasses import dataclass

from lib.file_extensions import KNOWN_FILE_EXTENSIONS

# The leading (!) is the whole point — every existing wikilink pattern in this
# repo omits it, so none of them distinguish an embed from a plain link.
_EMBED_RE = re.compile(r"(!)?\[\[([^\[\]]+)\]\]")

# Extensions that name a note or a note-like container, not an attachment file.
# KNOWN_FILE_EXTENSIONS also contains "md" — see _is_attachment_target.
_NOTE_EXTENSIONS = frozenset({"md", "canvas", "base"})


def extract_attachment_embeds(body: str) -> list[str]:
    """Return embed targets that name a FILE (not a note), in document order,
    deduplicated.

    Only `![[...]]` counts. A plain `[[...]]` link is a deliberate reference,
    not a dependency of the note.
    """
    out: list[str] = []
    seen: set[str] = set()
    for bang, raw in _EMBED_RE.findall(body):
        if not bang:
            continue  # plain link — not an attachment
        target = _strip_alias_and_anchor(raw)
        if not _is_attachment_target(target):
            continue  # note embed, e.g. ![[Some Note]]
        if target not in seen:
            seen.add(target)
            out.append(target)
    return out


def build_inbox_index(list_dir_result: list[dict] | None) -> dict[str, list[str]]:
    """Index inbox files by basename: basename -> list of vault-relative paths.

    Accepts the flat list of item dicts returned by `KadoClient.list_dir()`,
    each carrying `path` and `type`. Folder entries are excluded; `.md`
    files are indexed like any other file, in list order. Returns `{}` for
    `None`, an empty list, or any other falsy/malformed input — never raises.
    Duplicate identical paths are not deduplicated.
    """
    index: dict[str, list[str]] = {}
    if not list_dir_result:
        return index
    for item in list_dir_result:
        if not isinstance(item, dict) or item.get("type") != "file":
            continue
        path = item.get("path")
        if not path:
            continue
        basename = path.rsplit("/", 1)[-1]
        index.setdefault(basename, []).append(path)
    return index


@dataclass(frozen=True)
class AttachmentRef:
    """One embed target's resolution outcome against an inbox index."""

    embed_target: str
    resolved_path: str | None
    status: str  # "resolved" | "unresolved" | "ambiguous"


def resolve_attachments(
    embed_targets: list[str], index: dict[str, list[str]]
) -> list[AttachmentRef]:
    """Resolve each embed target against an inbox index from build_inbox_index().

    A bare target is looked up by basename: exactly one hit resolves to that
    path; two or more hits are ambiguous; zero hits are unresolved. A
    path-qualified target is looked up by its own basename, then narrowed to
    whichever of that basename's candidate paths ends with the given target
    (e.g. a path ending in ".../Images/karte.jpg" for a target of
    "Images/karte.jpg"); resolved_path is always that retrieved candidate, not
    the target string. Narrowing to zero or to more than one candidate yields
    unresolved / ambiguous respectively, same as the bare case.
    """
    out: list[AttachmentRef] = []
    for target in embed_targets:
        basename = target.rsplit("/", 1)[-1] if "/" in target else target
        candidates = index.get(basename, [])
        if "/" in target:
            candidates = [
                path for path in candidates
                if path == target or path.endswith("/" + target)
            ]
        if len(candidates) == 1:
            out.append(AttachmentRef(target, candidates[0], "resolved"))
        elif len(candidates) > 1:
            out.append(AttachmentRef(target, None, "ambiguous"))
        else:
            out.append(AttachmentRef(target, None, "unresolved"))
    return out


def _is_attachment_target(target: str) -> bool:
    """True if `target` names a file, not a note.

    Two-step test, not a membership check: KNOWN_FILE_EXTENSIONS also
    contains "md", so a naive `ext in KNOWN_FILE_EXTENSIONS` would classify
    `![[Note.md]]` as an attachment. `canvas` and `base` are not in that
    frozenset today, so they already fall out at step one — they are named
    here anyway to keep the note/attachment partition explicit.
    """
    ext = target.rsplit(".", 1)[-1].lower() if "." in target else ""
    return ext in KNOWN_FILE_EXTENSIONS and ext not in _NOTE_EXTENSIONS


def _strip_alias_and_anchor(raw: str) -> str:
    """Strip alias (|) then anchors (# and ^) from a raw embed target.

    Unlike topic-extract.py's `_strip_link_target`, this does NOT strip the
    path — a path-qualified embed target is already an answer and must be
    preserved.
    """
    target = raw.split("|")[0].strip()   # alias: "karte.jpg|Karte" → "karte.jpg"
    target = target.split("#")[0].strip()  # heading/block anchor
    target = target.split("^")[0].strip()  # defensive: bare "target^block"
    return target
