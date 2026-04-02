# Kado Connection Configuration
# version: 0.1.0
# This file is filled with real values by the install script.

## Connection

- Host: {{KADO_HOST}}
- Port: {{KADO_PORT}}
- Protocol: {{KADO_PROTOCOL}}
- Bearer token: configured in .mcp.json (not stored here)

## Permissions

Kado enforces its own permission model. Tomo accesses the vault through these MCP tools:
- `read_file` — read note content
- `write_file` — create or update notes
- `list_directory` — browse folder structure
- `search` — full-text vault search
