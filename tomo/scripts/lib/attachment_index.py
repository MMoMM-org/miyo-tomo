#!/usr/bin/env python3
# version: 0.4.0
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


def is_file_entry(item: object) -> bool:
    """True if `item` is a Kado `listDir` entry naming a file, not a folder.

    Case-insensitive and defensive: Kado's gateway always emits a lowercase
    `"file"`/`"folder"` literal (`search-adapter.ts`), but this repo's two
    listDir-filtering call sites — `build_inbox_index` below and
    `inbox-triage.py`'s `discover_files` — independently disagreed on how to
    handle case variants, a `None` type, a missing `type` key, and a
    non-dict entry (spec 034 T3.1). Both now route through this single
    predicate so they cannot re-diverge (ADR-3).
    """
    if not isinstance(item, dict):
        return False
    return (item.get("type") or "").lower() == "file"


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
        if not is_file_entry(item):
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


def narrow_candidates(
    reference: str,
    index: dict[str, list[str]] | None,
    *,
    default_extension: str | None = None,
) -> list[str]:
    """The one narrowing rule: a wikilink-style reference -> its candidate paths.

    Strips the alias and any anchor, optionally supplies the extension a note
    link omits, matches by basename, then narrows by path suffix when the
    reference is path-qualified. Returns every surviving candidate, in index
    order; callers decide what one, none or several mean to them.

    `default_extension` (e.g. ".md") is appended only when the stripped
    reference does not already end in it. Order matters and is owned here:
    appending before stripping would search for "Dresden|Alias.md".

    This is the single definition of the rule. It was previously hand-copied
    at three call sites and had already drifted — one copy stripped "|" and
    "#" but not "^", so a block-anchored reference failed against an index
    that contained it (PRD Business Rule 9, spec 034).
    """
    target = _strip_alias_and_anchor(reference)
    if default_extension and not target.lower().endswith(default_extension.lower()):
        target += default_extension
    basename = target.rsplit("/", 1)[-1]
    candidates = (index or {}).get(basename, [])
    if "/" in target:
        candidates = [
            path for path in candidates
            if path == target or path.endswith("/" + target)
        ]
    return list(candidates)


def resolve_attachments(
    embed_targets: list[str], index: dict[str, list[str]]
) -> list[AttachmentRef]:
    """Resolve each embed target against an inbox index from build_inbox_index().

    Narrowing is `narrow_candidates` — shared with every other site that
    resolves a reference against this index. This function only maps its
    result onto the three-state outcome: exactly one candidate resolves, two
    or more are ambiguous, zero is unresolved. `resolved_path` is always the
    retrieved candidate, never the target string, and `embed_target` echoes
    the reference exactly as given (alias and anchor included, if any).
    """
    out: list[AttachmentRef] = []
    for target in embed_targets:
        candidates = narrow_candidates(target, index)
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
