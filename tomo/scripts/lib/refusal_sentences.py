#!/usr/bin/env python3
# version: 0.5.0
"""refusal_sentences.py — the prose the owner reads when a typed name or folder is refused.

One home for every refusal sentence, so the wording of a refusal is edited in
one file and never spread across the renderers that report it. Pure functions
on strings: no I/O, no run state. `typed_name_sentence` takes a code from
`lib.typed_name_check.REFUSAL_REASONS`; `folder_sentence` takes one from
`lib.typed_name_check.FOLDER_REFUSAL_REASONS`; `occupied_target_sentence`
phrases the `vault_occupied` withheld kind. `unchecked_target_sentence`,
`folder_created_sentence` and `qualified_embed_sentence` phrase what the
instruction document reports about a move that IS emitted.
`withheld_attachment_remedy` is the one remedy per withheld-attachment kind,
used by every surface that reports one. Functions taking a code raise
`ValueError` on one they do not know — an unknown code is a bug upstream, never
reported as some other outcome.

Refusal sentences state only what was verified about the typed name (no remedy
text, no promise about a re-run) and name the typed name itself, with control
characters shown as escapes so the sentence stays readable.
"""
from __future__ import annotations

from lib.typed_name_check import is_control_char
from lib.vault_paths import same_spelling


def _visible(text: str) -> str:
    """`text` with every control character replaced by its `\\xNN` escape."""
    return "".join(
        f"\\x{ord(c):02x}" if is_control_char(c) else c for c in text
    )


def typed_name_sentence(reason: str, name: str) -> str:
    """The sentence for one refused typed name, given its reason code."""
    shown = _visible(name)
    if reason == "separator_present":
        return (
            f"typed name refused: `{shown}` contains a path "
            f"separator, which is not allowed in a filename"
        )
    if reason == "forbidden_character":
        return (
            f"typed name refused: `{shown}` contains a character "
            f"Obsidian does not allow in a filename"
        )
    if reason == "blank":
        return "typed name refused: the typed name is blank"
    if reason == "breaks_link":
        return (
            f"typed name refused: `{shown}` has leading or trailing "
            f"whitespace or one of # ^ [ ], which would break the link"
        )
    if reason == "unsafe_sequence":
        return (
            f"typed name refused: `{shown}` contains a control character or "
            f"a template sequence, which would corrupt the instruction set"
        )
    raise ValueError(f"unknown typed-name refusal reason: {reason!r}")


_FOLDER_TAILS = {
    "escapes_vault": "leaves the vault or is not a plain vault-relative path",
    "empty_segment": "contains an empty path segment (`//`)",
    "edge_whitespace": "has whitespace at the start or end of a path segment",
    "trailing_separator": "ends in a path separator",
    "forbidden_character": "contains a character Obsidian does not allow in a name",
    "breaks_link": "contains one of # ^ [ ], which would break the link",
    "unsafe_sequence": (
        "contains a control character or a template sequence, which would "
        "corrupt the instruction set"
    ),
    "inside_inbox": (
        "is the inbox folder or inside it, so the next run would read it as "
        "inbox material"
    ),
}


def folder_sentence(reason: str, folder: str) -> str:
    """The sentence for one refused typed folder, given its reason code."""
    if reason == "blank":
        # A malformed folder line, or two folder lines that disagree, reach
        # the plan as "" too — so the sentence must not say the owner left it
        # blank.
        return (
            "typed folder refused: the folder line is blank or could not be "
            "read as a single folder in backticks"
        )
    tail = _FOLDER_TAILS.get(reason)
    if tail is None:
        raise ValueError(f"unknown typed-folder refusal reason: {reason!r}")
    return f"typed folder refused: `{_visible(folder)}` {tail}"


def occupied_target_sentence(
    target: str, occupier: str | None, *, occupier_is_folder: bool = False
) -> str:
    """The sentence for a `vault_occupied` withheld attachment.

    Names the target and what occupies it as the vault spells it, in words for
    an attachment — never "a note already exists".
    """
    if occupier_is_folder:
        return (
            f"target occupied: the vault already has a folder at "
            f"`{_visible(target)}`, so the attachment is not filed there"
        )
    if occupier is None or same_spelling(occupier, target):
        return (
            f"target occupied: the vault already holds a file at the target "
            f"`{_visible(target)}`, so the attachment is not filed over it"
        )
    return (
        f"target occupied: the vault already holds `{_visible(occupier)}`, "
        f"which differs from the target `{_visible(target)}` only in case — "
        f"the filesystem may treat them as one file — so the attachment is "
        f"not filed over it"
    )


def unchecked_target_sentence(target: str) -> str:
    """The sentence for a move whose target the vault did not answer for.

    States only what is known: nothing was learned about the target, so it is
    never called free.
    """
    return (
        f"the vault did not answer whether anything already occupies "
        f"`{_visible(target)}`, so this target was not checked before this move "
        f"was put into the instructions; if the move fails, the attachment and the source note "
        f"that embeds it stay in the inbox. You can apply this move as it is; to be "
        f"sure first, check in the vault that nothing is at `{_visible(target)}`"
    )


def folder_created_sentence(folder: str) -> str:
    """The sentence for a target folder the vault listed as absent."""
    return f"`{_visible(folder)}` does not exist yet and will be created on apply"


_QUALIFIED_TAILS = {
    "ambiguous": "because another file has the same name",
    "unanswered": "because the vault did not answer whether another file has the same name",
}


def qualified_embed_sentence(target: str, reason: str) -> str:
    """The sentence for an embed written with the attachment's full path."""
    tail = _QUALIFIED_TAILS.get(reason)
    if tail is None:
        raise ValueError(f"unknown embed qualification reason: {reason!r}")
    return f"notes that embed it link to `{_visible(target)}`, {tail}"


_BEFORE_APPLY = "run `/inbox --pass2 --force` before you apply"
_HELD_AFTER_APPLY = (
    "If you have already applied, the attachment is still in the inbox, and so "
    "is every note that embeds it: run `/inbox --recover` and "
)


def withheld_attachment_remedy(kind: str, destination: str | None = None) -> str:
    """The one remedy for a withheld attachment of `kind`, without a final full stop.

    Every surface that reports a withheld attachment ends its line with this,
    so the same item never carries two remedies. `destination` is named only by
    `collision`, the one kind whose remedy depends on it.
    """
    if kind == "typed_folder_refused":
        return (
            f"To fix: correct the folder in the suggestions document and "
            f"{_BEFORE_APPLY}. {_HELD_AFTER_APPLY}choose the attachment's "
            f"folder again"
        )
    if kind == "typed_name_refused":
        return (
            f"To fix: correct the name in the suggestions document and "
            f"{_BEFORE_APPLY}. {_HELD_AFTER_APPLY}name the attachment again"
        )
    if kind == "vault_occupied":
        return (
            f"To fix: free that target in the vault, then {_BEFORE_APPLY}. "
            f"{_HELD_AFTER_APPLY}choose another name for the attachment, or "
            f"free the target first"
        )
    if kind == "collision":
        return (
            f"To fix: rename one of the two files so they no longer share "
            f"`{_visible(destination or '?')}`, then {_BEFORE_APPLY}. "
            f"{_HELD_AFTER_APPLY}name the attachment again"
        )
    if kind == "no_basename":
        return (
            f"To fix: correct that inbox path in the note that embeds it — this "
            f"is not a naming conflict — then {_BEFORE_APPLY}. If you have "
            f"already applied, every note that embeds it is still in the inbox: "
            f"correct the path there and run `/inbox --recover`"
        )
    if kind == "vault_collision_held":
        return (
            f"No action needed unless you change your mind. To file it after "
            f"all, tick Rename in the suggestions document and {_BEFORE_APPLY}. "
            f"If you have already applied, rename the attachment in the inbox "
            f"and run `/inbox` again"
        )
    raise ValueError(f"unknown withheld-attachment kind: {kind!r}")
