"""build_fixtures.py — builds the spec 043 grader-pattern trace fixtures in this directory.

Exists so every fixture beside it can be traced to a recorded spike trace plus one
named edit. Two steps:

  trim <pass1-raw-trace> <pass2-raw-trace> <out-dir>
      Writes pass1-spike.jsonl and pass2-spike.jsonl from the kept raw spike traces
      (e-t7N3jn = Pass 1, e-O6bppm = Pass 2): drops rate-limit, init, thinking-token and
      thinking-only events, and neutralises workspace/repo paths. The raw traces lived
      under /private/tmp/e-t7N3jn/out/ and /private/tmp/e-O6bppm/out/, which are
      temporary: once they are gone this step cannot be re-run, and the committed
      pass1-spike.jsonl / pass2-spike.jsonl are the source of record.

  variants <fixtures-dir> <out-dir>
      Derives every variant fixture from the committed pass1-spike.jsonl and
      pass2-spike.jsonl in <fixtures-dir>. Re-runnable; tests/test_043_grader_patterns.py
      runs it into a temp dir and requires byte-identical output.

Not collected by pytest (not under tests/, not named test_*).
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

PASS1_WS = "e-t7N3jn"
PASS2_WS = "e-O6bppm"
# Pass 1 raw-trace lines 121/122: `ls -la tomo-tmp/items` (owner name in the listing),
# not needed by any pattern.
PASS1_DROPPED = {121, 122}


def enc(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False, separators=(",", ":"))


def write(out: Path, name: str, lines: list[str]) -> None:
    text = "\n".join(lines) + "\n"
    (out / name).write_text(text, encoding="utf-8")
    print(name, len(lines), "lines", len(text.encode("utf-8")), "bytes")


def index_of(lines: list[str], needle: str) -> int:
    return next(i for i, line in enumerate(lines) if needle in line)


def indices_of(lines: list[str], needle: str) -> list[int]:
    return [i for i, line in enumerate(lines) if needle in line]


# ---- trim ---------------------------------------------------------------------------


def neutral(line: str, ws_id: str) -> str:
    line = line.replace(
        f"/private/tmp/{ws_id}/tmp/claude-501/-private-tmp-{ws_id}-home-cwd", "<TASKS>"
    )
    line = line.replace(f"/private/tmp/{ws_id}/home/cwd", "<WS>")
    line = line.replace(f"/private/tmp/{ws_id}", "<WS-ROOT>")
    line = line.replace(f"-private-tmp-{ws_id}", "-WS")
    line = line.replace("/Volumes/Moon/Coding/MiYo/Tomo", "<REPO>")
    line = line.replace("claude-501", "claude-UID")
    line = line.replace(ws_id, "WS")
    return line


def keep(event: dict) -> bool:
    kind = event.get("type")
    if kind == "rate_limit_event":
        return False
    if kind == "system" and event.get("subtype") in ("init", "thinking_tokens"):
        return False
    content = (event.get("message") or {}).get("content")
    if (
        kind == "assistant"
        and isinstance(content, list)
        and all(b.get("type") == "thinking" for b in content)
    ):
        return False
    return True


def trim_trace(path: Path, ws_id: str, dropped: set[int] = frozenset()) -> list[str]:
    raw = path.read_text(encoding="utf-8").split("\n")
    if raw[-1] == "":
        raw.pop()
    out = []
    for i, line in enumerate(raw):
        event = json.loads(line)
        assert enc(event) == line, f"{path}:{i} is not compactly encoded"
        if i in dropped or not keep(event):
            continue
        out.append(neutral(line, ws_id))
    for line in out:
        json.loads(line)
    return out


def trim(pass1_raw: Path, pass2_raw: Path, out: Path) -> None:
    write(out, "pass1-spike.jsonl", trim_trace(pass1_raw, PASS1_WS, PASS1_DROPPED))
    write(out, "pass2-spike.jsonl", trim_trace(pass2_raw, PASS2_WS))


# ---- variants -----------------------------------------------------------------------


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def pass1_variants(p1: list[str], out: Path) -> None:
    agents = indices_of(p1, '"name":"Agent","input":{')
    first_agent = agents[0]

    warn_result = json.loads(
        p1[index_of(p1, "active tracker field(s) have no keywords")]
    )
    warn_text = warn_result["message"]["content"][0]["content"]
    template = json.loads(
        p1[index_of(p1, '"text":"Next I\'ll load the suggest-handling skill')]
    )
    relay = copy.deepcopy(template)
    relay["message"]["content"][0]["text"] = warn_text
    relay["uuid"] = "00000000-0000-4000-8000-000000000001"
    relay_line = enc(relay)

    v = list(p1)
    v.insert(first_agent, relay_line)
    write(out, "pass1-warn-before-dispatch.jsonl", v)

    v = list(p1)
    v.insert(first_agent + 1, relay_line)
    write(out, "pass1-warn-after-dispatch.jsonl", v)

    red_use = index_of(p1, '"command":"python3 scripts/suggestions-reducer.py')
    red_res = index_of(p1, '"content":"suggestions-reducer: done=')
    assert red_res == red_use + 1
    assert red_use > agents[-1]

    def move_reducer_to(target: int) -> list[str]:
        v = list(p1)
        moved = v[red_use : red_res + 1]
        del v[red_use : red_res + 1]
        v[target:target] = moved
        return v

    write(out, "pass1-reducer-before-dispatch.jsonl", move_reducer_to(first_agent))
    write(out, "pass1-reducer-between-dispatches.jsonl", move_reducer_to(agents[-1]))

    dresden = index_of(p1, '"description":"Analyse Dresden"')

    def flatten_dresden(field: str) -> list[str]:
        event = json.loads(p1[dresden])
        block = event["message"]["content"][0]
        prompt = block["input"]["prompt"]
        nested = f'{field} = "100 Inbox/Places/Dresden.md"'
        assert prompt.count(nested) == 1, field
        block["input"]["prompt"] = prompt.replace(
            nested, f'{field} = "100 Inbox/Dresden.md"'
        )
        v = list(p1)
        v[dresden] = enc(event)
        return v

    # The prompt aligns `=` with padding; the field name carries the padding.
    write(out, "pass1-dresden-key-flattened.jsonl", flatten_dresden("item_key       "))
    write(out, "pass1-dresden-path-flattened.jsonl", flatten_dresden("path           "))

    w_use = index_of(p1, '"command":"python3 scripts/kado-write-file.py')
    w_res = index_of(p1, '"content":"kado-write-file: ')

    def second_write(stem: str) -> list[str]:
        use = json.loads(p1[w_use])
        res = json.loads(p1[w_res])
        tid = "toolu_00000000000000000000json"
        use["message"]["content"][0]["id"] = tid
        use["message"]["content"][0]["input"]["command"] = (
            "python3 scripts/kado-write-file.py --local tomo-tmp/suggestions-wire.json "
            f'--vault "100 Inbox/{stem}_suggestions.json"'
        )
        use["uuid"] = "00000000-0000-4000-8000-000000000002"
        res["message"]["content"][0]["tool_use_id"] = tid
        res["message"]["content"][0]["content"] = (
            "kado-write-file: tomo-tmp/suggestions-wire.json (3 bytes, op=file) "
            f"→ 100 Inbox/{stem}_suggestions.json"
        )
        res["uuid"] = "00000000-0000-4000-8000-000000000003"
        res.pop("tool_use_result", None)
        v = list(p1)
        v[w_res + 1 : w_res + 1] = [enc(use), enc(res)]
        return v

    write(out, "pass1-two-writes-same-stem.jsonl", second_write("2026-10-30_0000"))
    write(out, "pass1-two-writes-different-stem.jsonl", second_write("2026-10-30_1200"))


def pass2_variants(p2: list[str], out: Path) -> None:
    hb = index_of(p2, "[Subagent hand-back]")
    event = json.loads(p2[hb])
    sentence = "Pass 2 ran, with one upload problem."
    block = event["message"]["content"][0]["content"][0]
    anchor = "The report follows:\n  > Pass 2 complete"
    assert anchor in block["text"]
    block["text"] = block["text"].replace(
        anchor, f"The report follows:\n  {sentence}\n  > Pass 2 complete"
    )
    returned = event["tool_use_result"]["content"][1]
    assert returned["text"].startswith("> Pass 2 complete")
    returned["text"] = f"{sentence}\n" + returned["text"]
    v = list(p2)
    v[hb] = enc(event)
    write(out, "pass2-status-sentence.jsonl", v)

    v = list(p2)
    v.insert(hb + 1, p2[hb])
    write(out, "pass2-duplicate-handback.jsonl", v)


def variants(fixtures: Path, out: Path) -> None:
    pass1_variants(read_lines(fixtures / "pass1-spike.jsonl"), out)
    pass2_variants(read_lines(fixtures / "pass2-spike.jsonl"), out)


def main(argv: list[str]) -> int:
    if len(argv) == 4 and argv[0] == "trim":
        trim(Path(argv[1]), Path(argv[2]), Path(argv[3]))
        return 0
    if len(argv) == 3 and argv[0] == "variants":
        variants(Path(argv[1]), Path(argv[2]))
        return 0
    print(
        "usage: build_fixtures.py trim <pass1-raw> <pass2-raw> <out-dir>\n"
        "       build_fixtures.py variants <fixtures-dir> <out-dir>",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
