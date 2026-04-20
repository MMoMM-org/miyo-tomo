# XDD 010 Spikes — File Picker

Three live-test tasks that answer Phase-1 unknowns about Claude Code's
`fileSuggestion` API. Findings feed back into Phase 2 handler design.

Record all observations in `findings.md` (this directory).

---

## Spike T1.1 — Exit-code + stdout shape behaviour

**Question**: What does Claude Code do with non-zero exit codes, empty
stdout, and non-path stdout lines?

**Workflow** — query-routed, one install, no per-case script edits:

1. From the host, install the spike into the Tomo instance:
   ```bash
   bash scripts/spikes/xdd-010/prep-t1-1.sh
   ```
   This backs up the real `file-suggestion.sh` and installs the spike.

2. Restart your Tomo session (`bash begin-tomo.sh`).

3. In the Tomo prompt, type each case and observe:
   - `@CASE_A` — exit 0 + three valid paths
   - `@CASE_B` — exit 0 + empty stdout
   - `@CASE_C` — exit 1 + valid paths
   - `@CASE_D` — exit 0 + non-path text
   - `@CASE_E` — exit 0 + mixed valid + non-path (synthetic `... + N more` line)
   - any other query → `SPIKE-ACTIVE` hint, so you know the spike is live

4. Record observations in `findings.md`.

5. When done, restore the real picker:
   ```bash
   bash scripts/spikes/xdd-010/restore-picker.sh
   ```
   Restart Tomo.

---

## Spike T1.2 — Active-note suffix marker

**Question**: If we emit `path/to/note.md (active)`, does Claude Code:
- Show the suffix in the picker UI?
- Include the suffix on insertion into the prompt?
- Resolve the file content despite the suffix? (most important)

**Workflow**: mirror of T1.1 with `spike-suffix-marker.sh` as the
installed script. A `prep-t1-2.sh` will be added when T1.1 is closed.
For now: run T1.1 first and capture findings.

---

## Spike T1.3 — kado-open-notes path format

**Question**: What format does `notes[].path` come back in? Vault-relative?
Absolute? CLAUDE_PROJECT_DIR-relative?

**Workflow**: no picker swap needed. Direct Kado curl from inside the
Tomo container:

```bash
# Inside the running Tomo container:
KADO_ENDPOINT=$(jq -r .kadoEndpoint /tomo-install.json)
KADO_KEY=$(jq -r .kadoApiKey    /tomo-install.json)

curl -sS -N "$KADO_ENDPOINT/mcp" \
  -H "Authorization: Bearer $KADO_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc":"2.0","id":1,"method":"tools/call",
    "params":{"name":"kado-open-notes","arguments":{"scope":"all"}}
  }' | grep '^data:' | sed 's/^data: //' | jq .
```

Inspect `result.content[0].text` (parsed) for the `notes[]` shape.
Confirm `path` field format matches what `@` expects when Claude Code
resolves a picked entry.

Record format + any required transformation in `findings.md`.

---

## Files in this directory

| File | Purpose |
|------|---------|
| `README.md` | This file |
| `prep-t1-1.sh` | Host-side: install T1.1 spike into instance (backs up real picker) |
| `restore-picker.sh` | Host-side: restore real picker after any spike |
| `spike-exit-codes.sh` | T1.1 script — query-routed (@CASE_A..@CASE_E) |
| `spike-suffix-marker.sh` | T1.2 script — tests suffix hack |
| `findings.md` | Template for capturing observations. Fill in during spike. |

Findings drive Phase 2 implementation details. Summary decisions get
promoted to the spec README's Decisions Log when each spike closes.
