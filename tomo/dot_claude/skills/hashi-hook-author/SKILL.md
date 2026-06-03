---
name: hashi-hook-author
description: Use when the user wants to create, author, or write a Hashi hook, add a before/after hook for a Hashi action, or customize what Hashi does when it applies an instruction set. Triggers on "Hashi hook", "before-hook", "after-hook", ".tomo-hashi/hooks", or customizing Hashi execution behavior.
user-invocable: true
model: sonnet
allowed-tools: Read, Edit, Write, Bash, AskUserQuestion, mcp__kado__kado-write
---
# Hashi Hook Author
# version: 0.1.0

Guide the user through authoring one Hashi `.cjs` hook, classify its risk, and deliver it plus a handoff doc to the inbox. Run the steps in order. Stop only where a step says stop.

Valid phases: `before`, `after`.
Valid action-kinds: `create_moc`, `move_note`, `link_to_moc`, `add_relationship`, `update_tracker`, `update_log_entry`, `update_log_link`, `delete_source`, `skip`.

## 1. Disclaimer + acknowledgement

Show the user this disclaimer verbatim, then use AskUserQuestion to get acknowledgement. If they decline, stop.

> ⚠️ Hashi hooks run **unsandboxed on your host** with full vault, filesystem, and network access — the same privilege as the Hashi plugin itself. This skill drafts hook code, but **you** are responsible for reviewing it, testing it, and any consequences of running it. Tomo provides no guarantee and assumes no liability.

AskUserQuestion — header "Disclaimer": option "I understand, continue" / option "Cancel". On Cancel, stop.

## 2. Resolve the hooks directory

Read `config/vault-config.yaml`. Look for `extensions.hashi_hooks_path`.

- If present: confirm it with the user via AskUserQuestion (header "Hooks dir"): "Use `<path>`?" → "Yes" / "Change it".
- If absent or the user picks "Change it": AskUserQuestion for the path (default `.tomo-hashi/hooks`).

Persist the resolved path with the Edit tool — add or update `hashi_hooks_path:` under an `extensions:` block in `config/vault-config.yaml`. Surgical Edit only; never rewrite the file. If no `extensions:` block exists, add one at the top level.

## 3. Probe Kado access

Write this to `tomo-tmp/probe_hooks.py`, substituting the resolved dir, then run `python3 tomo-tmp/probe_hooks.py`:

```python
import sys, json
sys.path.insert(0, 'scripts')
from lib.kado_client import KadoClient, KadoError, KadoConnectionError
try:
    client = KadoClient()
    items = client.list_dir('<hooks_dir>', depth=1)
    print(json.dumps({"reachable": True, "items": [i["path"] for i in items]}))
except (KadoError, KadoConnectionError) as e:
    print(json.dumps({"reachable": False, "error": str(e)}))
```

- `reachable: true` → tell the user the dir is visible; list any existing `before-*.cjs` / `after-*.cjs` files. Record this list to warn about clobbering in step 7.
- `reachable: false` → tell the user Kado could not see the dir; continue anyway and note "access not verified" in the handoff doc.

## 4. Guided design

Print the 9 valid action-kinds. Then call AskUserQuestion with two questions:
- header "Phase": `before` (runs before the action; errors abort it) / `after` (runs after the action commits).
- header "Action": offer `move_note`, `create_moc`, `link_to_moc`, `add_relationship` as options; the remaining five are reachable via "Other".

Validate the chosen action-kind against the 9 valid values; if invalid, re-ask.

Then ask the user, in plain text, what the hook should do. Capture the intended behavior.

## 5. Generate the hook

Write the hook to `tomo-tmp/<phase>-<action>.cjs`. Required shape:

```js
module.exports = async (ctx) => {
  const { action, app, logger } = ctx;
  // ... behavior ...
  return { info: [], warnings: [], errors: [] };
};
```

Rules for the generated code:
- Prefer the Obsidian API only: `app.vault`, `app.fileManager.processFrontMatter`, `app.metadataCache`.
- A `before` hook returning `{ errors: [...] }` aborts the action; an `after` hook runs after the vault change is committed.
- Read `action` fields for the chosen kind rather than hardcoding paths.
- Do not add `child_process`, `node:fs` writes, network calls, `eval`, or `process.env` unless the user explicitly insists.

## 6. Classify

Run `python3 scripts/hashi-hook-scan.py --file tomo-tmp/<phase>-<action>.cjs` and parse the JSON `{tier, mass_change, findings}`.

- `tier` green AND `mass_change` false → proceed to step 7.
- `tier` yellow OR `mass_change` true → proceed, and include a loud warning block in the handoff doc that lists each finding and, if `mass_change`, states the hook can modify many notes in one run.
- `tier` red → show the user the findings, state clearly that running this kind of code through a Tomo-generated hook is **not advisable**, and recommend they write and review it by hand instead. Then AskUserQuestion (header "Red hook"): "Generate anyway" / "Stop". On "Stop", stop and write nothing.

## 7. Emit to the inbox

Read `concepts.inbox` from `config/vault-config.yaml` for the inbox path. Build a timestamp `YYYY-MM-DD_HHMM` (use `date +%Y-%m-%d_%H%M`).

If a file for this `<phase>-<action>` already exists in the hooks dir (from step 3), state in the handoff doc that moving this hook will overwrite the existing one.

**a. Write the hook file:**
```bash
python3 scripts/kado-write-file.py --local tomo-tmp/<phase>-<action>.cjs --vault "<inbox>/<ts>_<phase>-<action>.cjs"
```

**b. Write the handoff doc** via `mcp__kado__kado-write` (operation `note`) at `<inbox>/<ts>_hashi-hook-handoff.md`. The body MUST open with these three blocks, in this exact order, before anything else:
1. `> 🛡️ **Back up your vault now** — before you move this hook into place.`
2. `> 🛡️ **Back up your vault again** — before the next time you run Hashi with this hook active.`
3. The liability disclaimer from step 1.

Then include:
- What the hook does (the user's intended behavior, in one or two sentences).
- The exact target: move the file to `<hooks_dir>/<phase>-<action>.cjs` (Hashi loads `<phase>-<action>.cjs` only).
- How to enable it: set the Hashi hook policy to `Ask` (prompts on first run) or `Enabled`; `Disabled` blocks all hooks.
- The scan result: tier, `mass_change`, and the full findings list (plus the warning block if yellow/red/mass-change).
- A manual review checklist: read the code, confirm it only touches what you expect, dry-run on a backup vault, watch the Hashi run log.

## 8. Report

Tell the user both files are in the inbox (give the two filenames) and summarize the scan tier and whether `mass_change` was flagged.
