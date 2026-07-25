# WHY: kado-read-file.py

> Rationale for decisions in `tomo/scripts/kado-read-file.py`.
> The read counterpart to `kado-write-file.py`: download a vault file to a local
> path via the embedded Kado client (spec 030 Phase 7, T7.4).

## A script, not an inline kado-read tool call

WHY the agent pulls a vault file via this script instead of an inline `kado-read` MCP tool
call: same rationale as `kado-write-file.py` in the other direction. The content is written
straight to disk by this script's own Kado client, so a large artefact (a published
garden-audit report + wire) NEVER passes through the agent's output-token budget. An inline
`kado-read` would emit the whole body as a tool result and blow the token limit on a big report.

## Extension routes the read operation

WHY `.md` → `read_note` and everything else → `read_file_bytes`: Kado's note operation returns
markdown as text and rejects non-`.md` paths with `VALIDATION_ERROR`; the file operation returns
base64 bytes. This mirrors `kado-write-file.py`'s extension-based operation selection so the read
and write helpers are symmetric — a `.md` written as a note round-trips by being read as a note.

## Filled the read gap for the --suggest flow

WHY this script exists at all: `kado-write-file.py` shipped but had no read counterpart, and the
`--suggest` agent flow needs to fetch the published report + wire back into the instance before
enriching them. Rather than fold Kado access into `garden-audit-suggest.py` (which would couple
the deterministic enrichment helper to a live Kado client and make it harder to unit-test), the
transport stays a separate, reusable helper — matching the existing write-side separation.

## Version 0.1.0

WHY: Initial implementation (spec-030 Phase 7 T7.4) — the read counterpart to the shipped
`kado-write-file.py`. `update-tomo.sh` skips unchanged versions.
