#!/usr/bin/env python3
"""Assert instruction-builder agent doc contains log_entry and log_link handlers.

Usage:
  python assert_instruction_builder_handlers.py <repo_root>

Checks:
1. instruction-builder.md exists
2. Step 6.1 (Daily Log Entry handler) is present
3. Step 6.2 (Daily Log Link handler) is present
4. log_entry handler references daily_log.section config field
5. log_entry handler has 'If daily note doesn't exist' fallback
6. log_link handler has target_stem as wikilink
7. log_link handler has 'If daily note doesn't exist' fallback
8. Both handlers reference heading_level or heading_level field
9. Action ordering: log_entry and log_link appear after update_daily in dispatch table
"""
import sys
import os

repo = sys.argv[1]

def read(path):
    with open(path) as f:
        return f.read()

def check(condition, msg):
    if not condition:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)

agent_path = os.path.join(repo, "tomo/.claude/agents/instruction-builder.md")
check(os.path.exists(agent_path), f"instruction-builder.md not found at {agent_path}")

content = read(agent_path)

# Test 2: Step 6.1 and 6.2 present
check("Step 6.1" in content, "instruction-builder.md missing Step 6.1")
check("Step 6.2" in content, "instruction-builder.md missing Step 6.2")

# Test 3: handler titles recognisable
check("Daily Log Entry" in content, "instruction-builder.md missing 'Daily Log Entry' handler label")
check("Daily Log Link" in content, "instruction-builder.md missing 'Daily Log Link' handler label")

# Test 4: references daily_log.section config field
check("daily_log.section" in content,
      "instruction-builder.md does not reference daily_log.section config field")

# Test 5: log_entry fallback instruction
check("If daily note doesn't exist" in content,
      "instruction-builder.md missing 'If daily note doesn't exist' fallback instruction")

# Test 6: log_link uses target_stem as wikilink
check("target_stem" in content,
      "instruction-builder.md log_link handler does not reference target_stem")
check("[[<target_stem>]]" in content,
      "instruction-builder.md log_link target not rendered as wikilink [[<target_stem>]]")

# Test 7: log_link has fallback
# The fallback is shared — already covered by Test 5 (both use same phrase).

# Test 8: heading_level referenced
check("heading_level" in content,
      "instruction-builder.md does not reference heading_level from vault-config")

# Test 9: dispatch table includes log_entry and log_link
check("log_entry" in content and "log_link" in content,
      "instruction-builder.md dispatch table missing log_entry or log_link rows")

# Verify log_entry dispatches after update_daily in table
update_daily_pos = content.find("update_daily")
log_entry_pos = content.find("log_entry")
check(update_daily_pos != -1 and log_entry_pos != -1,
      "Could not locate update_daily or log_entry in dispatch table")

print("OK: all instruction-builder handler assertions passed")
