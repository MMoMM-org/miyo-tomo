# Tools — Tomo
<!-- CI, build pipeline, API clients, local dev setup. Updated: 2026-05-01 -->
<!-- What goes here: commands that are non-obvious, tool quirks, CI gotchas, env var names -->
<!-- What does NOT go here: domain rules (→ domain.md), code style (→ general.md) -->

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
