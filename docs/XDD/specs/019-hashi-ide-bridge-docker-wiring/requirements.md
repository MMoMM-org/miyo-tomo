---
title: "Hashi IDE Bridge Docker Wiring"
status: draft
version: "1.2"
---

# Product Requirements Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria (Gherkin format)
- [x] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [x] Problem is validated by evidence (not assumptions)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Every metric has corresponding tracking events
- [x] No feature redundancy (check for duplicates)
- [x] No technical implementation details included
- [x] A new team member could understand this PRD

---

## Product Overview

### Vision

Claude Code running inside the Tomo Docker container can receive real-time editor context from Obsidian via Hashi's IDE Bridge — giving it awareness of which file, section, and selection the user is looking at — without any changes to the security model or vault access controls.

### Problem Statement

When Claude Code runs inside the Tomo Docker container, it has no awareness of what the user is currently looking at in Obsidian. The user must manually describe their context ("I'm looking at the MOC for Shell & Terminal") every time they want Claude to reason about the visible content. This is friction that desktop Claude Code users don't experience — IDE integrations (VS Code, JetBrains) provide automatic editor context via the Claude Code IDE protocol.

Hashi's IDE Bridge (Kokoro ADR-019) implements this protocol as a WebSocket server inside Obsidian, but Claude Code inside Docker cannot reach it because:
1. The lock file Claude Code uses to discover the IDE server lives on the host, not inside the container
2. The WebSocket server binds to the host's `127.0.0.1:23027`, which is unreachable from the container's network namespace

Without Docker-side wiring, Tomo users cannot benefit from the IDE Bridge even after installing Hashi.

### Value Proposition

Zero-friction editor context for containerized Claude Code. After a one-time setup step (providing the auth token from Hashi), every Tomo session automatically connects to the IDE Bridge. The user selects text in Obsidian and Claude Code shows it inline — no copy-paste, no manual descriptions, no workflow interruption.

## User Personas

### Primary Persona: Tomo User with Hashi

- **Demographics:** PKM practitioner using Obsidian, has Tomo (Docker-based Claude Code), Kado (Obsidian MCP Gateway) and Hashi (Obsidian plugin) installed. Comfortable with terminal workflows.
- **Goals:** Wants Claude Code inside Docker to be aware of what they're reading/editing in Obsidian. Wants the same editor-context experience that VS Code users get natively.
- **Pain Points:** Must manually copy or describe context from Obsidian into the Tomo session. Switching between Obsidian and the terminal breaks flow. Loses the "Claude sees what I see" experience when using Docker instead of native Claude Code.

### Secondary Personas

**Tomo User without Hashi** — Has Tomo but hasn't installed Hashi yet. The IDE Bridge wiring must be invisible to this user (no errors, no prompts, no degradation). They may install Hashi later and should be able to add IDE Bridge support via `update-tomo.sh` without reinstalling.

**New Tomo User** — Installing Tomo for the first time. The install wizard should ask about IDE Bridge alongside the existing voice transcription wizard. If they haven't installed Hashi yet, the wizard should tell them to come back via `update-tomo.sh` after installing Hashi.

## User Journey Maps

### Primary User Journey: First-Time IDE Bridge Setup

1. **Awareness:** User installs Hashi in Obsidian. Hashi settings show an auth token and mention Tomo integration.
2. **Consideration:** User reads Hashi docs or sees a Tomo handoff explaining the IDE Bridge capability.
3. **Adoption:** User runs `update-tomo.sh` (or `install-tomo.sh` for new installs). The wizard asks "Enable IDE Bridge?" and requests the auth token and port from Hashi settings.
4. **Usage:** User launches Tomo via `begin-tomo.sh`. The banner shows "IDE: bridge active" and the statusline shows the connection state. They select text in Obsidian and see `⧉ Selected N lines from <file>` in the Claude Code transcript.
5. **Retention:** Every subsequent Tomo session auto-connects to the IDE Bridge. No recurring configuration needed.

### Secondary User Journey: Post-Install IDE Bridge Addition

1. User already has a working Tomo installation (without IDE Bridge).
2. User installs Hashi in Obsidian and copies the auth token from Hashi settings.
3. User runs `update-tomo.sh` — the wizard detects no IDE Bridge config and offers to set it up.
4. After entering the auth token and port, the lock file is generated in `tomo-home/.claude/ide/`.
5. Next `begin-tomo.sh` launch picks up the config automatically.

### Tertiary User Journey: Auth Token Rotation or Hashi Port change

1. User reinstalls Hashi or resets its settings — Hashi generates a new auth token.
2. User runs `update-tomo.sh` — the wizard shows current IDE Bridge state and offers to update the token or port.
3. User enters the new token or port. Lock file is regenerated.
4. Next Tomo launch connects with the new token or port.

## Feature Requirements

### Must Have Features

#### Feature 1: IDE Lock File Management

- **User Story:** As a Tomo user with Hashi, I want the install/update scripts to generate a Claude Code IDE lock file so that Claude Code inside Docker can discover and connect to Hashi's IDE Bridge.
- **Acceptance Criteria:**
  - [x] Given the user enables IDE Bridge and provides a valid auth token and port during install, When install-tomo.sh completes, Then a lock file exists at `tomo-home/.claude/ide/<port>.lock` (default `23027.lock`) with the correct JSON format
  - [x] Given the user has an existing Tomo installation without IDE Bridge, When they run update-tomo.sh and enable IDE Bridge, Then the lock file is created without requiring a full reinstall
  - [x] Given the user has IDE Bridge enabled and runs update-tomo.sh, When they choose to update the auth token, Then the lock file is regenerated with the new token
  - [x] Given the lock file exists, When it is read by Claude Code, Then it contains valid JSON with fields: pid, workspaceFolders, ideName, transport, authToken

#### Feature 2: Network Proxy for WebSocket

- **User Story:** As a Tomo user with IDE Bridge configured, I want the container to automatically proxy the WebSocket connection so that Claude Code can reach Hashi's server on the host.
- **Acceptance Criteria:**
  - [x] Given the lock file directory exists in the container and contains a `.lock` file, When the container starts, Then a TCP proxy forwards the container's `127.0.0.1:<port>` to `host.docker.internal:<port>`
  - [x] Given no lock file directory exists, When the container starts, Then no proxy is started and no error is shown
  - [x] Given the proxy is running, When Claude Code reads the lock file and connects to `ws://127.0.0.1:23027`, Then the connection reaches Hashi's WebSocket server on the host

#### Feature 3: Container Image Support

- **User Story:** As a Tomo user, I want the Docker image to include the networking tool needed for the proxy so that IDE Bridge works without manual container modifications.
- **Acceptance Criteria:**
  - [x] Given a freshly built Tomo Docker image, When the entrypoint checks for the proxy tool, Then it is available regardless of whether IDE Bridge is configured
  - [x] Given an existing Tomo image without the proxy tool, When the user runs begin-tomo.sh after enabling IDE Bridge, Then the image is rebuilt to include the tool (drift detection)

#### Feature 4: Install/Update Wizard

- **User Story:** As a Tomo user, I want the install and update scripts to guide me through IDE Bridge configuration so that I don't need to manually create files or know the lock file format.
- **Acceptance Criteria:**
  - [x] Given a fresh install, When install-tomo.sh runs the wizard, Then it asks whether to enable IDE Bridge and accepts the auth token and port
  - [x] Given a non-interactive install (`--non-interactive`), When install-tomo.sh runs, Then IDE Bridge configuration is skipped (preserving current state if updating)
  - [x] Given IDE Bridge is already configured, When update-tomo.sh runs, Then it shows current status and offers: keep / update token or port / disable
  - [x] Given the user enters an invalid auth token (not a UUID), When the wizard validates input, Then it rejects the token with a clear error message
  - [x] Given the user does not specify a port, When the wizard runs, Then it defaults to 23027 (Kado uses 23026); a non-numeric or out-of-range port is rejected with a clear error message

#### Feature 5: Vault Path Resolution for Bridge Context

- **User Story:** As a Tomo user, when the IDE Bridge tells Claude which file I'm viewing, I want Claude to read that file's full content (and related notes) through Kado, so it can reason about more than just the pushed selection.
- **Acceptance Criteria:**
  - [ ] Given the selected text is pushed over the IDE Bridge, When Claude uses the selection, Then no Kado read is required for the selection content itself
  - [ ] Given the IDE Bridge reports an active file with a vault-relative path, When Claude needs content beyond the selection, Then it reads the file via `kado-read` using that vault-relative path — never the container's local filesystem (the vault is not mounted in the container)
  - [ ] Given a file reference Claude cannot resolve via Kado (denied by ACL or capability gate), When Claude attempts the read, Then the denial surfaces clearly rather than silently falling back to a non-existent local path
- **Open mechanism (resolve before implementation — see Open Questions):** how Claude is steered to route bridge / vault-relative paths to `kado-read`. The vault FS is not mounted, so a bare path is unresolvable locally; a convention is needed. Being coordinated with Hashi and Kokoro.

### Should Have Features

#### Feature 6: Launch Banner Status

- **User Story:** As a Tomo user, I want the launch banner to show IDE Bridge status — including whether Hashi is actually reachable — so that I know whether editor context will be available in this session.
- **Acceptance Criteria:**
  - [x] Given IDE Bridge is configured and the lock file exists, When begin-tomo.sh launches, Then the banner shows "IDE: bridge active" (or similar)
  - [x] Given IDE Bridge is not configured, When begin-tomo.sh launches, Then the banner shows "IDE: not configured" (or similar, dimmed)
  - [x] Given IDE Bridge is configured but Hashi is not reachable, When begin-tomo.sh launches, Then a non-blocking warning is shown and the launch continues (reachability check, mirroring how Kado's status is probed at launch)

#### Feature 7: Statusline Connection Indicators

- **User Story:** As a Tomo user, I want the Tomo statusline to show the Hashi IDE Bridge connection state alongside Kado, in a consistent kanji + port format, so I can see both connections at a glance.
- **Acceptance Criteria:**
  - [x] Given Kado is configured, When the statusline renders, Then the Kado indicator uses the kanji + port format: `門:<kado-port> ✓` (green) when reachable, `門:<kado-port> ✗` (red) when unreachable/error, `門:<kado-port> ✓ Tags ✗` (yellow) when reachable but tag access is denied, `門:<kado-port> ?` (yellow) when not configured
  - [x] Given IDE Bridge is configured, When the statusline renders, Then the Hashi indicator shows `橋:<hashi-port> ✓` (green) when reachable, `橋:<hashi-port> ✗` (red) when unreachable, `橋:<hashi-port> ?` (yellow) when not configured — with no "Tags" sub-state, since the IDE Bridge exposes no capability gate
  - [x] Given either indicator renders, When state changes, Then connection state remains color-coded (green / red / yellow) as today — color is retained, not replaced by symbols

### Could Have Features

_None for this phase — the statusline redesign and the launch-time reachability check raised during review were promoted to Should-Have (Features 6 and 7)._

### Won't Have (This Phase)

- **Automatic token discovery** — The auth token is a one-time manual copy from Hashi settings. No automated exchange between Hashi and Tomo install scripts.
- **Multi-IDE support** — Only one IDE Bridge connection at a time. Tomo connects to a single Obsidian instance (as with its single Kado connection), so multiplexing across multiple Obsidian windows is out of scope and not expected to change.
- **Token refresh protocol** — No automatic token rotation. If Hashi regenerates the token, user re-runs update-tomo.sh manually.
- **Lock file mounting from host** — The lock file is generated by Tomo scripts in tomo-home, not bind-mounted from the host's `~/.claude/ide/`. This avoids host dependency and keeps tomo-home self-contained.

## Detailed Feature Specifications

### Feature: IDE Lock File Management

**Description:** The install and update scripts generate a JSON lock file that mimics the format Claude Code expects from an IDE integration. The lock file tells Claude Code where to find the WebSocket server and how to authenticate.

**User Flow:**
1. User runs `install-tomo.sh` or `update-tomo.sh`
2. Wizard asks: "Enable Hashi IDE Bridge? (requires Hashi plugin in Obsidian) [y/N]"
3. If yes, wizard asks: "Enter the auth token from Hashi settings:"
4. Wizard validates the token (UUID format)
5. Wizard asks: "Enter the IDE Bridge port [default 23027]:" and validates it is numeric and in range
6. Script creates `tomo-home/.claude/ide/<port>.lock` with the correct JSON
7. Script persists the IDE Bridge config (enabled flag, auth token, port) to `tomo-install.json`

**Business Rules:**
- Rule 1: The `pid` field is set to `0` (not meaningful across host/container boundary)
- Rule 2: The `ideName` field is always `"Obsidian"`
- Rule 3: The `transport` field is always `"ws"`
- Rule 4: Disabling IDE Bridge removes the lock file but preserves the auth token and port in tomo-install.json (re-enabling doesn't require re-entering them)
- Rule 5: The port in the lock file name must match the configured IDE Bridge port and the port used by the socat proxy
- Rule 6: The lock file is deliberately NOT given `0600` permissions — it is a bind-mounted file inside the container, the token is stored in cleartext, and the connection is host-only (`127.0.0.1`), so file-permission hardening (the former CVE-2025-52882 mitigation) adds no protection in this topology

**Edge Cases:**
- User provides auth token with leading/trailing whitespace → Expected: trim and validate
- Lock file directory doesn't exist yet → Expected: create `tomo-home/.claude/ide/` with `0700` permissions
- User disables IDE Bridge then re-enables → Expected: regenerate lock file from stored token
- User has Tomo but not Hashi → Expected: wizard explains Hashi is required, skips gracefully
- Multiple `.lock` files in the directory → Expected: entrypoint fails fast with a clear error pointing the user at the directory — Tomo supports exactly one IDE Bridge lock file

## Success Metrics

### Key Performance Indicators

- **Adoption:** IDE Bridge is enabled in the user's tomo-install.json (boolean check)
- **Engagement:** Claude Code shows `⧉ Selected` messages in the session transcript (indicates successful connection)
- **Quality:** Zero container startup failures related to IDE Bridge (socat errors, lock file issues)
- **Business Impact:** Reduction in manual context-sharing messages from user to Claude Code

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| IDE Bridge enabled/disabled | enabled: bool, source: install/update | Track adoption |
| Lock file created | port: number | Verify setup completion |
| Socat proxy started | port: number, pid: number | Verify runtime wiring |
| begin-tomo.sh IDE status | status: active/not-configured/error | Track session-level state |

---

## Constraints and Assumptions

### Constraints

- Port defaults to 23027 (per Kokoro ADR-019 port allocation table) but is user-configurable; Kado uses 23026
- Lock file format must match Claude Code's expected schema exactly (pid, workspaceFolders, ideName, transport, authToken)
- Scripts must run on bash 3.2 (macOS default) — no `declare -A`, no bash 4+ features
- The Docker container uses `host.docker.internal` to reach the host — macOS/OrbStack specific, may not work on all Linux Docker setups
- No network ports need to be exposed in `docker run` — the proxy runs inside the container on localhost

### Assumptions

- Hashi is installed and running in Obsidian when the user launches Tomo (otherwise IDE Bridge silently fails, which is acceptable)
- The auth token is a UUID that doesn't change unless the user resets Hashi
- `host.docker.internal` resolves correctly in the Tomo container (works on macOS with OrbStack/Docker Desktop)
- Claude Code discovers the lock file at `~/.claude/ide/<port>.lock` automatically — no env vars needed
- The lock file's `workspaceFolders` field is empty — it is an IDE-only field (VS Code / JetBrains workspace scoping) with no meaning in this host/container topology
- The proxy tool (socat) is available in Debian Bookworm's apt repositories

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `host.docker.internal` not available on Linux | High | Low | Document as macOS-only for now; Linux users can use `--add-host` workaround |
| Auth token mismatch (user copies wrong token) | Medium | Medium | Wizard validates UUID format; connection failure surfaces as warning in Claude Code |
| Socat process dies during session | Medium | Low | Claude Code IDE protocol handles disconnection gracefully; user can restart container |
| Port 23027 conflict with existing service | Medium | Low | ADR-019 reserves this port for MiYo; check for conflict at startup |
| Lock file format changes in future Claude Code versions | High | Low | Lock file format is documented in Claude Code docs; monitor for breaking changes |

## Open Questions

- [x] Lock file location: host mount vs tomo-home → **Decided: tomo-home** (user decision 2026-05-27)
- [x] Port allocation: default 23027 for IDE Bridge (per ADR-019), user-configurable → **Decided 2026-05-28**
- [x] Kado port showing 23027 vs canonical 23026 → **Resolved: not a 019 bug** — the user runs several Kado instances, so this is a local configuration artifact; Kado's default remains 23026
- [x] Lock file `workspaceFolders` value → **Empty** (IDE-only field, not used in this topology) (2026-05-28)
- [ ] **How does the Tomo Claude session resolve IDE-Bridge / vault-relative file paths to Kado reads?** The vault filesystem is not mounted in the container, so a bare path (`Notes/Foo.md`) is unresolvable locally — only Kado can read it. Candidate mechanisms (need research / Hashi + Kokoro answer):
  - (a) CLAUDE.md rule — any path not starting with `/` → attempt a `kado-read` first (mirrors the existing `@`-redirection convention, which works today)
  - (b) Transport-prefixed references from Hashi — e.g. `kado:Notes/Foo.md` — so the routing is explicit in the reference itself
  - (c) Other (TBD)
  - **Cross-repo:** the same question is being raised in Hashi; the resolution must be reflected in Kokoro per the cross-component-contract rule. Feature 5 depends on this.

---

## Supporting Research

### Competitive Analysis

The Claude Code IDE protocol is implemented by:
- **VS Code** — native extension, lock file at `~/.claude/ide/<port>.lock`
- **JetBrains** — native extension, same lock file format
- **Neovim** — community plugin (claudecode.nvim, ~300 LOC), full RFC 6455 WebSocket
- **Obsidian** — community plugin (obsidian-claude-ide, 74 stars) + MiYo Hashi (in development)

All implementations use the same lock file discovery mechanism. The Docker wiring challenge is unique to Tomo — other integrations run on the same host as Claude Code.

### User Research

The problem is validated by the Tomo development workflow itself — every session where Marcus needs to reference visible Obsidian content requires manual context-sharing. The IDE Bridge eliminates this for the primary use case (editing/reviewing vault content while Claude Code runs in Docker).

### Market Data

Not applicable — this is an infrastructure feature for a single-user PKM system, not a market-facing product.
