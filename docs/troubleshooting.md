# Troubleshooting

## Authentication

### Browser Auth Callback Fails (String Too Long)

**Symptom:** After authenticating in the browser, the callback URL doesn't work — the auth string wraps to two lines in the browser URL bar.

**Cause:** The auth callback string is very long and some browsers or terminals wrap it across two lines, breaking the URL.

**Solution:**
1. Copy the entire callback string from the browser URL bar
2. Paste it into a plain text editor (Notes, TextEdit, nano, etc.)
3. Remove the line break so it becomes one continuous string
4. Copy the fixed string and paste it back into the browser URL bar
5. Press Enter

### No .credentials.json Found

**Symptom:** Install script warns about missing `.credentials.json`.

**Cause:** Claude Code credentials are stored in the macOS Keychain and need to be exported.

**Solution:** Run `claude login` inside the container on first start. The credentials will be created automatically.

## Notifications

### Notifications Not Appearing (macOS)

**Symptom:** No desktop notifications when Tomo needs attention.

**Solution:** Install terminal-notifier:
```bash
brew install terminal-notifier
```

### Notifications Not Appearing (Linux)

**Symptom:** No desktop notifications.

**Solution:** Install libnotify:
```bash
# Debian/Ubuntu
sudo apt install libnotify-bin

# Fedora
sudo dnf install libnotify

# Arch
sudo pacman -S libnotify
```

## Docker

### Container Can't Reach Kado

**Symptom:** MCP connection errors when running /inbox or /execute.

**Possible causes:**
1. Kado is not running on the host
2. Wrong host/port in the instance config
3. Docker networking issue

**Solutions:**
- Verify Kado is running: `curl http://localhost:37022/health`
- Check your `tomo-install.json` for correct Kado host/port
- On Linux, `host.docker.internal` may not resolve — try using the host's actual IP address

### Image Build Fails

**Symptom:** `docker build` fails during `npm install -g @anthropic-ai/claude-code`.

**Solution:** Check your internet connection and Docker's DNS settings. If behind a proxy, configure Docker's proxy settings.
