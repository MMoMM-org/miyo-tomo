# WHY: lib/file_extensions.py

> Rationale for decisions in `tomo/scripts/lib/file_extensions.py`.
> The module owns `KNOWN_FILE_EXTENSIONS`, the single allowlist used to tell a
> real file extension apart from a dotted note title.

## Split Out of `render_actions.py` to Keep `attachment_index.py` a Pure Library (spec 031 T1.1, ADR-2)

WHY the allowlist moved to its own module instead of `attachment_index.py`
importing it from `render_actions.py`, where it used to live: `render_actions.py`
is not a leaf module — importing anything from it transitively pulls in
roughly 175 modules, including `kado_client`, and triggers a module-scope
`exec_module()` of `tag-handler-group.py` (`render_actions.py:32-44`) purely
as an import side effect. `attachment_index.py` needs to stay a genuinely
I/O-free text library per ADR-2's pure-library boundary — a text-classification
function should not need a working Kado client and a live tag-handler module
just to be imported. Relocating `KNOWN_FILE_EXTENSIONS` into its own module
dropped the transitive import count for `attachment_index.py` to 4.

`render_actions.py` keeps `_KNOWN_FILE_EXTENSIONS = KNOWN_FILE_EXTENSIONS` as a
back-compat alias, so its own call sites (`_ensure_md_extension` and its
callers) needed no changes. A subprocess-based test in
`tests/test_attachment_index.py` guards against the alias and the module
drifting apart again.

This was a deliberate, approved deviation from the SDD's "reuses the existing
classifier" wording: the single source of truth for the allowlist moved to a
new home, it was not duplicated. There is still exactly one frozenset;
`render_actions.py` points at it rather than owning a second copy.
