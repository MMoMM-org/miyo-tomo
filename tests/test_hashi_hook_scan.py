#!/usr/bin/env python3
# version: 0.1.0
"""test_hashi_hook_scan.py — Behavioural tests for hashi-hook-scan.py.

The scanner classifies generated Hashi hooks into green/yellow/red tiers plus a
mass-change flag. Per the MiYo Constitution (Testing L1), permission/safety logic
must prove BOTH correct allow (green stays green) AND correct reject (dangerous
constructs escalate to red), plus the mass-change flag in both directions.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

import importlib

scan_mod = importlib.import_module("hashi-hook-scan")
scan = scan_mod.scan


# ---------------------------------------------------------------------------
# GREEN — Obsidian API only
# ---------------------------------------------------------------------------

GREEN_HOOK = """
module.exports = async (ctx) => {
  const { action, app, logger } = ctx;
  const file = app.vault.getAbstractFileByPath(action.destination);
  if (!file) return { warnings: ["not found"] };
  await app.fileManager.processFrontMatter(file, (fm) => {
    fm.aliases = [`${action.title} (HASHI)`];
  });
  logger.info("alias set");
  return { info: ["alias set"] };
};
"""


def test_green_obsidian_api_only():
    result = scan(GREEN_HOOK)
    assert result["tier"] == "green"
    assert result["mass_change"] is False
    assert result["findings"] == []


# ---------------------------------------------------------------------------
# RED — must reject dangerous constructs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("category,source", [
    ("child_process",
     "const cp = require('child_process'); module.exports = async (ctx) => {};"),
    ("child_process",
     "const cp = require('node:child_process'); module.exports = async (ctx) => {};"),
    ("shell-exec",
     "const { execSync } = require('node:os'); execSync('rm -rf /');"),
    ("network-require",
     "const https = require('https'); module.exports = async (ctx) => {};"),
    ("network-fetch",
     "module.exports = async (ctx) => { await fetch('http://evil.example/x'); };"),
    ("network-fetch",
     "module.exports = async (ctx) => { await requestUrl({url:'http://x'}); };"),
    ("code-eval",
     "module.exports = async (ctx) => { eval(ctx.action.title); };"),
    ("code-eval",
     "const vm = require('node:vm'); module.exports = async (ctx) => {};"),
    ("dynamic-require",
     "module.exports = async (ctx) => { const m = require(ctx.action.title); };"),
])
def test_red_dangerous_constructs(category, source):
    result = scan(source)
    assert result["tier"] == "red", f"{category} should classify red"
    assert any(f["category"] == category for f in result["findings"])


def test_red_fs_write():
    source = (
        "const fs = require('node:fs');\n"
        "module.exports = async (ctx) => { fs.writeFileSync('/tmp/x', 'data'); };"
    )
    result = scan(source)
    assert result["tier"] == "red"
    assert any(f["category"] == "fs-write" for f in result["findings"])


# ---------------------------------------------------------------------------
# YELLOW — flag but do not reject
# ---------------------------------------------------------------------------

def test_yellow_fs_read_only():
    source = (
        "const fs = require('node:fs');\n"
        "module.exports = async (ctx) => { const c = fs.readFileSync('/etc/hosts'); };"
    )
    result = scan(source)
    assert result["tier"] == "yellow"
    assert any(f["category"] == "fs-read" for f in result["findings"])


def test_yellow_process_env():
    source = "module.exports = async (ctx) => { const t = process.env.TOKEN; };"
    result = scan(source)
    assert result["tier"] == "yellow"
    assert any(f["category"] == "process-env" for f in result["findings"])


def test_yellow_builtin_module():
    source = "const crypto = require('crypto'); module.exports = async (ctx) => {};"
    result = scan(source)
    assert result["tier"] == "yellow"


# ---------------------------------------------------------------------------
# MASS-CHANGE — orthogonal flag, both directions
# ---------------------------------------------------------------------------

def test_mass_change_detected_even_with_green_api():
    source = """
    module.exports = async (ctx) => {
      const files = ctx.app.vault.getMarkdownFiles();
      for (const f of files) {
        await ctx.app.fileManager.processFrontMatter(f, (fm) => { fm.touched = true; });
      }
    };
    """
    result = scan(source)
    assert result["mass_change"] is True
    # Tier stays green — uses only the Obsidian API — but the flag warns.
    assert result["tier"] == "green"


def test_no_mass_change_single_file():
    result = scan(GREEN_HOOK)
    assert result["mass_change"] is False


# ---------------------------------------------------------------------------
# Comment stripping — no false positives from commented-out danger
# ---------------------------------------------------------------------------

def test_commented_danger_is_ignored():
    source = """
    // const cp = require('child_process');
    /* await fetch('http://x'); */
    module.exports = async (ctx) => {
      return { info: ["clean"] };
    };
    """
    result = scan(source)
    assert result["tier"] == "green"
    assert result["findings"] == []
