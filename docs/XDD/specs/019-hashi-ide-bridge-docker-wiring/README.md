# Specification: 019-hashi-ide-bridge-docker-wiring

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-05-27 |
| **Current Phase** | Implemented (all 4 phases complete; T4.1 live e2e PASSED 2026-05-31) |
| **Last Updated** | 2026-05-31 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 5 Must-Have, 2 Should (banner+statusline), 0 Could (v1.2); vault-path resolution resolved (Kokoro ADR-019 §5) |
| solution.md | completed | Feature-mirror architecture; ADR-1/2/3 confirmed; ADR-5 vault-path routing (Kokoro ADR-019 §5) |
| plan/ | completed | 4 phases, 11 tasks, all complete + two-stage reviewed (spec + quality). T4.1 live e2e PASSED 2026-05-31 (bridge connects, editor context flows host→container); four live-surfaced wiring gaps fixed (token format, update-tomo delivery, workspaceFolders, auto-connect). |

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
| 2026-05-29 | Phase 2 implemented + reviewed | socat in base Dockerfile (0.4.0) + conditional entrypoint proxy (0.3.0). Two-stage review per task (spec compliance → code quality). 14 tests added. |
| 2026-05-29 | Phase 3 implemented + reviewed | Launch banner + /dev/tcp probe + socat drift rebuild (begin-tomo.sh.template 0.12.0); statusline 門:<port>/橋:<port> (tomo-statusline.sh 0.5.2); CLAUDE.md vault-path routing rule + docs/tomo WHY-mirror. 37 tests added. Accepted deviation (MU1): read_kado_port re-reads .mcp.json rather than threading the port out of kado_check — kado_check returns early on cache-hit, so a uniform re-read cleanly covers both paths; cost negligible (tiny local file). |
| 2026-05-29 | Phase 4 partial (T4.2 + T4.3 done) | Full suite 482 passed / 1 skipped (docker-gated install smoke); bash 3.2 clean on all 5 edited shell files; all 7 versioned files bumped. Doc close-out: tools.md Kado-port section made port-agnostic (read from .mcp.json; corrected the false "port differs host vs Docker" claim — hostname differs, port identical). T4.1 live end-to-end (real Obsidian+Hashi) remains pending — manual, owner-driven. Spec flips to Implemented on live confirmation. |
| 2026-05-30 | T4.1 live-test fix — token format | Live testing surfaced that the wizard validated a BARE UUID, but real Hashi tokens are `hashi_<uuid>` (e.g. `hashi_b3f97399-…`) — so every valid token was rejected and the bridge could not be enabled. Fix (user decision: require the `hashi_` prefix): `_is_uuid` → `_is_hashi_token` in configure-ide-bridge.sh (0.2.0), accepts ONLY `hashi_<uuid>`, stores verbatim with prefix; prompt/error text updated; PRD F4-AC4 + SDD interface specs corrected from `<uuid>` to `hashi_<uuid>`. Both review stages PASS. This was the kind of wiring gap T4.1 exists to catch. |
| 2026-05-30 | T4.1 delivery-gap fix — update-tomo ships entrypoint + launcher | Found that `update-tomo.sh` synced instance runtime files but did NOT regenerate `begin-tomo.sh` (0.12.0) nor copy `docker/entrypoint.sh` → `tomo-home/entrypoint.sh` (0.3.0) — so an existing user enabling the bridge via `update-tomo` got a lock file but a stale launcher + entrypoint → no working proxy. Fix (update-tomo.sh 0.5.2): both now flow through the plan/execute model, version-gated, honoring `--dry-run`/`--force`; launcher rendered atomically (tmp→mv) with the same 5 substitutions as install; added a `--config-file` flag (enables isolated testing, mirrors install). 5 new tests. Both review stages PASS. Drift follow-up logged as backlog D-09 (extract a shared render-launcher helper; interim cross-reference comments added to both sed blocks). |
| 2026-05-30 | workspaceFolders carries the container instance path | Live testing: the IDE workspace must match Claude Code's container cwd. The earlier assumption (empty; IDE-only field) was wrong — Claude Code uses workspaceFolders to anchor workspace context. The container instance path equals the host instance path because begin-tomo mounts the instance at the same location via `-v $INSTANCE_PATH:$INSTANCE_PATH` and sets cwd with `-w $INSTANCE_PATH`. configure-ide-bridge.sh 0.3.0 accepts a 4th arg `workspace_path`; install-tomo.sh 0.3.3 and update-tomo.sh 0.5.3 pass `$INSTANCE_PATH`. Supersedes the 2026-05-28 "assumed empty" decision. |
| 2026-05-31 | entrypoint exports CLAUDE_CODE_AUTO_CONNECT_IDE=true in single-lock branch | Live testing showed the IDE Bridge does not auto-connect from a lock file alone — the user had to run `/ide` manually. `CLAUDE_CODE_AUTO_CONNECT_IDE=true` is the documented deterministic mechanism for headless/obscured-parent-terminal cases (highest precedence; `autoConnectIde` is NOT a settings.json field, only `.claude.json` state). Set inside the entrypoint's lock-gated `elif` branch so it is exported only when exactly one lock file is present and the proxy is spawned; never set when 0 locks (bridge not configured). entrypoint.sh bumped to 0.4.0. |
| 2026-05-31 | T4.1 live e2e PASSED — spec Implemented | Bridge connects end-to-end against the real instance + Obsidian/Hashi; editor context flows host→container. All four phases complete. Four wiring gaps that only live testing could surface were fixed at the source (token format `hashi_<uuid>`, update-tomo entrypoint+launcher delivery, workspaceFolders=container instance path, IDE auto-connect) — each TDD + two-stage reviewed. Diagnosis was driven by the instance IDE log (`tomo-home/.cache/.../mcp-logs-ide/*.jsonl`), not container process checks. Carry-forward: a Hashi-side `serverInfo.version` handshake conformance point was noted in an early log — not a Tomo issue; raise with Hashi if it recurs. Open follow-up: backlog D-09 (extract shared render-launcher helper). Note: host pytest needs `jsonschema` installed (env-only; the container ships python3-jsonschema). |

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
