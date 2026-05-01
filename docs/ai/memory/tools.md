# Tools — Tomo
<!-- CI, build pipeline, API clients, local dev setup. Updated: 2026-05-01 -->
<!-- What goes here: commands that are non-obvious, tool quirks, CI gotchas, env var names -->
<!-- What does NOT go here: domain rules (→ domain.md), code style (→ general.md) -->

<!-- 2026-05-01 -->

## Subagent: impersonation vs Agent-tool dispatch (~60% token diff)

When a slash command invokes an orchestrator agent, the parent has two valid interpretations: **impersonation** (parent reads the agent spec and follows it directly inside its own context) or **dispatch** (parent spawns the agent via the Agent tool). Token cost differs by ~60% — impersonation reuses parent context; dispatch creates a fresh subagent and pays full cache-read on each hop. If the orchestrator fans out further subagents, only impersonation works (nested Agent dispatches fail). Lock the intended reading explicitly in the slash-command spec with STRICT/MUST/NEVER wording.

## Model floor: `sonnet` minimum for STRICT-orchestration agents

`haiku` is not strong enough to follow STRICT/NEVER format rules in orchestrator agents. Observed 2026-05-01: instruction-builder pinned to haiku silently rendered Pass 2 itself instead of dispatching `instruction-render.py` (twice in one session). Pin `sonnet` minimum for any agent whose contract requires literal-format-following or "NEVER do X" discipline. Document the model choice in the agent's frontmatter.

## Parent model inheritance via `.claude/settings.json` `model:` field

`"model": "sonnet"` in `.claude/settings.json` controls the **parent session** model — including the main-thread of slash commands that orchestrate subagents. This is the right knob to pin Pass 1 main-thread cost (today 7.14M tokens on opus → expected <2.5M on sonnet). Pinned 2026-05-01; effect on `/inbox` Pass 1 token consumption to be measured on next run.

## Resetting `tomo-tmp/` between test runs

Use **`scripts/reset-tomo-tmp.sh`** instead of manual `rm -rf` of subsets. Three modes plus dry-run:

| Mode | Use when | Removes |
|------|----------|---------|
| `--pass2` (default) | Iterating on `suggestions.md` edits + Pass 2 testing | `parsed-suggestions.json`, `rendered/` |
| `--pass1` | Changing analyst behavior, skill edits, Pass-1 affecting config | All Pass-1 + Pass-2 outputs (keeps `archive/` + `voice/`) |
| `--all` | True zero state needed | Everything in `tomo-tmp/` |

Quick reference:
```bash
bash scripts/reset-tomo-tmp.sh                  # default --pass2
bash scripts/reset-tomo-tmp.sh --pass1
bash scripts/reset-tomo-tmp.sh --all
bash scripts/reset-tomo-tmp.sh --dry-run --pass1   # preview
bash scripts/reset-tomo-tmp.sh --instance ./other-instance/tomo-tmp
```

Auto-resolves the instance path from `tomo-install.json`'s `install_path` field; falls back to `./tomo-instance/tomo-tmp`. Refuses to operate if the resolved directory does not exist (exit 1).

**Not the same as `cleanup-tomo.sh`:** that script tears down the whole instance for re-install testing. `reset-tomo-tmp.sh` only touches the working-state directory.

Full doc with the per-mode comparison table: `docs/troubleshooting.md` § "Resetting Working State Between Test Runs".
