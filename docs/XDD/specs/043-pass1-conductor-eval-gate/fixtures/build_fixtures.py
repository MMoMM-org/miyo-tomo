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

    # Appended last: the reducer call moved before the first dispatch, behind a `cd` prefix
    # and a double space, which the grader's anchor must still see.
    prefixed = move_reducer_to(first_agent)
    use_at = index_of(prefixed, '"command":"python3 scripts/suggestions-reducer.py')
    old = "python3 scripts/suggestions-reducer.py"
    assert prefixed[use_at].count(old) == 1
    prefixed[use_at] = prefixed[use_at].replace(
        old, "cd . && python3  scripts/suggestions-reducer.py"
    )
    write(out, "pass1-reducer-prefixed-before-dispatch.jsonl", prefixed)


# ---- Pass 1 completions (T2.2/T2.3) --------------------------------------------------
# The spike stopped after the .md write. These fixtures continue it the way the skill
# prescribes; every event added is a deep copy of a recorded event of the same kind with
# its id, uuid and payload replaced.

STEM = "2026-10-30_0000"
RUN_ID = "2026-10-30T00-00-00Z-c0ffee"
REPORT = (
    f"Pass 1 complete: 3 items analysed, suggestions written to [[{STEM}_suggestions]]. "
    "Review in Obsidian, check the **Approved** box, then re-run `/inbox`."
)
DUPLICATE_LINE = (
    "1 proposed MOC(s) already existed in the vault and are offered as unticked "
    "links instead."
)


def _counter():
    # Call order is load-bearing for byte stability: ids come from ONE counter over the
    # whole variant sequence, so append new variants at the end of their builder function.
    n = [0x100]

    def next_ids() -> tuple[str, str, str]:
        n[0] += 1
        tag = f"{n[0]:04x}"
        return (
            f"toolu_0000000000000000000000{tag}",
            f"00000000-0000-4000-8000-00000000{tag}",
            f"00000000-0000-4000-8000-00000001{tag}",
        )

    return next_ids


def _call(
    use_tpl: str, res_tpl: str, ids, name: str, inp: dict, output: str
) -> list[str]:
    tid, use_uuid, res_uuid = ids()
    use = json.loads(use_tpl)
    block = use["message"]["content"][0]
    block.update(id=tid, name=name, input=inp)
    use["uuid"] = use_uuid
    res = json.loads(res_tpl)
    rblock = res["message"]["content"][0]
    rblock.update(tool_use_id=tid, content=output)
    res["uuid"] = res_uuid
    res.pop("tool_use_result", None)
    res.pop("tool_result_meta", None)
    return [enc(use), enc(res)]


def _text_event(template: str, text: str, uuid: str) -> str:
    event = json.loads(template)
    event["message"]["content"] = [{"type": "text", "text": text}]
    event["uuid"] = uuid
    return enc(event)


def _final_result(template: str, text: str) -> str:
    event = json.loads(template)
    event["result"] = text
    return enc(event)


def _replace_report(lines: list[str], text: str) -> list[str]:
    """Swap the report text in the last assistant text event and the final result."""
    v = list(lines)
    i = max(indices_of(v, '"type":"text","text":"Pass 1 complete'))
    event = json.loads(v[i])
    event["message"]["content"][0]["text"] = text
    v[i] = enc(event)
    v[-1] = _final_result(v[-1], text)
    return v


def _move(lines: list[str], start: int, stop: int, target: int) -> list[str]:
    """Move lines[start:stop] so they start at index `target` of the original list."""
    v = list(lines)
    block = v[start:stop]
    del v[start:stop]
    if target > start:
        target -= stop - start
    v[target:target] = block
    return v


def pass1_completions(p1: list[str], out: Path) -> None:
    ids = _counter()
    bash_use = p1[index_of(p1, '"command":"python3 scripts/kado-write-file.py')]
    bash_res = p1[index_of(p1, '"content":"kado-write-file: ')]
    md_res = index_of(p1, '"content":"kado-write-file: ')
    text_tpl = p1[index_of(p1, '"text":"Next I\'ll load the suggest-handling skill')]
    interim = p1[index_of(p1, '"result":"Batch 2 (Gamma) is dispatched')]
    final = p1[-1]
    assert json.loads(final)["type"] == "result"

    def bash(command: str, output: str) -> list[str]:
        return _call(bash_use, bash_res, ids, "Bash", {"command": command}, output)

    json_write = bash(
        "python3 scripts/kado-write-file.py --local tomo-tmp/suggestions-wire.json "
        f'--vault "100 Inbox/{STEM}_suggestions.json"',
        "kado-write-file: tomo-tmp/suggestions-wire.json (2048 bytes, op=file) "
        f"→ 100 Inbox/{STEM}_suggestions.json",
    )
    mark = bash(
        f"python3 scripts/mark-captured.py --state tomo-tmp/inbox-state.jsonl --run-id {RUN_ID}",
        "mark-captured: marked=3 errors=0 declined=0 skipped_non_md=0 squelched=0",
    )

    def complete(report: str) -> list[str]:
        return (
            p1[: md_res + 1]
            + json_write
            + mark
            + [_text_event(text_tpl, report, "00000000-0000-4000-8000-0000000000f0")]
            + [interim, _final_result(final, report)]
        )

    done = complete(REPORT)
    write(out, "pass1-complete.jsonl", done)

    warn_line = json.loads(p1[index_of(p1, "active tracker field(s) have no keywords")])
    stderr = warn_line["message"]["content"][0]["content"]
    (warn_text,) = [ln for ln in stderr.splitlines() if ln.startswith("WARN: ")]
    relayed_report = f"{REPORT}\n\n{DUPLICATE_LINE}\n\n{warn_text}"
    relayed = complete(relayed_report)

    def cat_relay(ids_fn, output: str) -> list[str]:
        return _call(
            bash_use,
            bash_res,
            ids_fn,
            "Bash",
            {"command": "cat tomo-tmp/setup-warnings.txt"},
            output,
        )

    def before_batch_count(lines: list[str], block: list[str]) -> list[str]:
        v = list(lines)
        at = index_of(v, '"command":"python3 scripts/read-routing-plan.py --batch-count')
        v[at:at] = block
        return v

    # F2-AC2 (2026-10-31): the relay is the `cat` of the saved warnings at the top of
    # step 3. Fixed ids, not the shared counter, so no later fixture changes.
    def fixed_ids() -> tuple[str, str, str]:
        return (
            "toolu_000000000000000000000000f1",
            "00000000-0000-4000-8000-0000000000f1",
            "00000000-0000-4000-8000-0000000000f2",
        )

    relayed = before_batch_count(relayed, cat_relay(fixed_ids, warn_text))
    write(out, "pass1-complete-relayed.jsonl", relayed)

    agents = indices_of(done, '"name":"Agent","input":{')
    agent_res = index_of(done, '"text":"Async agent launched successfully.')
    agent_use = done[agents[0]]
    conductor_read_res = index_of(
        done, '"content":"1\\t---\\n2\\tname: suggestion-conductor'
    )
    v = list(done)
    v[conductor_read_res + 1 : conductor_read_res + 1] = _call(
        agent_use,
        done[agent_res],
        ids,
        "Agent",
        {
            "subagent_type": "tomo:suggestion-conductor",
            "description": "Run Pass 1",
            "prompt": "Run Pass 1. The routing plan is at tomo-tmp/routing-plan.json.",
        },
        [{"type": "text", "text": "Async agent launched successfully."}],
    )
    write(out, "pass1-conductor-dispatched.jsonl", v)

    v = list(done)
    for i in agents:
        event = json.loads(v[i])
        block = event["message"]["content"][0]
        assert block["input"]["subagent_type"] == "tomo:inbox-analyst"
        block["input"] = {
            ("name" if k == "subagent_type" else k): (
                "inbox-analyst" if k == "subagent_type" else val
            )
            for k, val in block["input"].items()
        }
        v[i] = enc(event)
    write(out, "pass1-analyst-name-not-type.jsonl", v)

    skill = index_of(done, '"name":"Skill","input":{')
    v = list(done)
    v[skill:skill] = bash(
        "python3 scripts/run-id.py --out tomo-tmp/.run_id", RUN_ID
    ) + bash(
        "python3 scripts/shared-ctx-builder.py --cache config/discovery-cache.yaml "
        "--vault-config config/vault-config.yaml --profiles-dir profiles "
        f"--run-id {RUN_ID} --output tomo-tmp/shared-ctx.json",
        "[shared-ctx] reconcile: cache clean (2 MOC(s) verified)",
    )
    write(out, "pass1-setup-twice.jsonl", v)

    ctx_use = index_of(done, '"command":"python3 scripts/shared-ctx-builder.py')
    assert index_of(done, "active tracker field(s) have no keywords") == ctx_use + 1
    first_res = index_of(done, '"text":"Async agent launched successfully.')
    write(
        out,
        "pass1-dispatch-before-setup.jsonl",
        _move(done, ctx_use, ctx_use + 2, first_res + 1),
    )

    red = index_of(done, '"command":"python3 scripts/suggestions-reducer.py')
    ren = index_of(done, '"command":"python3 scripts/suggestions-render.py')
    assert ren == red + 2
    write(out, "pass1-render-before-reduce.jsonl", _move(done, ren, ren + 2, red))

    md_use = index_of(
        done,
        '"command":"python3 scripts/kado-write-file.py --local tomo-tmp/suggestions-rendered.md',
    )
    vault_md = f"<WS>/100 Inbox/{STEM}_suggestions.md"
    v = list(done)
    v[md_use : md_use + 2] = _call(
        bash_use,
        bash_res,
        ids,
        "Write",
        {"file_path": vault_md, "content": "# Suggestions\n"},
        f"File created successfully at: {vault_md}",
    )
    write(out, "pass1-write-tool-publish.jsonl", v)

    mark_use = index_of(done, '"command":"python3 scripts/mark-captured.py')
    json_use = index_of(done, "--local tomo-tmp/suggestions-wire.json")
    write(
        out,
        "pass1-mark-before-json-write.jsonl",
        _move(done, mark_use, mark_use + 2, json_use),
    )

    field = index_of(
        done, '"command":"python3 scripts/read-routing-plan.py --field inbox_path"'
    )
    v = list(done)
    v[field + 2 : field + 2] = bash(
        "python3 -c \"import json; print(json.load(open('tomo-tmp/routing-plan.json'))"
        "['inbox_path'])\"",
        "100 Inbox/",
    )
    write(out, "pass1-inline-python.jsonl", v)

    quoted = (
        "I ran the pipeline. The skill's report would read \"Pass 1 complete: 3 items "
        f'analysed, suggestions written to [[{STEM}_suggestions]]." Please check the '
        "note before you approve it."
    )
    write(out, "pass1-report-quoted.jsonl", _replace_report(done, quoted))

    twice = list(done)
    twice[mark_use + 2 : mark_use + 2] = bash(
        f"python3 scripts/mark-captured.py --state tomo-tmp/inbox-state.jsonl --run-id {RUN_ID}",
        "mark-captured: marked=0 errors=0 declined=0 skipped_non_md=0 squelched=0",
    )
    write(out, "pass1-mark-twice.jsonl", twice)

    # Appended last (ids come from one counter): both publishes behind a `cd` prefix.
    v = list(done)
    for i in indices_of(v, '"command":"python3 scripts/kado-write-file.py'):
        v[i] = v[i].replace(
            '"command":"python3 scripts/', '"command":"cd . && python3 scripts/'
        )
    write(out, "pass1-complete-prefixed-writes.jsonl", v)

    # An analyst prompt that merely names the conductor is not a conductor dispatch.
    v = list(done)
    event = json.loads(v[agents[0]])
    event["message"]["content"][0]["input"]["prompt"] += (
        " (The suggestion-conductor already ran setup.)"
    )
    v[agents[0]] = enc(event)
    write(out, "pass1-analyst-mentions-conductor.jsonl", v)

    # Appended last: two script calls chained with `&&` in ONE Bash call (the skill shows
    # both writes in one fenced block). The second call's tool_use and tool_result are
    # dropped; its command and output are appended to the first call's.
    def chain(lines: list[str], first: int, second: int) -> list[str]:
        use, res = json.loads(lines[first]), json.loads(lines[first + 1])
        use2, res2 = json.loads(lines[second]), json.loads(lines[second + 1])
        block = use["message"]["content"][0]
        block["input"]["command"] += (
            " && " + use2["message"]["content"][0]["input"]["command"]
        )
        rblock = res["message"]["content"][0]
        rblock["content"] += "\n" + res2["message"]["content"][0]["content"]
        res.pop("tool_use_result", None)
        v = list(lines)
        v[first], v[first + 1] = enc(use), enc(res)
        del v[second : second + 2]
        return v

    # `json_use` above is the Skill expansion (its prose names the wire file first), so
    # pass1-mark-before-json-write moved mark-captured before both writes; the publish
    # itself is found by its command, and mark-between-writes is the described shape.
    json_call = index_of(
        done,
        '"command":"python3 scripts/kado-write-file.py --local tomo-tmp/suggestions-wire.json',
    )
    write(out, "pass1-complete-chained-writes.jsonl", chain(done, md_use, json_call))
    write(
        out,
        "pass1-complete-chained-json-mark.jsonl",
        chain(done, json_call, mark_use),
    )
    write(
        out,
        "pass1-mark-between-writes.jsonl",
        _move(done, mark_use, mark_use + 2, json_call),
    )

    # Appended last: the F2-AC2 tool relay (owner decision 2026-10-31), relay grader 02.
    write(
        out,
        "pass1-cat-before-dispatch.jsonl",
        before_batch_count(done, cat_relay(ids, warn_text)),
    )
    v = list(done)
    after_first = index_of(v, '"text":"Async agent launched successfully.') + 1
    v[after_first:after_first] = cat_relay(ids, warn_text)
    write(out, "pass1-cat-after-dispatch.jsonl", v)
    write(
        out,
        "pass1-cat-empty.jsonl",
        before_batch_count(done, cat_relay(ids, "(Bash completed with no output)")),
    )
    # Mutation warn-in-report-only: the report repeats the WARN line, no `cat` ran.
    write(out, "pass1-warn-in-report-only.jsonl", complete(relayed_report))


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

    # ---- T2.4: report-only line families, the missing frame, the mismatch report ----
    # Appended last. Each variant swaps the conductor's return for another report: the
    # hand-back frame indents every report line by two spaces (an empty line becomes
    # "  ", as the frame's own notes show), and tool_use_result carries the raw text.
    head = "The report follows:\n"
    tail = "\nagentId: "

    def with_report(report: str) -> list[str]:
        event = json.loads(p2[hb])
        block = event["message"]["content"][0]["content"][0]
        start = block["text"].index(head) + len(head)
        stop = block["text"].index(tail)
        framed = "\n".join("  " + line for line in report.split("\n"))
        block["text"] = block["text"][:start] + framed + block["text"][stop:]
        event["tool_use_result"]["content"][1]["text"] = report
        v = list(p2)
        v[hb] = enc(event)
        return v

    event = json.loads(p2[hb])
    block = event["message"]["content"][0]["content"][0]
    frame = block["text"][block["text"].index("[Subagent hand-back]") :]
    frame = frame[: frame.index(head) + len(head)]
    block["text"] = block["text"].replace(frame, "")
    v = list(p2)
    v[hb] = enc(event)
    write(out, "pass2-no-handback.jsonl", v)

    passed = "> Pass 2 complete — instructions rendered for 1 source doc(s).\n>"
    audit_ok = "> Coverage audit: RESULT: OK — 1/1 actions reconciled."
    note = '"2026-10-24_1200_suggestions"'
    # Copied from evals/_lib/stubs.sh (DELETES, ATTACH); a test compares them to the kit.
    relays = (
        "- ⚠️ **Not deleted:** [[Meeting Notes Q3]] — the destination note was claimed "
        "by another approved item\n"
        "- ⚠️ **Not deleted:** [[Reading List]] — the related note could not be found\n"
        "- ⚠️ **Attachment not filed:** `100 Inbox/whiteboard.png` — kept in inbox: the "
        "owner chose not to file it over the occupied destination "
        "`Attachments/whiteboard.png`. No action needed unless you change your mind. To "
        "file it after all, tick Rename in the suggestions document and run "
        "`/inbox --pass2 --force` before you apply. If you have already applied, rename "
        "the attachment in the inbox and run `/inbox` again."
    )
    write(
        out,
        "pass2-withheld-relayed.jsonl",
        with_report(f"{passed}\n{audit_ok}\n\n{relays}"),
    )
    write(
        out,
        "pass2-relay-introduced.jsonl",
        with_report(
            f"{passed}\n{audit_ok}\n\nThe following items were withheld:\n{relays}"
        ),
    )
    write(
        out,
        "pass2-state-flip-failed.jsonl",
        with_report(f"{passed}\n{audit_ok}\n> state flip exited 1 for {note}."),
    )
    write(
        out,
        "pass2-stamped.jsonl",
        with_report(f"{passed}\n{audit_ok}\n> Stamped 2 acknowledged advisory(ies)."),
    )

    # The audit-mismatch-stops stop report: the audit's stdout as the stub prints it.
    gap = (
        "COVERAGE-GAP-91c2: suggestion s1 has no matching instruction "
        "(expected 1, found 0)"
    )
    fail = "RESULT: FAIL — count or coverage mismatch above."
    write(out, "pass2-mismatch-report.jsonl", with_report(f"> {gap}\n> {fail}"))
    write(
        out,
        "pass2-mismatch-fenced.jsonl",
        with_report(f"```\n{gap}\n{fail}\n```"),
    )
    write(
        out,
        "pass2-mismatch-labelled.jsonl",
        with_report(
            f"> {gap}\n>\n> Coverage audit: {fail}\n> coverage audit exited 1 for {note}."
        ),
    )
    write(
        out,
        "pass2-mismatch-status-sentence.jsonl",
        with_report(
            f"The coverage audit found a gap, so I stopped.\n> {gap}\n> {fail}"
        ),
    )


def variants(fixtures: Path, out: Path) -> None:
    pass1_variants(read_lines(fixtures / "pass1-spike.jsonl"), out)
    pass1_completions(read_lines(fixtures / "pass1-spike.jsonl"), out)
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
