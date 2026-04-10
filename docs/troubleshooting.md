# Troubleshooting

## Authentication

### Browser Auth Callback Fails (String Too Long)

**Symptom:** After authenticating in the browser, the callback URL doesn't work.

**Cause:** The auth callback string is very long and some browsers wrap it across two lines.

**Solution:**
1. Copy the entire callback string from the browser URL bar
2. Paste into a plain text editor
3. Remove the line break so it becomes one continuous string
4. Paste the fixed string back and press Enter

### No .credentials.json Found

**Symptom:** Install script warns about missing `.credentials.json`.

**Solution:** Run `claude login` inside the container on first start.

## Kado Connection

### Container Can't Reach Kado

**Symptom:** MCP connection errors when running `/inbox` or `/explore-vault`.

**Check:**
1. Kado is running: `curl http://localhost:37022/mcp` (should respond, not timeout)
2. Correct host/port in `tomo-install.json` and `.mcp.json`
3. Bearer token is valid (starts with `kado_`)

**Platform-specific:**
- **macOS:** `host.docker.internal` resolves automatically
- **Linux:** `host.docker.internal` may not resolve — use your host's IP address or add `--add-host=host.docker.internal:host-gateway` to Docker run

### Kado Permission Denied

**Symptom:** "Permission denied" or "gate: scope" errors from Kado.

**Cause:** Your API key doesn't have access to the requested vault path.

**Solution:** Check Kado's API key configuration — ensure the key's whitelist includes the folders Tomo needs (inbox, notes, maps, calendar, templates).

## Vault Explorer

### /explore-vault Finds No Notes

**Symptom:** Structure scan shows 0 notes for all concepts.

**Check:**
1. Vault-config concept paths match your actual vault folders
2. Kado can read those folders (test: `kado-search listDir` on a concept path)
3. Vault is not empty

### Discovery Cache Is Empty

**Symptom:** `discovery-cache.yaml` has zero MOCs.

**Possible causes:**
- No files in configured `map_note.paths`
- MOC tag not matching (check `map_note.tags` in vault-config)
- Kado can't read the maps folder

### Frontmatter Detection Shows Wrong Fields

**Symptom:** `/explore-vault` proposes incorrect required/optional fields.

**Solution:** When prompted, edit the proposed fields. You can also manually edit `vault-config.yaml` `frontmatter:` section after discovery.

## Inbox Processing

### /inbox Shows "Nothing to Process"

**Symptom:** `/inbox` reports idle, but you have files in the inbox.

**Check:**
1. Files have the lifecycle tag `#MiYo-Tomo/captured` (or your configured prefix)
2. Files are in the configured inbox folder path
3. Kado can list and read the inbox folder

### Suggestions Document Not Generated

**Symptom:** Pass 1 runs but no suggestions file appears.

**Check:**
1. Kado can write to the inbox folder
2. Check stderr output for errors during analysis

### Token Rendering Fails

**Symptom:** Instruction set has `{{unresolved}}` tokens.

**Check:**
1. Template files exist at the configured paths (verify via Kado)
2. Required tokens (uuid, datestamp, title) should always resolve
3. Config-sourced tokens need matching `frontmatter.optional` entries with defaults

### Lifecycle Tags Not Transitioning

**Symptom:** Running `/inbox` repeatedly does the same thing.

**Check:**
1. You changed the tag in Obsidian (e.g., `proposed` → `confirmed`)
2. Obsidian synced the tag change (if using sync)
3. The tag format matches: `#MiYo-Tomo/confirmed` (exact prefix match)

## Docker

### Image Build Fails

**Symptom:** `docker build` fails during `npm install -g @anthropic-ai/claude-code`.

**Solution:** Check internet connection and Docker DNS. If behind a proxy, configure Docker proxy settings.

### Container Exits Immediately

**Symptom:** `begin-tomo.sh` starts but container exits.

**Check:**
1. `tomo-home/entrypoint.sh` exists and is executable
2. Docker image was built successfully
3. Check logs: `docker logs <container_name>`

## YAML Errors

### vault-config.yaml Won't Parse

**Symptom:** Scripts fail with YAML parse errors.

**Solution:** Run the YAML fixer:
```bash
python3 scripts/yaml-fixer.py config/vault-config.yaml
```

Common fixes: tabs→spaces, unquoted strings with colons, indentation errors.

### Profile YAML Invalid

**Symptom:** Install script fails loading a profile.

**Check:** Validate profile syntax:
```bash
python3 -c "import yaml; yaml.safe_load(open('tomo/profiles/miyo.yaml'))"
```
