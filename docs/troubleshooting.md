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
1. Kado is running: `curl http://localhost:23026/mcp` (should respond, not timeout)
2. Correct host/port in `tomo-install.json` and `.mcp.json` — Kado binds `127.0.0.1:23026` by default
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

### instructions.json Missing or Malformed

**Symptom:** Pass 2 finished but `*_instructions.json` wasn't written, or the JSON looks wrong.

**Check:**
1. `instruction-render.py` stderr output — it logs each rendered file plus the final paths for `manifest.json`, `instructions.json`, and `instructions.md`.
2. Validate the JSON is machine-consumable:
   ```bash
   python3 scripts/instructions-dryrun.py /path/to/YYYY-MM-DD_HHMM_instructions.json
   ```
   This flags unknown action kinds, missing required fields, and prints a one-line summary per action. Exit 0 = ready for Tomo Hashi / manual apply.
3. `instructions.json` should conform to `tomo/schemas/instructions.schema.json`. The `actions[]` array covers every action the human-readable `instructions.md` references.

### `/inbox` Keeps Running the Same Pass

**Symptom:** Running `/inbox` repeatedly does the same thing (re-runs Pass 1 instead of advancing to Pass 2, or re-runs Pass 2 instead of cleaning up).

**Cause:** `/inbox` is state-driven — it inspects inbox contents to decide what's next. If the expected state marker is missing, it falls back to an earlier pass.

**Check:**
1. **Pass 1 → Pass 2 transition** — the `*_suggestions.md` doc must contain `- [x] Approved` at the top (the whole-document approval). Without it, `/inbox` assumes Pass 1 is still pending and re-runs it.
2. **Pass 2 → Cleanup transition** — per-action `- [x] Applied` checkboxes on the `*_instructions.md` doc signal applied actions. Missing checkboxes keep the instruction set "open."
3. **Source items** still use lifecycle tags (e.g., `#MiYo-Tomo/captured` for inbox items). The tag prefix is set during install; check `tomo-install.json` `prefix` field if unsure.
4. If Obsidian is syncing, give the checkbox/tag changes a moment to propagate before re-running `/inbox`.

## Docker

### Image Build Fails

**Symptom:** `docker build` fails during `npm install -g @anthropic-ai/claude-code`.

**Solution:** Check internet connection and Docker DNS. If behind a proxy, configure Docker proxy settings.

### UID 1000 Is Not Unique

**Symptom:** `docker build` fails at `useradd -u 1000 coder` with `UID 1000 is not unique`.

**Cause:** Recent `node:22-bookworm-slim` base images ship with a `node` user already at UID 1000. The Dockerfile removes it before creating `coder` — if you see this error, you're on an older Dockerfile.

**Solution:** Pull the latest Tomo changes (`git pull`) and rebuild the image. The fix is in `docker/Dockerfile` — the base image's existing UID-1000 user is removed via `userdel -r node || true` before `coder` is created.

### Container Exits Immediately

**Symptom:** `begin-tomo.sh` starts but container exits.

**Check:**
1. `tomo-home/entrypoint.sh` exists and is executable
2. Docker image was built successfully
3. Check logs: `docker logs <container_name>`

### Stale Docker Image

**Symptom:** Claude Code or other container tools behave oddly after a Tomo update, or the image is several days old.

**Solution:** Force a rebuild:
```bash
bash begin-tomo.sh --rebuild-image
```

This rebuilds `miyo-tomo:latest` from `<tomo-repo>/docker/Dockerfile` before launching. Useful after pulling Dockerfile changes or dependency updates.

### OAuth Re-authentication

**Symptom:** Claude Code credentials expired, or you want to switch accounts without touching your instance state.

**Solution:**
```bash
bash begin-tomo.sh --login
```

This launches the container with port 10000 exposed for the OAuth callback. Complete the browser login flow and your new credentials are saved to `tomo-home/.claude/.credentials.json`. No cleanup or re-install needed.

## `@` File Picker

### Empty Picker / No Results

**Symptom:** Typing `@` shows nothing, or `@<query>` returns no matches.

**Check:**
1. `tomo/dot_claude/scripts/file-suggestion.sh` exists in the instance at
   `.claude/scripts/file-suggestion.sh` and is executable.
2. `.claude/settings.json` has `fileSuggestion` wired to the script.
3. Kado is reachable (the picker falls back to cache but the first run
   needs Kado for `listDir` + `kado-open-notes`).
4. Check the cache directory at `cache/` inside the instance — the picker
   writes `inbox-cache`, `vault-cache`, and `open-notes-cache` files there.

The picker always exits 0 by design. A non-zero exit hides the picker
silently and there's no error banner, so failures surface as "empty
results" rather than stack traces. Run the script manually with a query
to see its stderr:

```bash
echo "catan" | bash .claude/scripts/file-suggestion.sh
```

### Picked Note Doesn't Resolve

**Symptom:** `@Calendar/301 Daily/2026-03-26.md` ends up as a quoted literal
or Claude says it can't find the file.

**Cause:** Kado returns vault-relative paths. Claude Code tries `Read`
locally first, hits `ENOENT`, and the session is expected to fall back to
`kado-read`. If your session doesn't have Kado MCP tools in scope, the
fallback can't happen.

**Check:**
1. The current agent/command has `mcp__kado__kado-read` in its tool list.
2. Kado connection is live (see "Container Can't Reach Kado" above).

### Open Notes Not Appearing

**Symptom:** `@` doesn't surface currently-open Obsidian notes — only
inbox + vault files show up.

**Cause:** `kado-open-notes` requires Kado v0.7.0+. Older Kado versions
return `FORBIDDEN` or no such tool, and the picker silently skips open
notes.

**Solution:** Upgrade Kado to v0.7.0+ (check the Kado plugin version in
Obsidian's Community Plugins pane).

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

## Re-Install / Clean State

### Starting Over After a Bad Config

**Symptom:** You picked wrong concept paths, the wrong profile, or want to reset everything.

**Solution:** Use the cleanup script to remove install artifacts, then re-run the installer:
```bash
bash scripts/cleanup-tomo.sh --dry-run    # preview
bash scripts/cleanup-tomo.sh              # interactive
bash scripts/install-tomo.sh              # fresh install
```

To preserve your Claude Code auth between re-runs:
```bash
bash scripts/cleanup-tomo.sh --force --keep-home
```

The cleanup script refuses any path outside the repo root as a safety check.
