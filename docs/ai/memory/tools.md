# Tools — Tomo
<!-- CI, build pipeline, API clients, local dev setup. Updated: 2026-05-08 -->
<!-- What goes here: commands that are non-obvious, tool quirks, CI gotchas, env var names -->
<!-- What does NOT go here: domain rules (→ domain.md), code style (→ general.md) -->

<!-- 2026-05-29 -->

## Regex-extraction harnesses need a non-empty guard — silent false greens otherwise

When a test harness extracts a code block via regex (e.g., section between comment delimiters in a shell script) and inlines it into a subprocess, tests that assert "nothing happened" pass trivially when the extraction returns `""`. The block is absent → harness runs an empty string → no socat call, no error → test passes. Regression is invisible. Fix: assert the extracted block is non-empty in the **shared helper** (one assert covers all callers). Discovered during 019 T2.2 entrypoint proxy tests 2026-05-29.

<!-- 2026-05-08 -->

## Code-quality reviewer diff range — file-scoped filtering for parallel implementers

When N implementers run in parallel on the same branch and each touches different files, git produces clean linear history but the BASE..HEAD ranges they report are **stale relative to sibling commits**. Each implementer's range covers only their own commits when measured against `main`, but the broader span of the branch crosses task boundaries. Implications for `/tcs-workflow:code-quality-reviewer` dispatch:

- **Don't pass the broad delta** (e.g., `f90551d..12ee612` covering all T4.2 fix-passes) — it pulls in a sibling task's commit (`aa4e176` was a T4.3 commit inside the T4.2 timespan), and the reviewer flags it as "out-of-scope" / "missing review", producing a procedural false-positive FAIL.
- **Pass diff ranges scoped to the specific task's commits only** — use `git log --oneline -- <file_path>` to filter, OR build the range from the implementer-reported commit hashes that touch only the relevant files, OR explicitly tell the reviewer in the prompt: "ignore commit `<sha>` — that's a sibling task already reviewed separately".

Confirmed during F-43 Phase 4 parallel implementation 2026-05-08 (T4.1 + T4.2 + T4.3 in flight simultaneously).

<!-- 2026-06-03 -->

## A new `dot_claude/` subdir must be wired in BOTH install-tomo.sh AND update-tomo.sh

Both installers sync an **explicit directory allowlist** — there is no generic "copy everything under `dot_claude/`" step. Adding a new runtime subdir (e.g. `output-styles/`) requires wiring it in *both* scripts or it silently never reaches the container:

- `install-tomo.sh`: a `mkdir -p "$INSTANCE_PATH/.claude/<dir>"` in the mkdir block **plus** a guarded `cp "$TOMO_SOURCE/dot_claude/<dir>/"*.<ext>` in the copy block.
- `update-tomo.sh`: an `add_versioned` loop in the pre-flight scan, **plus** a matching `print_section_plan "<section>"` **and** `execute_section "<section>"` entry. The synced file needs a `# version:` comment so the version comparator can track it.

`update-tomo`'s `execute_one` already runs `ensure_dir "$(dirname "$dst")"`, so existing instances get the new directory created automatically on update — no separate mkdir needed there. Discovered adding the `tomo-companion` output style 2026-06-03 (PR #11).

<!-- 2026-05-01 -->

## Subagent: impersonation vs Agent-tool dispatch (~60% token diff)

When a slash command invokes an orchestrator agent, the parent has two valid interpretations: **impersonation** (parent reads the agent spec and follows it directly inside its own context) or **dispatch** (parent spawns the agent via the Agent tool). Token cost differs by ~60% — impersonation reuses parent context; dispatch creates a fresh subagent and pays full cache-read on each hop. If the orchestrator fans out further subagents, only impersonation works (nested Agent dispatches fail). Lock the intended reading explicitly in the slash-command spec with STRICT/MUST/NEVER wording.

## Model floor: `sonnet` minimum for STRICT-orchestration agents

`haiku` is not strong enough to follow STRICT/NEVER format rules in orchestrator agents. Observed 2026-05-01: instruction-builder pinned to haiku silently rendered Pass 2 itself instead of dispatching `instruction-render.py` (twice in one session). Pin `sonnet` minimum for any agent whose contract requires literal-format-following or "NEVER do X" discipline. Document the model choice in the agent's frontmatter.

## Parent model inheritance via `.claude/settings.json` `model:` field

`"model": "sonnet"` in `.claude/settings.json` controls the **parent session** model — including the main-thread of slash commands that orchestrate subagents. This is the right knob to pin Pass 1 main-thread cost (today 7.14M tokens on opus → expected <2.5M on sonnet). Pinned 2026-05-01; effect on `/inbox` Pass 1 token consumption to be measured on next run.

## Resetting `tomo-tmp/` between test runs

Use **`scripts/reset-tomo-tmp.sh`** instead of manual `rm -rf`. Five modes matching the routing-plan action vocabulary:

| Mode | Use when | Removes |
|------|----------|---------|
| `--pass2` (default) | Iterating on `suggestions.md` edits + Pass 2 | `parsed-suggestions.json`, `rendered/` |
| `--fan-resolve` | Re-running fan-resolve only | `suggestions-fan*` files |
| `--pass1` | Changing analyst behavior, skill edits | All Pass-1 + Pass-2 outputs (keeps `voice/`) |
| `--transcribe` | Re-running voice transcription | `voice/summary.json` |
| `--all` | True zero state needed | Everything in `tomo-tmp/` |

Quick reference:
```bash
bash scripts/reset-tomo-tmp.sh                  # default --pass2
bash scripts/reset-tomo-tmp.sh --pass1
bash scripts/reset-tomo-tmp.sh --all
bash scripts/reset-tomo-tmp.sh --dry-run --pass1
```

## Accessing Kado from the host (outside tomo-instance)

Kado runs inside Obsidian, listening on `127.0.0.1:<port>`. The port is whatever the Kado plugin is configured to use (the documented default is `23026`, but instances may run on other ports) — **read it from `tomo-instance/.mcp.json`, don't hardcode it**. The same server is reached as `127.0.0.1:<port>` from the host and `host.docker.internal:<port>` from inside the Docker container — only the hostname differs, the port is identical. A bearer token is required.

```bash
KADO_URL=$(python3 -c "import json; cfg=json.load(open('tomo-instance/.mcp.json')); print(cfg['mcpServers']['kado']['url'].replace('host.docker.internal','127.0.0.1'))") \
KADO_TOKEN=$(python3 -c "import json; cfg=json.load(open('tomo-instance/.mcp.json')); print(cfg['mcpServers']['kado']['headers']['Authorization'].replace('Bearer ',''))") \
python3 <script.py>
```

Or in Python:
```python
import json, sys
sys.path.insert(0, "tomo/scripts")
from lib.kado_client import _extract_from_mcp_json, KadoClient

url, token = _extract_from_mcp_json(json.load(open("tomo-instance/.mcp.json")))
url = url.replace("host.docker.internal", "127.0.0.1")  # Docker→host rewrite
client = KadoClient(base_url=url, token=token)
```

Key differences from inside Docker: hostname is `127.0.0.1` (not `host.docker.internal`) — the port is the same on both sides, read from `.mcp.json`; and `.mcp.json` is at `tomo-instance/.mcp.json` (not `.mcp.json` in cwd).

<!-- 2026-05-31 -->

## Hashi IDE Bridge — connection diagnosis + auto-connect (XDD 019 live-test)

**Diagnose failures via the IDE log, not process checks.** The authoritative log is `tomo-home/.cache/claude-cli-nodejs/<encoded-project>/mcp-logs-ide/*.jsonl` inside the instance. A failed connect appears there as a structured error — e.g. Zod `invalid_type: serverInfo.version expected string, received undefined` means the connection reached the server and the **Hashi-side handshake** is non-conformant (missing `serverInfo.version`), NOT a transport/lock/token problem. Do **not** diagnose with container process checks: the minimal container shell has no `pgrep` and no `/dev/tcp`, so `pgrep -af socat` and `: </dev/tcp/...` return misleading "not found" errors. Read the `mcp-logs-ide` jsonl.

**Auto-connect needs a signal — a lock file alone is the target, not the trigger.** Claude Code does NOT auto-connect on startup just because `~/.claude/ide/<port>.lock` exists. Mechanisms (documented): env var **`CLAUDE_CODE_AUTO_CONNECT_IDE=true`** (highest precedence), the `claude --ide` flag, or launching from an IDE integrated terminal. Running `/ide` once writes `autoConnectIde: true` into `~/.claude.json` (app state) — that is **NOT** a `settings.json` field; never put `autoConnectIde` in settings.json. Tomo's `docker/entrypoint.sh` (0.4.0+) exports `CLAUDE_CODE_AUTO_CONNECT_IDE=true` in the single-lock branch (kept out of the `unset` list so it survives into `exec "$@"`), so the container auto-connects without manual `/ide`.

**IDE lock fields:** `authToken` is `hashi_<uuid>` (the `hashi_` prefix is part of the token — store verbatim). `workspaceFolders` carries the **container instance path** (`begin-tomo` mounts the instance at the same path host+container via `-v $INSTANCE_PATH:$INSTANCE_PATH` and `-w $INSTANCE_PATH`), not empty — Claude Code uses it to anchor the workspace. `IDE_BRIDGE_ENABLED` is host-side only (not passed into the container); the lock file is the sole in-container signal that the bridge is active.

<!-- 2026-06-01 -->

## Before assuming a bug is new, check unmerged branches for an orphaned fix

`git branch -a --no-merged HEAD` then `git log -1 --format='%s' <branch>` lists work that never landed. In spec-020 a real fix (`87262c1` "quote tilde in vault-path case pattern") plus its regression test sat on `fix/install-vault-path-tilde-case` — pushed to origin but **never merged** into `feat/020` — so a long-fixed bug resurfaced ("we fixed it but lost it somewhere"). Recovery: `git checkout <branch> -- <test-file>` for clean file adds; re-apply the code hunk manually when surrounding context has diverged. The same `--no-merged` scan also catches **reserved-ID collisions**: an unmerged branch (`docs/backlog-d10-documentation-refresh`) already owned backlog `D-10`, so a newly-added `D-10` had to be renumbered to `D-11`. Lesson: orphaned branches strand both fixes AND reserved IDs — scan before declaring a bug new or claiming the next free backlog/spec ID.

<!-- 2026-06-06 -->

## `update-tomo.sh` retires source-deleted scripts only via a hardcoded list

Deleting a runtime `tomo/scripts/*.py` from source does NOT remove it from existing instances on `update-tomo --yolo`: the sync copies/versions present files but only retires (deletes) instance scripts named in the hardcoded `RETIRED_SCRIPTS` array (`scripts/update-tomo.sh` ~:454). Miss the entry → the orphan persists in every instance after every update. When you delete a runtime script, add its basename to `RETIRED_SCRIPTS` in the same change (021 T3.3 deleted `atomic-note-indexer.py` but missed the array; caught during instance cleanup, fixed in `99d8412`). Same mechanism + `RETIRED_SCRIPT_TESTS` for tests.
