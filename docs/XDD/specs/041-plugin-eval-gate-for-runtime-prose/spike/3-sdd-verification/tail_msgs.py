"""Print the conductor's final report and the main session's final message from a trace."""
import json
import sys

records = [json.loads(line) for line in open(sys.argv[1])]
for rec in records:
    if rec.get("type") == "user":
        for block in rec.get("message", {}).get("content", []):
            if isinstance(block, dict) and block.get("type") == "tool_result" and rec.get("parent_tool_use_id") is None:
                content = block.get("content")
                if isinstance(content, list):
                    text = "".join(c.get("text", "") for c in content if isinstance(c, dict))
                else:
                    text = str(content)
                if "Pass 2" in text:
                    print("=== CONDUCTOR RESULT (as returned to main) ===")
                    print(text[-1500:])
    if rec.get("type") == "result":
        print("=== MAIN FINAL MESSAGE ===")
        print(repr(rec.get("result", "")[-900:]))
