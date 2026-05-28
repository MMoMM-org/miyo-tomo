---
title: "Phase 3: Launch & Status Surfaces"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Launch & Status Surfaces

The user-visible layer: the launch banner reports bridge status + a host-side reachability probe and ships the new socat image (drift rebuild); the statusline gains a `橋:<port>` Hashi indicator and reformats Kado to `門:<port>`; and `CLAUDE.md` gets the vault-path routing rule so Claude reads bridge file paths through Kado. All three tasks touch **different files** and are independent — run them in parallel.

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/Feature 5 (Vault Path Resolution); AC1-AC3]`
- `[ref: PRD/Feature 6 (Launch Banner Status); AC1-AC3]`
- `[ref: PRD/Feature 7 (Statusline Connection Indicators); AC1-AC3]`
- `[ref: SDD/Statusline indicator format; lines: 199-208]`
- `[ref: SDD/ADR-3 reachability probe; lines: 286-290]`
- `[ref: SDD/ADR-5 vault-path routing; lines: 295-298]`
- `[ref: SDD/Feature 5 — CLAUDE.md routing rule; lines: 132-134]`

**Key Decisions**:
- **ADR-3**: reachability = TCP-connect to `127.0.0.1:<port>`. Host-side (`begin-tomo.sh`) hits Hashi directly; container-side (statusline) hits it **through the socat proxy**. Per-probe timeout ≤ 3s; reuse the existing 60s statusline cache.
- **ADR-1 drift**: `begin-tomo.sh` rebuilds images built **before** socat existed, via an image label (one-shot migration flag, not a voice-style on/off dimension).
- **ADR-5**: namespace routing rule in `CLAUDE.md.template`; no protocol prefix; fails closed (vault unmounted).
- **CON-6**: do not regress the voice banner line or the Kado statusline semantics (connectivity + Tags probe). Color (green/red/yellow) is **retained**, not replaced by symbols (F7-AC3).

**Dependencies**: Phase 1 (config `.ide_bridge` for the host banner; lock file for the statusline/entrypoint) and Phase 2 (the proxy the statusline probes through). The three tasks are mutually independent (separate files).

**Runtime source of the port** (carries the Phase-1 deviation): host-side `begin-tomo.sh` reads `.ide_bridge.{enabled,port}` from `tomo-install.json` directly. Container-side `tomo-statusline.sh` reads the **lock file** at `$HOME/.claude/ide/*.lock` (bind-mounted) — no instance mirror exists. "Configured" for the statusline == a lock file is present.

---

## Tasks

- [ ] **T3.1 Launch banner + reachability probe + socat drift rebuild (`begin-tomo.sh.template`)** `[activity: devops]` `[parallel: true]`

  1. **Prime**: Read `scripts/lib/begin-tomo.sh.template` — the voice drift-label read + `build_image`/rebuild branch (lines ~236-314), the banner Voice line (lines ~371-384), and the `set +e` guard pattern around `docker image inspect` (lines ~289-292, the bash 3.2 errexit trap — memory `feedback_bash32_set_e_cmdsubst_silent_exit`). Read `[ref: SDD/ADR-3; lines: 286-290]`.
  2. **Test** (`tests/ide_bridge/test_begin_tomo_ide.py` — render the template with `sed` substitutions into a tmp script, stub `docker`/`jq` on `PATH`, drive the relevant snippets):
     - configured (`.ide_bridge.enabled=true`) + reachable port (stub a listener / stub the probe true) → banner shows "IDE: bridge active" `[ref: PRD/F6-AC1]`
     - not configured (`.ide_bridge` absent or `enabled=false`) → banner shows "IDE: not configured" (dimmed) `[ref: PRD/F6-AC2]`
     - configured + unreachable (probe false) → non-blocking warning printed, launch continues (exit not forced) `[ref: PRD/F6-AC3]`
     - image label missing/empty (pre-socat image) → rebuild branch taken `[ref: PRD/F3-AC2]`
     - probe respects a ≤3s bound and never blocks the launch (ADR-3)
  3. **Implement** (`# version:` bump 0.11.0 → 0.12.0):
     - read `.ide_bridge.enabled`/`.ide_bridge.port` from `$CONFIG_FILE` (host `tomo-install.json`) with `// false`/`// 23027` fallbacks, single jq call where practical
     - **drift label**: add `--label "tomo.has_socat=1"` in `build_image`; read it with the same `set +e`-guarded `docker image inspect` approach already used for `tomo.voice_enabled`; when the label is absent/empty on an existing image, take a one-time rebuild branch with a distinct "first run with socat-labeled image" message (mirrors the existing pre-voice-label migration message)
     - **reachability probe** (host-side, ADR-3): a `/dev/tcp/127.0.0.1/<port>` connect wrapped so it can't hang or trip `set -e` (background + `timeout`, or a small `nc -z`-style helper); ≤3s
     - **banner line**: a single "IDE:" line, color-coded like the Voice line — `bridge active` (green) when configured+reachable, `bridge active (Hashi unreachable)` warning (yellow, non-blocking) when configured+unreachable, `not configured` (dim) otherwise
  4. **Validate**: `pytest tests/ide_bridge/test_begin_tomo_ide.py -v`; `/bin/bash -n` on the rendered template (and `scripts/install-tomo.sh` still renders it without error); voice banner + drift rebuild unchanged (CON-6).
  5. **Success**: banner reflects configured/unreachable/not-configured states; pre-socat images rebuild; unreachable Hashi never blocks launch `[ref: PRD/F6-AC1, F6-AC2, F6-AC3, F3-AC2]`.

- [ ] **T3.2 Statusline `門:<port>` Kado reformat + `橋:<port>` Hashi indicator (`tomo-statusline.sh`)** `[activity: backend-shell]` `[parallel: true]`

  1. **Prime**: Read `tomo/scripts/tomo-statusline.sh` — the cache mechanism (lines ~47-64), `kado_check` and the Kado URL/port parse (lines ~66-170), and the render `case` block (lines ~181-196). Read `[ref: SDD/Statusline indicator format; lines: 199-208]`. The script runs **inside the container** (cwd = instance, `$HOME=/home/coder`); the lock file is at `$HOME/.claude/ide/*.lock`.
  2. **Test** (`tests/ide_bridge/test_statusline_render.py` — feed JSON on stdin, stub the probes, assert the rendered line; mirror how the existing statusline is exercised):
     - Kado renders as `門:<port> ✓` (green), `門:<port> ✗` (red), `門:<port> ✓ Tags ✗` (yellow), `門:<port> ?` (yellow, no_config) — **port parsed from `.mcp.json` URL** `[ref: PRD/F7-AC1]`
     - Hashi configured (lock file present) + reachable (probe true) → `橋:<port> ✓` (green); unreachable → `橋:<port> ✗` (red) `[ref: PRD/F7-AC2]`
     - Hashi not configured (no lock file) → `橋:<port> ?` (yellow); **no Tags sub-state** ever appears for Hashi `[ref: PRD/F7-AC2]`
     - color codes retained for all states (assert ANSI present, not symbol-only) `[ref: PRD/F7-AC3]`
     - instance label `友 <name>` rendering unchanged (CON-6)
  3. **Implement** (`# version:` bump 0.4.0 → 0.5.0):
     - reformat the Kado render `case` to `門:<port>` (derive `<port>` from the Kado URL already parsed in `kado_check`; thread the port out to the render)
     - add a `hashi_check` (cached, ≤3s timeout, reusing/extending the 60s cache — either a second cache file or a combined cached payload): "configured" iff a single `$HOME/.claude/ide/*.lock` exists; read `<port>` from the lock filename; TCP-probe `127.0.0.1:<port>` via `timeout 3 bash -c ':</dev/tcp/127.0.0.1/<port>'`; map to `ok`/`unreachable`/`no_config`
     - add a `橋:<port>` render `case` (green/red/yellow; no Tags state). Keep the statusline crash-proof (no `set -e`/`set -u`, per the file's existing contract)
  4. **Validate**: `pytest tests/ide_bridge/test_statusline_render.py -v`; `/bin/bash -n tomo/scripts/tomo-statusline.sh`; manual stdin smoke renders both indicators. Confirm probe timeout can't stall rendering.
  5. **Success**: Kado shows `門:<port>` with its existing 4 states; Hashi shows `橋:<port>` with 3 states, no Tags; color retained `[ref: PRD/F7-AC1, F7-AC2, F7-AC3]`.

- [ ] **T3.3 Vault-path routing rule in `CLAUDE.md.template` (Feature 5 / ADR-5)** `[activity: docs-prompt]` `[parallel: true]`

  1. **Prime**: Read `tomo/CLAUDE.md.template` (the `## Rules` and `## MCP` sections). Read `[ref: SDD/ADR-5; lines: 295-298]` and `[ref: SDD/Feature 5; lines: 132-134]` and PRD Feature 5 ACs. Note the runtime-file discipline (CLAUDE.md root rule): this is an LLM-loaded runtime file — write imperatives + the routing rule, **not** rationale; rationale belongs in `docs/tomo/CLAUDE.md.template.md` (the WHY layer).
  2. **Test**: a content/contract assertion (no runtime behavior to unit-test — prompt-level steering). Add a small check (in `tests/ide_bridge/`, or a doc-lint assertion) that the rendered `CLAUDE.md` (post-`sed`) contains the routing rule with all four namespace cases: bridge active file, `[[wikilinks]]`, `@`-mentions, `kado-search` results → `kado-read` first; container-local → local `Read`; ambiguous bare path → `kado-read` first then `Read` fallback on not-found/denied; true vault path that isn't local → fails closed. Verify `{{KADO_*}}` placeholders still render.
  3. **Implement**: add a concise routing rule to `tomo/CLAUDE.md.template` (a new sub-section under `## Rules` or `## MCP`). State the namespace rule as imperatives: vault-note paths are read via `kado-read`; the vault is **not** mounted in the container, so never use local `Read`/filesystem for a vault path; local `Read` is only for container-local working files; on an ambiguous bare relative path try `kado-read` first and fall back to local `Read` only on a Kado not-found/denied; a true vault path that is not found locally is an error (fail closed). No protocol prefix — Hashi emits plain vault-relative paths. Keep it short; bump the template's version comment if it carries one (it does not currently — check and add the project's standard header only if the file already uses one). Capture the WHY (ADR-5 rationale, mechanism-(b) reserve) in `docs/tomo/CLAUDE.md.template.md` if that mirror exists or create it (CLAUDE.md root rule — WHY-persistence layer).
  4. **Validate**: render via the install `sed` pipeline into a tmp file; confirm placeholders resolve and the rule reads cleanly; `pytest` content assertion green.
  5. **Success**: the routing rule covers selection-needs-no-read, active-file→`kado-read`, wikilink/@-mention/search-result→`kado-read`-first, and the fail-closed fallback `[ref: PRD/F5-AC1, F5-AC2, F5-AC3]`.

- [ ] **T3.4 Phase Validation** `[activity: validate]`

  `pytest tests/ide_bridge/ -v` and full `pytest tests/` (CON-6). `/bin/bash -n` on `begin-tomo.sh.template` (rendered) and `tomo-statusline.sh`. Confirm version bumps on `begin-tomo.sh.template` and `tomo-statusline.sh`. Render `CLAUDE.md.template` and eyeball the routing rule. Verify against PRD Features 5/6/7 and SDD ADR-3/ADR-5 + the statusline format block.
