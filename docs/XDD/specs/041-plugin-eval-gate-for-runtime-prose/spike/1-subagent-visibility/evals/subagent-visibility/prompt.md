---
name: subagent-visibility
description: Can graders see tool calls made inside a plugin subagent?
runs: 1
max_turns: 8
timeout_seconds: 240
allowed_tools: [Agent, Bash]
---
Use the Agent tool to dispatch the `tomo-eval-spike:probe-runner` agent with the prompt "run the visibility probe". Do not run any shell command yourself. When it returns, repeat its one-line reply verbatim.
