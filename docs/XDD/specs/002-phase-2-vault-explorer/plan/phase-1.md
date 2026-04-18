---
title: "Phase 1: Scan Scripts"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Scan Scripts

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `docs/XDD/reference/tier-3/vault-exploration/structure-scan.md` — folder topology, note counts, unmapped detection
- `docs/XDD/reference/tier-3/vault-exploration/topic-extraction.md` — 5 extraction methods, performance targets
- `docs/XDD/reference/tier-2/workflows/vault-exploration.md` — overall workflow (steps 1, 5)

**Key Decisions**:
- Scripts call Kado HTTP API directly via requests/urllib
- Scripts read Kado connection from environment or config file
- Output is JSON to stdout for agent consumption
- Scripts must work inside Docker container (Python 3, PyYAML available)

**Dependencies**:
- Phase 1 (Config Foundation) complete — profiles and vault-config exist
- Kado v0.1.6 running and accessible

---

## Tasks

Establishes the data-gathering scripts that enumerate vault structure and extract topics from notes.

- [ ] **T1.1 Kado Client Library** `[activity: build-feature]`

  1. Prime: Read Kado MCP tool definitions from `docs/XDD/reference/tier-2/workflows/vault-exploration.md` and Kado plugin docs. Understand MCP StreamableHTTP transport at `host:port/mcp`.
  2. Test: Client connects to Kado; `list_directory("/")` returns vault root contents; `read_file("path")` returns note content; handles auth (Bearer token from env/config); returns structured Python dicts; raises clear errors on connection failure
  3. Implement: Create `scripts/lib/kado_client.py` — lightweight MCP client that sends JSON-RPC tool calls over HTTP. Reads KADO_URL and KADO_TOKEN from environment variables (fallback: parse `.mcp.json` in current directory). Methods: `list_dir(path, depth=None)`, `read_file(path)`, `search_by_tag(tag)`, `search(query)`
  4. Validate: Import works; `--help` or `--test` flag verifies connection
  5. Success: All Kado MCP tools accessible from Python; clear error messages on auth/connection failure

- [ ] **T1.2 Vault Structure Scanner** `[parallel: true]` `[activity: build-feature]`

  1. Prime: Read `[ref: docs/XDD/reference/tier-3/vault-exploration/structure-scan.md]`
  2. Test: Maps folder structure from vault-config concept paths; counts notes per concept; detects subdirectories (esp. Dewey numbering); identifies unmapped folders; outputs JSON with vault_structure, concepts_mapped, unmapped_folders, totals
  3. Implement: Create `scripts/vault-scan.py` — reads vault-config.yaml, calls Kado list_dir for each concept path, aggregates counts, detects unmapped top-level folders. Outputs JSON to stdout.
  4. Validate: `python3 scripts/vault-scan.py --help` works; outputs valid JSON
  5. Success: Structure scan JSON matches spec format; unmapped folders detected correctly

- [ ] **T1.3 Topic Extractor** `[parallel: true]` `[activity: build-feature]`

  1. Prime: Read `[ref: docs/XDD/reference/tier-3/vault-exploration/topic-extraction.md]`
  2. Test: Extracts topics from note content using 5 methods (title analysis, H2 headings, linked note titles, content keywords, tag-based topics); returns flat keyword list (max 30); handles binary files (filename only); locale-aware
  3. Implement: Create `scripts/topic-extract.py` — reads note content from stdin or file, applies 5 extraction methods, deduplicates, returns JSON array of topics. The LLM keyword method (method 4) is optional and skipped unless --llm flag provided (for use in MOC indexing only).
  4. Validate: `python3 scripts/topic-extract.py --help` works; test with sample markdown input
  5. Success: Topics extracted match expected patterns; performance <2s/note for MOCs

- [ ] **T1.4 Phase Validation** `[activity: validate]`

  - Kado client connects and lists vault root. vault-scan.py produces valid JSON from a vault-config. topic-extract.py extracts topics from sample markdown. All scripts have --help flags.
