---
name: garden-audit
description: Audit the knowledge garden for staleness, broken links, orphaned notes, and missing connections. Bare /garden-audit infers the mode; add a token — configure to manage exclusions, suggest to compute candidate targets for findings you ticked, or stats for a read-only overview.
argument-hint: "optional: configure | suggest | stats"
---
# /garden-audit
# version: 0.4.0

Audit the knowledge garden for staleness, broken links, orphaned notes, and
missing connections. Produces a reviewable audit report in your inbox folder.

## STRICT — How to Run This Command

| Step | Agent | How to run |
|------|-------|------------|
| All steps | `garden-auditor` | **Impersonate** — read `.claude/agents/garden-auditor.md` and execute its Workflow steps in your context. Do NOT dispatch via the `Agent` tool. |

Authoritative spec: `.claude/agents/garden-auditor.md`.

## Usage

```
/garden-audit            # infers mode: first-run → wizard; a report with ticked Suggest boxes → asks; else fresh scan
/garden-audit audit      # force a fresh scan (skip inference)
/garden-audit configure  # manage exclusions (the exclusion wizard)
/garden-audit suggest    # compute candidate targets for findings you ticked "Suggest targets"
/garden-audit stats      # read-only overview: what's open, excluded, on pushback (relayed to chat, no vault write)
```

Bare `/garden-audit` infers the mode (see the agent's Step 1 precedence). Pass the invocation
tokens through to the `garden-auditor` agent as-is; the legacy `--configure` / `--suggest`
flags are still accepted as aliases.

# STRICT — IMPERSONATE, never dispatch. Why: dispatched subagents cannot use the Agent tool.
