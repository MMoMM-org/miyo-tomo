# Specification: 019-hashi-ide-bridge-docker-wiring

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-05-27 |
| **Current Phase** | SDD |
| **Last Updated** | 2026-05-28 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 5 Must-Have, 2 Should (banner+statusline), 0 Could (v1.2); vault-path resolution resolved (Kokoro ADR-019 §5) |
| solution.md | completed | Feature-mirror architecture; ADR-1/2/3 confirmed; ADR-5 vault-path routing (Kokoro ADR-019 §5) |
| plan/ | in_progress | 4 phases, 11 tasks; mirrors the voice-feature delivery pattern; all 23 PRD ACs traced to tasks |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-27 | Spec created | Kokoro ADR-019 approved Hashi IDE Bridge. Two handoffs received (from-kokoro, from-hashi) requesting Tomo Docker wiring. |
| 2026-05-27 | Lock file in tomo-home, not host mount | User decision: IDE lock file lives in tomo-home/.claude/ide/, managed by install/update scripts, not mounted from host ~/.claude/ide/. |
| 2026-05-27 | PRD completed | 4 Must-Have features (lock file, proxy, image, wizard), 1 Should (banner), 1 Could (health check). 14 acceptance criteria. |
| 2026-05-28 | PRD reconciled with review notes (v1.1) | Port user-configurable (default 23027); dropped 0600 lock-file permission (host-only/cleartext/bind-mount); folded health check into launch banner; added statusline connection indicators (kanji+port) for Kado + Hashi; multiple lock files → fail fast. |
| 2026-05-28 | Vault-path resolution added (v1.2) | New Must-Have Feature 5: Claude resolves IDE-Bridge vault-relative paths via kado-read (vault not mounted in container). `workspaceFolders` assumed empty. Mechanism (CLAUDE.md non-`/` rule vs `kado:` transport prefix vs other) is an OPEN cross-repo question — being raised in Hashi, to be settled in Kokoro. |
| 2026-05-28 | SDD completed | Feature-mirror architecture (reuse the voice-feature pattern across install/Dockerfile/entrypoint/begin-tomo/statusline). ADR-1 socat in base image; ADR-2 entrypoint spawns socat unsupervised; ADR-3 TCP-connect reachability probe — all confirmed. ADR-4 token-cleartext confirmed by PRD. Feature 5 design parked pending Kokoro decision. |
| 2026-05-28 | Feature 5 unblocked (Kokoro ADR-019 §5) | Mechanism (a) chosen: namespace-based routing rule in tomo/CLAUDE.md.template (kado-read-first for vault paths; local Read for container-local; not-found/denied fallback). Recorded as SDD ADR-5. Feature 5 design + ACs filled in; implementation (CLAUDE.md.template edit) sequenced for the plan. workspaceFolders-empty confirmed. |
| 2026-05-28 | PLAN drafted (4 phases, 11 tasks) | Phase 1 wizard-lib + lock file; Phase 2 socat image + entrypoint proxy; Phase 3 banner + statusline + CLAUDE.md routing (3 parallel files); Phase 4 live integration + regression/version-bump audit + doc close-out. All 23 PRD ACs traced to tasks. Recorded deviation from the voice pattern: no instance mirror — the lock file (in bind-mounted tomo-home) is the runtime source for the entrypoint + statusline; begin-tomo reads tomo-install.json host-side. |

## Context

Add Docker-side support for Hashi's IDE Bridge (Kokoro ADR-019). The IDE Bridge gives Claude Code inside the Tomo Docker container real-time editor context from Obsidian (current file, selection, cursor position).

Three integration points:
1. **Dockerfile** — add socat package for TCP proxying
2. **Install/Update scripts** — wizard step to configure IDE Bridge (auth token, lock file generation in tomo-home/.claude/ide/)
3. **Entrypoint** — conditional socat proxy forwarding container localhost:23027 → host.docker.internal:23027

Source handoffs:
- `_inbox/from-kokoro/2026-05-27_kokoro-to-tomo_ide-bridge-docker-wiring.md` (authoritative)
- `_inbox/from-hashi/2026-05-27_hashi-to-tomo_ide-bridge-docker-wiring.md`

Bonus: fix stale Kado port reference (23027→23026) in docs/ai/memory/tools.md.

---
*This file is managed by the xdd-meta skill.*
