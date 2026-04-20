# /explore-vault
# version: 0.2.0

Scan your Obsidian vault to discover structure, frontmatter patterns, tags, and MOC hierarchy.
Builds the discovery cache that powers Tomo's PKM intelligence.

## Usage

`/explore-vault` — Full scan with user confirmation (first run) or silent cache rebuild (subsequent)
`/explore-vault --confirm` — Re-run all detection with user confirmation

## What This Does

1. Connects to Kado MCP
2. Scans vault folder structure
3. Detects frontmatter patterns, tag taxonomy, relationship markers, callout usage
4. Indexes all MOCs and builds topic tree
5. Generates discovery-cache.yaml

You will be asked to confirm each detection step. Your vault is never modified — only Tomo's config files are updated.

## Agent

This command delegates to the `vault-explorer` agent.
