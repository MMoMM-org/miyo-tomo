# WHY: lib/note_io.py

> Rationale for decisions in `tomo/scripts/lib/note_io.py`.
> Only non-obvious decisions are recorded here.

## WHY One Config Reader and One Atomic Write (spec 044, #169)

The Phase 2 drift check of spec 044 found the `vault-config.yaml` reader three
times (`note-session.py`, `template-outline.py`, `note-instructions.py`) and the
temp-file-then-`os.replace` write four times (`note-instructions.py`,
`template-outline.py`, `lib/note_meta.py`, `lib/note_process.py`). The copies
had already drifted: the readers caught different exception sets, so a YAML
date such as `2026-13-45` (a `ValueError`) read as empty config in two scripts
and crashed the third. The hyphenated scripts cannot import each other, so the
shared code lives in `lib/`. The owner approved the consolidation.

## WHY the Reader Raises and Never Decides

Each caller has a documented, tested policy for an unusable config, and they
differ on purpose:

| Caller | Missing file | Unreadable / not YAML | Not a mapping |
|---|---|---|---|
| `note-session.py` | empty config, one stderr line | empty config, one stderr line | empty config, silent |
| `template-outline.py` | empty config, silent (checked before the read) | empty config, one stderr line | empty config, silent |
| `note-instructions.py` | exit 2 | exit 2 | exit 2 |

`note-session` and `template-outline` must never crash on a config problem (a
crash makes the model re-run the script); `note-instructions` has no fallback
for `concepts.inbox`, so the user has to fix the config. A reader that chose
one of these would force it on the others. So `load_vault_config` raises
`ConfigUnreadable` or `ConfigNotMapping` (both `ConfigError`) and every caller
keeps its policy at the call site. Two subclasses, because two callers treat a
non-mapping differently from an unreadable file.

The message and `cause` carry the error class only, never file text, because
the callers print them to stderr (privacy: vault config may name sensitive
folders). For `ConfigNotMapping`, `cause` is the parsed value's type name
(`list`, `NoneType`), not an exception class.

WHY `ValueError` is caught: `UnicodeDecodeError` is one, and PyYAML raises a
plain `ValueError` for an impossible timestamp. Since 0.1.0 this means
`note-instructions.py` exits 2 on such a date instead of a traceback; the other
two already read it as empty config.

WHY PyYAML is imported inside the function: `lib/note_meta.py` imports this
module and is stdlib-only at import time; `template-outline.py` imported
PyYAML lazily before the consolidation, too.

## WHY atomic_write_text Does Not Create the Parent

Only `lib/note_process.py` (the process folder may not exist yet) and
`template-outline.py` (the `--out` folder) created the parent folder; the stage
writers in `note-instructions.py` and `lib/note_meta.py` write into a stage
directory that must already exist, and a missing one is a failure there. The
helper writes; the two callers that create a parent still do so themselves.

## WHY the Temp Is `<name>.tmp` Beside the Target

`os.replace` is only atomic within one filesystem, so the temp sits in the
target's folder. The fixed name matches what every copy used before and what
`tests/test_template_outline.py` checks is gone after a run. On failure the
temp is removed (the former copies in `note-instructions.py`, `note_meta.py` and
`note_process.py` left it behind), so a failed write leaves the old target and
nothing else.

## WHY template-outline Keeps Its Own Loop

`template-outline.py` writes up to three files all or nothing: every temp first,
then every `os.replace`. Calling `atomic_write_text` per file would replace the
first before the second is written. It builds the loop on `temp_sibling` and
`remove_temps` instead, so the temp naming and cleanup exist once.

## WHY the Frontmatter Fence Split Was Not Moved Here

`lib/note_process.py` keeps its own `_split`. `lib/template_syntax.leading_block`
splits lines on `\n` only; `note_process` uses `str.splitlines`, which also
splits on a lone `\r`, `\x85`, ` `, form feed and similar. A process file
with old-Mac `\r` line endings reads with its `destination` today and would read
as body-only under `leading_block`. That is a behaviour change, so it was
reported back for an owner decision instead of being made in a refactor.
