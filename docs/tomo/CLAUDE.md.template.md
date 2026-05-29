# WHY: tomo/CLAUDE.md.template

Mirror file for the WHY-persistence layer of `tomo/CLAUDE.md.template`.
This file explains every decision baked into the runtime template — for the user/maintainer audience.
The runtime file contains only imperatives. Rationale, ADR refs, and dates live here.

---

## Vault-Path Routing Rule (Feature 5 / ADR-5)

**Source**: Kokoro ADR-019 §5 (confirmed 2026-05-28).

### Why kado-read-first for every vault-path source

The vault is NOT mounted inside the Tomo container (CON-4: Kado is the sole vault surface).
Direct filesystem access from the container cannot reach vault files regardless of path.
A single namespace-based rule covers every vault-path source:
- IDE Bridge active file (emitted by Hashi via the WS bridge)
- `[[wikilinks]]` and `@`-mentions encountered in vault notes
- `kado-search` results (paths returned by `kado-search`)

One rule avoids the need to categorize the origin of a path — the LLM applies the rule
universally whenever the path looks like it refers to a vault note.

### Why no protocol prefix (ADR-019 §2.3 preserved)

Hashi emits plain vault-relative paths (e.g. `PKM/Notes/my-note.md`), not `kado:`-prefixed paths.
A protocol-prefix approach would require Hashi to tag paths, a Tomo parser to strip the prefix,
and would not cover `[[wikilinks]]` or `@`-mentions (which arrive without any prefix).
The namespace rule is more general and requires no protocol extension.

Mechanism (b) — a `kado:` prefix — is the documented reserve: if prompt-level steering proves
unreliable in practice, a future ADR could adopt the prefix as a hard signal. That would require
a Hashi convention (emit `kado:`-prefixed paths) plus a Tomo parser. Until then, mechanism (a)
(this routing rule) is the chosen approach.

### Why fail-closed

If a vault path cannot be resolved via Kado (e.g. the path is wrong, Kado is unreachable,
or the path was never a real vault file), silently substituting a local file would produce
incorrect results and obscure the problem. Fail-closed means the LLM surfaces an error,
giving the user an actionable signal instead of silently reading the wrong content.

### Why the ambiguous-path fallback exists

Some tasks involve container-local working files (e.g. draft instruction sets, temp files)
whose paths look like bare relative paths. If the LLM always routed bare paths to kado-read,
it would fail on every container-local file. The fallback (try kado-read first, then local
Read on not-found/denied) lets the routing rule handle both cases without requiring the LLM
to pre-classify every path it encounters.

### Why selection text needs no read

When the IDE Bridge delivers selected text, the content arrives in-context via the bridge
message payload — no separate Kado read or local Read is needed. The routing rule is only
about path-based reads; in-context content does not involve a path resolution step.

### Summary of the rule's four namespace cases

| Source | Action |
|--------|--------|
| Vault-note path (active file, `[[wikilink]]`, `@`-mention, kado-search result) | Read via kado-read — never local Read or filesystem |
| Container-local working file | Read via local Read |
| Ambiguous bare relative path | Try kado-read first; fall back to local Read only on not-found/denied |
| True vault path not readable via Kado | Error — do not silently substitute a local file |

Selection text (arrives in-context via the bridge) needs no read at all.
