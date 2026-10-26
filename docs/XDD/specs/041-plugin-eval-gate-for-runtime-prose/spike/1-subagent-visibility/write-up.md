## Spike result: yes, an eval run reaches and observes a plugin subagent

The question that decided whether this issue is worth pursuing was whether an eval run can reach one of our subagents and see what it does. It can. I tested it on Claude Code 2.1.310, which also clears the version floor (≥ 2.1.269).

**Setup.** A throwaway plugin outside the repo:

- `.claude-plugin/plugin.json` with `{ "name": "tomo-eval-spike" }`.
- One agent, `probe-runner` (haiku, `tools: Bash`), whose only job is `echo PROBE-INSIDE-SUBAGENT-7f3a`.
- One case: `allowed_tools: [Agent, Bash]`, with a prompt that tells the main session to dispatch `tomo-eval-spike:probe-runner` and not to run any shell command itself.

It ran with `--runs 1 --ablation none --no-publish --allow-tools "Bash(echo:*)"`.

| Grader | Positive run | Negative control (agent echoes a different string) |
|---|---|---|
| `tool_used: Agent`, `input_match: probe-runner` | ✅ 1× | ✅ 1× |
| `tool_used: Bash`, `input_match: PROBE-INSIDE-SUBAGENT-7f3a` | ✅ 1× | ❌ 0× |
| `regex` over `trace` for the command | ✅ | ❌ |
| `regex` over `last_message` for the relayed output | ✅ | ❌ |

- **The Bash call came from inside the subagent.** In `trace.jsonl`, its record carries `parent_tool_use_id` equal to the `Agent` call's id, and the main session made no Bash call of its own. So `tool_used`, and by the same trace `tool_order`, count calls made inside a subagent. The docs don't say this; it is observed.
- **The negative control shows the graders can fail.** With a different command, grader 2 and grader 3 went red while the dispatch grader stayed green.
- **Cost:** $0.13 for the positive run and $0.09 for the control, about 16 s each.

**Consequence.** Item 4's worst case ("only the command-level surface is testable") is ruled out. A case can dispatch `tomo:synthesis-conductor` directly and assert on the scripts it runs, so the next step in the plan applies: reproduce the `4350ddd` ordering defect with `tool_order` and show it red against the pre-fix commit.

**Still open, unchanged by the spike:**

- The empty working directory. Every case needs a `scaffold_script` that stages `scripts/` and a `tomo-tmp/` fixture, and every run needs `--scaffold`.
- The manifest decision (permanent vs generated), which belongs in Kokoro first.
