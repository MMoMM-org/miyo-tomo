---
from: tomo
to: kokoro
date: 2026-05-28
topic: IDE Bridge vault-path resolution — mechanism decision request
status: done
status_note: Recorded in ADR-019 §5: mechanism (a) Tomo CLAUDE.md routing rule (kado-read-first, namespace-based, local fallback); (b) prefixes retained as fallback; workspaceFolders-empty confirmed. Reply handoffs sent to for-tomo and for-hashi.
priority: normal
requires_action: true
---

# IDE Bridge vault-path resolution — how does Tomo's Claude reach the file Hashi reports?

## What Changed

Tomo's XDD 019 (Hashi IDE Bridge Docker Wiring) PRD reached v1.2 and now carries a **Must-Have Feature 5 (Vault Path Resolution)** plus an **unresolved cross-repo open question**. Feature 5's acceptance criteria are written but intentionally left unchecked — they depend on a mechanism decision that is Kokoro's to make.

## Why

The IDE Bridge gives Claude (running inside the Tomo Docker container) editor context from Obsidian. There are two distinct channels, and the seam between them is unspecified:

- **Hashi IDE Bridge (push, WebSocket):** delivers the active file path + the **selected text content**. For the selection itself, Claude needs nothing more.
- **Kado MCP (pull):** the *only* way Claude can read vault content **beyond** the selection (full file, linked notes). The vault filesystem is **not** mounted in the container — by constitution, Kado is the sole inbound vault surface.

Key facts:
- The bridge-reported path is **vault-relative** — the same namespace Kado addresses — so it is a valid `kado-read` target with no remapping.
- The lock file's `workspaceFolders` is **empty** (IDE-only field, no meaning in this host/container topology).
- Therefore a bare path like `Notes/Foo.md` is **unresolvable on the container filesystem**; if Claude naively uses its local `Read` tool it fails. Claude must be *steered* to route such paths through Kado.

## Impact on Kokoro

This is a cross-component interface concern (Hashi ↔ Tomo ↔ Kado), so per the MiYo constitution it must be **decided and recorded in Kokoro** (ADR or decision-log entry), not settled unilaterally in Tomo. The **same question is being raised in Hashi in parallel** — Tomo and Hashi need to converge on one recorded mechanism. ADR-019 (IDE Bridge) is the natural anchor for this addition.

## Action Required

Pick a mechanism (or propose another) and record it so Tomo (019 Feature 5) and Hashi can implement against a single contract:

- **(a) CLAUDE.md routing rule** — any path **without a leading `/`** → Claude attempts a `kado-read` first. Mirrors the existing `@`-redirection convention in Tomo, which already works. Lowest-friction; no Hashi-side change.
- **(b) Transport-prefixed references from Hashi** — e.g. `kado:Notes/Foo.md` — routing made explicit in the reference itself. Requires a Hashi-side convention and a Tomo-side parser.
- **(c) Other / TBD** — Kokoro's call.

Please also confirm the `workspaceFolders`-empty assumption holds from the ADR-019 perspective.

## References

- Tomo spec: `docs/XDD/specs/019-hashi-ide-bridge-docker-wiring/requirements.md` (v1.2 — Feature 5, Assumptions, Open Questions)
- Kokoro: ADR-019 (Hashi IDE Bridge)
- Parallel question raised in Hashi (same topic) — to be reconciled here

