#!/usr/bin/env python3
"""Assert wizard skill files exist and contain required structural elements.

Usage:
  python assert_wizard_skills.py <repo_root>

Checks:
1. tomo-trackers-wizard.md exists in tomo/.claude/skills/
2. tomo-daily-log-wizard.md exists in tomo/.claude/skills/
3. Both files have YAML frontmatter with name: tomo-*
4. tomo-trackers-wizard mentions AskUserQuestion and keywords
5. tomo-daily-log-wizard mentions AskUserQuestion and daily_log
6. tomo-setup.md references both wizards in Mode B
7. tomo-setup.md contains Phase 3b section
"""
import sys
import os
import re

repo = sys.argv[1]

def read(path):
    with open(path) as f:
        return f.read()

def check(condition, msg):
    if not condition:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)

trackers_path = os.path.join(repo, "tomo/.claude/skills/tomo-trackers-wizard.md")
daily_log_path = os.path.join(repo, "tomo/.claude/skills/tomo-daily-log-wizard.md")
setup_path = os.path.join(repo, "tomo/.claude/commands/tomo-setup.md")

# Test 1: files exist
check(os.path.exists(trackers_path), f"tomo-trackers-wizard.md not found at {trackers_path}")
check(os.path.exists(daily_log_path), f"tomo-daily-log-wizard.md not found at {daily_log_path}")
check(os.path.exists(setup_path), f"tomo-setup.md not found at {setup_path}")

trackers_content = read(trackers_path)
daily_log_content = read(daily_log_path)
setup_content = read(setup_path)

# Test 2: YAML frontmatter with correct name fields
check("name: tomo-trackers-wizard" in trackers_content,
      "tomo-trackers-wizard.md missing 'name: tomo-trackers-wizard' frontmatter")
check("name: tomo-daily-log-wizard" in daily_log_content,
      "tomo-daily-log-wizard.md missing 'name: tomo-daily-log-wizard' frontmatter")

# Test 3: version header in both
check("# version:" in trackers_content, "tomo-trackers-wizard.md missing # version: comment")
check("# version:" in daily_log_content, "tomo-daily-log-wizard.md missing # version: comment")

# Test 4: trackers wizard has required content
check("AskUserQuestion" in trackers_content,
      "tomo-trackers-wizard.md does not reference AskUserQuestion")
check("keywords" in trackers_content.lower(),
      "tomo-trackers-wizard.md does not mention keywords")
check("description" in trackers_content,
      "tomo-trackers-wizard.md does not mention description field")
check("Edit tool" in trackers_content,
      "tomo-trackers-wizard.md does not specify Edit tool for config writes")

# Test 5: daily-log wizard has required content
check("AskUserQuestion" in daily_log_content,
      "tomo-daily-log-wizard.md does not reference AskUserQuestion")
check("daily_log" in daily_log_content,
      "tomo-daily-log-wizard.md does not mention daily_log")
check("auto_create_if_missing" in daily_log_content,
      "tomo-daily-log-wizard.md does not mention auto_create_if_missing")
check("false" in daily_log_content,
      "tomo-daily-log-wizard.md does not specify auto_create_if_missing: false constraint")

# Test 6: tomo-setup Mode B has both wizard shortcuts
check("trackers" in setup_content and "tomo-trackers-wizard" in setup_content,
      "tomo-setup.md Mode B missing trackers → tomo-trackers-wizard shortcut")
check("daily-log" in setup_content and "tomo-daily-log-wizard" in setup_content,
      "tomo-setup.md Mode B missing daily-log → tomo-daily-log-wizard shortcut")

# Test 7: tomo-setup has Phase 3b
check("Phase 3b" in setup_content,
      "tomo-setup.md does not contain Phase 3b section")
check("daily_log" in setup_content,
      "tomo-setup.md Phase 3b does not check for daily_log section")

print("OK: all wizard skill assertions passed")
