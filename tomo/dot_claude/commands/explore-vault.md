---
name: explore-vault
description: Scan your Obsidian vault to discover structure, tags, relationships, callouts, and MOC hierarchy. Builds the discovery cache that powers Tomo's PKM intelligence. Impersonates the vault-explorer agent.
argument-hint: "optional: --confirm to force re-detection"
---
# /explore-vault
# version: 0.3.3

Scan your Obsidian vault to discover structure, tags, relationships, callouts, and MOC hierarchy.
Builds the discovery cache that powers Tomo's PKM intelligence.

## Usage

`/explore-vault` — Full scan with user confirmation (first run) or silent cache rebuild (subsequent)
`/explore-vault --confirm` — Re-run all detection with user confirmation

## STRICT — How to Run This Command

| Step | Agent | How to run |
|------|-------|------------|
| All steps | `vault-explorer` | **Impersonate** — read `agents/vault-explorer.md` and execute its workflow in your context. Do NOT dispatch via the `Agent` tool. |

Why impersonate: this command runs once per vault (or on `--confirm`),
uses `AskUserQuestion` repeatedly, and has no further subagent fan-out
to coordinate. Impersonation keeps the user-interaction loop in the
main session where it's most reliable.

## What This Does

1. Connects to Kado MCP
2. Scans vault folder structure
3. Detects tag taxonomy, relationship markers, callout usage (frontmatter is profile-driven)
4. Indexes all MOCs and builds topic tree
5. Generates discovery-cache.yaml

You will be asked to confirm each detection step. Your vault is never modified — only Tomo's config files are updated.

