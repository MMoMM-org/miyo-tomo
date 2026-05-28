---
title: "Phase 2: Container Runtime Wiring"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Container Runtime Wiring

Makes the bridge reachable from inside the container: `socat` is baked into the base image, and the entrypoint spawns a localhost→host TCP proxy when (and only when) a lock file is present. This is the transport layer the Phase 1 lock file points Claude Code at.

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/Feature 2 (Network Proxy for WebSocket); AC1-AC3]`
- `[ref: PRD/Feature 3 (Container Image Support); AC1-AC2]`
- `[ref: SDD/Runtime View → Launch + connect; lines: 220-244]`
- `[ref: SDD/Error Handling; lines: 246-252]` — no-lock-silent, multiple-lock-fail-fast, socat-dies-no-restart
- `[ref: SDD/Deployment View; lines: 254-259]`

**Key Decisions**:
- **ADR-1**: `socat` in the **base** image layer, always present (Feature 3 AC1 needs it "regardless of whether IDE Bridge is configured"). No conditional `ARG`.
- **ADR-2**: entrypoint spawns `socat` **unsupervised**, in the background, only if a lock file is present, **before** `exec "$@"`. No auto-restart.
- **CON-2**: `host.docker.internal` is the only host-reachability mechanism (macOS/OrbStack/Docker-Desktop). **CON-3**: no exposed ports — proxy is container-localhost only.

**Dependencies**: Phase 1 (the lock file the entrypoint detects). The Dockerfile change (T2.1) has no code dependency on T2.2 and they touch different files — they may run in parallel. The drift-rebuild that ships the new image to existing users is wired in Phase 3 T3.1 (begin-tomo.sh) — call out in T2.1.

---

## Tasks

- [ ] **T2.1 Add `socat` to the base Docker image** `[activity: devops]` `[parallel: true]`

  1. **Prime**: Read `docker/Dockerfile` — the base `apt-get install` layer (lines ~12-26) and the existing voice `ARG`/label drift pattern (lines ~40-54) you are **not** copying (ADR-1 says base, not ARG).
  2. **Test**: build assertion — after `docker build`, `docker run --rm <image> sh -c 'command -v socat'` exits 0 `[ref: PRD/F3-AC1]`. (Build-dependent; if a full build is too heavy for the loop, assert the Dockerfile contains `socat` in the unconditional base layer via a grep test and defer the live build to Phase 4 T4.1.)
  3. **Implement**: add `socat` to the unconditional base `apt-get install -y --no-install-recommends` list in `docker/Dockerfile`; bump `# version:` (0.3.1 → 0.4.0). Leave the voice `ARG VOICE_ENABLED` block untouched (CON-6).
  4. **Validate**: `docker build -t miyo-tomo:test ./docker/` succeeds; `socat` resolves in the built image; voice build path still toggles correctly.
  5. **Success**: every freshly built image contains `socat` `[ref: PRD/F3-AC1]`. (Drift rebuild for pre-socat images is delivered in T3.1.)

- [ ] **T2.2 Conditional `socat` proxy spawn in the entrypoint** `[activity: devops]` `[parallel: true]`

  1. **Prime**: Read `docker/entrypoint.sh` (the `exec "$@"` tail at line ~29 and the `on-start.sh` hook block as the placement reference). The lock file is at `~/.claude/ide/<port>.lock` = `/home/coder/.claude/ide/<port>.lock` (tomo-home is bind-mounted to `/home/coder`). Read `[ref: SDD/Error Handling; lines: 246-252]`.
  2. **Test** (`tests/ide_bridge/test_entrypoint_proxy.py`, exercising the proxy-decision logic via `bash -c` against a fake `~/.claude/ide` dir; stub `socat` with a shell function/`PATH` shim that records its argv to a file instead of execing the real binary, and stub the final `exec`):
     - no `.claude/ide/` dir / no `.lock` → no socat invocation, exit 0, no error on stderr `[ref: PRD/F2-AC2]`
     - exactly one `<port>.lock` → socat invoked once, backgrounded, with `127.0.0.1:<port>` listen → `host.docker.internal:<port>` target; **port derived from the lock filename** (Business Rule 5) `[ref: PRD/F2-AC1]`
     - two `.lock` files present → fail fast, non-zero exit, message names the directory; socat NOT invoked `[ref: SDD/Error Handling; PRD/Feature 1 edge case]`
     - proxy spawn does not block `exec "$@"` (the recorded command list still reaches the stubbed exec)
  3. **Implement**: in `docker/entrypoint.sh`, before `exec "$@"`, add an IDE Bridge block (bump `# version:` 0.2.0 → 0.3.0):
     - `IDE_DIR="$HOME/.claude/ide"`; if dir absent → skip silently (Feature 2 AC2)
     - count `"$IDE_DIR"/*.lock` (bash 3.2-safe glob with nullglob-equivalent guard); 0 → skip; >1 → `echo` an error naming `$IDE_DIR` and `exit 1`
     - 1 → derive `PORT` from `basename "$lock" .lock`; spawn `socat TCP-LISTEN:"$PORT",fork,reuseaddr,bind=127.0.0.1 TCP:host.docker.internal:"$PORT" &` (unsupervised, ADR-2); keep `set -e` honored (background spawn must not trip errexit — guard as needed)
     - never fail the container start when IDE Bridge is unconfigured or Hashi is down (Quality: Reliability)
  4. **Validate**: `pytest tests/ide_bridge/test_entrypoint_proxy.py -v` green; `/bin/bash -n docker/entrypoint.sh` clean; existing entrypoint behavior (git config, on-start hook, `exec`) unchanged.
  5. **Success**:
     - lock present → proxy forwards container `127.0.0.1:<port>` → `host.docker.internal:<port>` `[ref: PRD/F2-AC1]`
     - no lock → no proxy, no error `[ref: PRD/F2-AC2]`
     - multiple locks → fail fast pointing at the directory `[ref: SDD/Error Handling]`

- [ ] **T2.3 Phase Validation** `[activity: validate]`

  `pytest tests/ide_bridge/ -v` and full `pytest tests/` (CON-6). `/bin/bash -n docker/entrypoint.sh`. `docker build ./docker/` succeeds and `socat` is present. Confirm version bumps on both `Dockerfile` and `entrypoint.sh` (else `update-tomo.sh`/rebuild ship nothing — memory `feedback_bump_version_on_managed_file_edit`). Verify against PRD Feature 2 + Feature 3 ACs and SDD Runtime/Error-Handling sections.
