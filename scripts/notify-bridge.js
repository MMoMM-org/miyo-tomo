#!/usr/bin/env node
'use strict';

// Local HTTP → desktop-notification bridge for containerized Claude Code sessions.
//
// Why this exists instead of the npm `dev-notify-bridge` package: that package depends on
// node-notifier@10.0.1, which hardcodes its own vendored `terminal-notifier.app` binary
// (Mach-O x86_64, bundle id nl.superalloy.oss.terminal-notifier). It never looks at PATH,
// so every notification ran an x86 process under Rosetta — and would die silently once
// Rosetta is gone. This bridge shells out to whatever native notifier the host provides.
//
// Zero dependencies on purpose: no npm install, no vendored binaries, no supply chain.
// Wire protocol is byte-compatible with dev-notify-bridge so container-side hooks are unchanged.

const http = require('node:http');
const os = require('node:os');
const { execFile } = require('node:child_process');

const DEFAULT_PORT = 9999;
const MAX_BODY_BYTES = 64 * 1024;
const NOTIFIER_TIMEOUT_MS = 10_000;

// ── CLI ──────────────────────────────────────────────────────

function parsePort(argv) {
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    const raw = arg === '--port' ? argv[i + 1] : arg.startsWith('--port=') ? arg.slice(7) : null;
    if (raw === null) continue;
    const port = Number.parseInt(raw, 10);
    if (Number.isInteger(port) && port > 0 && port < 65536) return port;
    fail(`Invalid --port value: ${raw}`);
  }
  return DEFAULT_PORT;
}

function fail(message) {
  console.error(`[notify-bridge] ${message}`);
  process.exit(1);
}

function log(message) {
  console.log(`[notify-bridge] ${message}`);
}

// ── Notifier dispatch ────────────────────────────────────────

// execFile with an argument array — never a shell string. Titles and messages originate
// from Claude sessions and must not be able to reach a shell.
function run(command, args) {
  return new Promise((resolve, reject) => {
    execFile(command, args, { timeout: NOTIFIER_TIMEOUT_MS }, (err) => {
      if (err) reject(err);
      else resolve();
    });
  });
}

const isMissingBinary = (err) => err && (err.code === 'ENOENT' || err.code === 127);

// AppleScript string literal — escapes backslash and double quote.
const appleScriptString = (value) => `"${String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;

async function notifyDarwin({ title, message, sound }) {
  // Homebrew terminal-notifier (arm64 native) is preferred: it supports sound and grouping.
  try {
    const args = ['-title', title, '-message', message];
    if (sound) args.push('-sound', 'default');
    await run('terminal-notifier', args);
    return 'terminal-notifier';
  } catch (err) {
    if (!isMissingBinary(err)) throw err;
  }

  // Fallback so the bridge works on a bare macOS host without Homebrew.
  let script = `display notification ${appleScriptString(message)} with title ${appleScriptString(title)}`;
  if (sound) script += ' sound name "Submarine"';
  await run('osascript', ['-e', script]);
  return 'osascript';
}

async function notifyLinux({ title, message }) {
  // `--` guards against a title that starts with a dash being parsed as an option.
  await run('notify-send', ['--', title, message]);
  return 'notify-send';
}

async function dispatch(notification) {
  switch (process.platform) {
    case 'darwin':
      return notifyDarwin(notification);
    case 'linux':
      return notifyLinux(notification);
    default:
      throw Object.assign(new Error(`Unsupported platform: ${process.platform}`), { unsupported: true });
  }
}

function describeFailure(err) {
  if (err.unsupported) return err.message;
  if (isMissingBinary(err)) {
    return process.platform === 'darwin'
      ? 'No notifier found (terminal-notifier and osascript both missing)'
      : 'notify-send not found — install libnotify-bin';
  }
  if (err.killed) return `Notifier timed out after ${NOTIFIER_TIMEOUT_MS}ms`;
  return err.message || String(err);
}

// ── HTTP ─────────────────────────────────────────────────────

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', (chunk) => {
      size += chunk.length;
      if (size > MAX_BODY_BYTES) {
        reject(Object.assign(new Error('Request body too large'), { status: 413 }));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

async function handleNotify(req, res, verbose) {
  let body;
  try {
    const raw = await readBody(req);
    body = raw ? JSON.parse(raw) : {};
  } catch (err) {
    sendJson(res, err.status || 400, { success: false, error: err.status ? err.message : 'Invalid JSON body' });
    return;
  }

  if (!body || !body.title || !body.message) {
    sendJson(res, 400, { success: false, error: 'Missing title or message' });
    return;
  }

  const notification = {
    title: String(body.title),
    message: String(body.message),
    sound: body.sound ?? true,
  };

  try {
    const notifier = await dispatch(notification);
    if (verbose) log(`Notification: ${notification.title} - ${notification.message} (via ${notifier})`);
    sendJson(res, 200, {
      success: true,
      backend: 'desktop',
      response: 'Notification sent',
      metadata: { hostname: os.hostname(), platform: os.platform(), notifier },
    });
  } catch (err) {
    // Surfaced rather than swallowed: a silently broken notifier is how the x86 bridge failed.
    const error = describeFailure(err);
    console.error(`[notify-bridge] Failed to send notification: ${error}`);
    sendJson(res, 500, { success: false, backend: 'desktop', error });
  }
}

function startBridge({ port = DEFAULT_PORT, verbose = false } = {}) {
  const server = http.createServer((req, res) => {
    const path = (req.url || '/').split('?')[0];

    if (req.method === 'POST' && path === '/notify') {
      handleNotify(req, res, verbose);
      return;
    }

    if (req.method === 'GET' && (path === '/' || path === '/health')) {
      sendJson(res, 200, {
        name: 'notify-bridge',
        status: 'ok',
        message: 'POST /notify to trigger desktop notifications',
        port,
        platform: os.platform(),
      });
      return;
    }

    sendJson(res, 404, { success: false, error: 'Not found' });
  });

  server.on('error', (err) => {
    fail(err.code === 'EADDRINUSE' ? `Port ${port} is already in use` : err.message);
  });

  // 0.0.0.0 is required: containers reach the host via host.docker.internal, which resolves
  // to the host's gateway address, not loopback.
  server.listen(port, '0.0.0.0', () => {
    log(`Running on http://localhost:${port} (platform: ${os.platform()})`);
    log('Listening for POST /notify requests...');
  });

  for (const signal of ['SIGINT', 'SIGTERM']) {
    process.on(signal, () => {
      log(`Received ${signal} — shutting down`);
      // Idle keep-alive sockets would otherwise hold server.close() open indefinitely,
      // leaving the port bound after begin-code.sh quits the screen session.
      server.closeAllConnections?.();
      server.close(() => process.exit(0));
      setTimeout(() => process.exit(0), 2000).unref();
    });
  }

  return server;
}

const argv = process.argv.slice(2);
startBridge({ port: parsePort(argv), verbose: argv.includes('--verbose') || argv.includes('-v') });
