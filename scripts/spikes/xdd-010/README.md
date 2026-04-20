# XDD 010 Spikes — File Picker

Three live-test scripts to answer Phase-1 unknowns about Claude Code's
`fileSuggestion` API. Each spike is run by **swapping the
`fileSuggestion.command` in your instance's `.claude/settings.json`**
to point at the spike script, restarting Claude in the instance, then
typing `@<query>` and observing what happens.

After each spike, **revert the settings.json change** to point back at
the real `file-suggestion.sh`.

---

## Spike T1.1 — Exit-code behaviour

**Question**: What happens on non-zero exit? On empty stdout? On stdout
with non-path text?

**Setup**:
```bash
# Symlink the spike into the instance .claude/scripts/
ln -sf "$REPO_ROOT/scripts/spikes/xdd-010/spike-exit-codes.sh" \
       "$INSTANCE_PATH/.claude/scripts/file-suggestion.sh"
```

Edit the spike script to comment in/out the various cases, restart Claude,
type `@x` and observe.

**Cases to test**:
- exit 0, three valid paths → expect picker shows them
- exit 0, empty stdout → expect ?  (silent? "no results"?)
- exit 1 → expect ?  (fallback to built-in? error banner?)
- exit 0, three lines of "not a real path" → expect ?  (shown? insertable?)

**Record observations** in `findings.md` (this directory).

---

## Spike T1.2 — Active-note suffix marker

**Question**: If we emit `path/to/note.md (active)`, does Claude Code:
- Show the suffix in the picker UI?
- Include the suffix on insertion into the prompt?
- Resolve the file content despite the suffix? (most important)

**Setup**: same symlink trick with `spike-suffix-marker.sh`.

In your test vault, have at least one note like `Atlas/Test.md`. Restart
Claude. Type `@`, pick the entry shown as `Atlas/Test.md (active)`,
observe what gets inserted and whether the file content is provided to
Claude.

**Outcomes**:
- A) Suffix visible AND insertion clean (Claude Code strips the suffix
  before resolving) → use suffix-hack.
- B) Suffix visible BUT insertion includes it AND file resolves anyway
  → use suffix-hack.
- C) Anything else → fall back to position-only marker.

---

## Spike T1.3 — kado-open-notes path format

**Question**: What format does `notes[].path` come back in? Vault-relative?
Absolute? CLAUDE_PROJECT_DIR-relative?

**Setup**: no script swap needed — direct curl from inside the container.

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

**Inspect** `result.content[0].text` (parsed) for the `notes[]` shape.
Confirm `path` field format matches what `@` expects when Claude Code
resolves a picked entry.

If mismatch → document the transformation needed in
`findings.md` (e.g., "strip leading slash", "prepend vault root").

---

## findings.md

Create `findings.md` in this directory and record:
- Date of spike
- Spike (T1.1 / T1.2 / T1.3)
- Observation
- Decision (if any)

Findings drive Phase 2 implementation details.
