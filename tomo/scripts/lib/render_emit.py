# version: 0.1.0
"""render_emit.py — id, path and wikilink helpers shared by every action builder.

Split out of render_actions.py (#216, Constitution L2 file size). Every
`_build_*` module mints ids from one shared counter and joins inbox paths the
same way; keeping those helpers in a leaf module lets each builder module
import them without importing the render_actions facade (which imports the
builders — a cycle). Pure functions, no Kado reads.
"""
from __future__ import annotations

from lib.obsidian_filename import sanitize_stem
from lib.source_link import qualified_target


def _next_id(counter: list[int]) -> str:
    counter[0] += 1
    return f"I{counter[0]:02d}"


def _inbox_join(inbox: str, basename: str) -> str:
    """Join inbox path + basename, normalising the trailing slash."""
    return f"{(inbox or '').rstrip('/')}/{basename}"


def _disambiguate_filename(base_filename: str, used_filenames: set[str]) -> str:
    """Return a filename that is not in *used_filenames*.

    When *base_filename* is not yet used, returns it unchanged (common case —
    CON-2 regression guarantee).  On collision, appends a stable ``_NN`` suffix
    (``_01``, ``_02``, …) in the order callers present collisions.  Raises
    ``ValueError`` if all suffixes up to ``_99`` are already taken.

    Args:
        base_filename: The derived filename, e.g. ``2026-06-11_0900_my-topic.md``.
        used_filenames: Set of filenames already claimed in this render run.
            The caller is responsible for adding the returned name to this set.

    Returns:
        A distinct filename (may equal *base_filename* when there is no collision).

    Raises:
        ValueError: When the collision cannot be resolved within 99 attempts.
    """
    assert base_filename.endswith(".md"), (
        f"_disambiguate_filename requires a .md filename, got: {base_filename!r}"
    )

    if base_filename not in used_filenames:
        return base_filename

    # Strip .md, append _NN, restore .md
    stem = base_filename[:-3]

    for i in range(1, 100):
        candidate = f"{stem}_{i:02d}.md"
        if candidate not in used_filenames:
            return candidate

    raise ValueError(
        f"filename collision guard exhausted for slug '{stem}' — "
        "all suffixes _01 through _99 are taken; cannot render without overwrite"
    )


def _wikilink(title: str, destination: str | None = None) -> str:
    """Render an Obsidian wikilink whose target resolves to the safe filename.

    When the title contains Obsidian-forbidden chars the file is stored under
    a sanitised stem (see _dest_join), so the link must target that stem or it
    dangles. An alias preserves the original title as display text:
    ``[[safe-stem|Original: Title]]``. Titles already safe render as ``[[Title]]``.

    ``destination`` is passed only when this run claims one filename for more
    than one note (spec 034 T5.5), and makes the link name the note by path —
    ``[[Atlas/203 Sources/Dresden|Dresden]]``, the form the vault itself writes
    for a duplicate basename. The alias slot carries the display title either
    way, so the two cases compose: a sanitised title under a contested filename
    renders ``[[folder/safe-stem|Original: Title]]``.
    """
    stem = sanitize_stem(title)
    if destination:
        return f"[[{qualified_target(destination, title)}]]"
    if stem != title:
        return f"[[{stem}|{title}]]"
    return f"[[{title}]]"


def _origin_key(resolved_path: str | None) -> str:
    """The per-note identity the delete bookkeeping joins on (spec 034 T5.0b).

    `_build_delete_source_actions` joins three inputs that describe the same
    inbox note in three different spellings — a confirmed item, a move_note
    origin and a daily entry. That join used to be the bare filename stem,
    which two notes in different inbox subfolders share once discovery is
    recursive: each collection collapsed two distinct notes into one bucket.

    The key is the resolved vault-relative path (ADR-1) with a trailing `.md`
    removed, because the three inputs disagree about that one extension: a
    confirmed item's `source_path` carries it, a daily entry's `source_stem`
    does not, and a move_note origin has already been through
    `_ensure_md_extension`. Every other extension is significant and is kept —
    an `.m4a` origin is a different file from an `.md` note of the same name.
    """
    if not resolved_path:
        return ""
    return resolved_path[:-3] if resolved_path.endswith(".md") else resolved_path
