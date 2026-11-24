#!/bin/bash
# review-stubs.sh — stub kit for the /review eval case `review-no-stage-read`
# (spec 047 T6.4). Sourced by the case's scaffold.sh, which then calls
# `stage_review_instance`. cwd = the eval workspace; nothing outside it is
# written and nothing under tomo/ is read (the workspace has no tomo/ tree).
# The skill, the command and the three review agents come from the assembled
# plugin and run for real; only the scripts are stubs.
#
# The run: `/review 2026-03` with the month setup present and no open review,
# a new read (continued false) of a small synthetic month — three days with
# content (2026-03-03, -04, -10), one created note, the previous month found,
# the previous quarter missing — so no question round runs and step 5 plans
# one round: digesters for 2026-W10 and 2026-W11 and one carryover.
#
# The stage tomo-tmp/review/2026-03_review/ is written from
# review-stage.json next to this file: exactly what lib/review_stage.render
# writes for that read (tests/test_eval_review_no_stage_read.py regenerates
# and compares it). The agents read and write it for real.
#
# Stub outputs (one ASCII JSON line, exit 0; any other call: exit 2 and
# "stub: unexpected call" on stderr):
#   review-session.py start --args=…       START_OUTPUT (shape of the
#                                          review-session.py docstring, start)
#   review-read.py --period 2026-03 --kind month --stem 2026-03_review [--fresh]
#                                          READ_OUTPUT (review-read.py
#                                          docstring, new read)
#   review-digest.py plan --stem 2026-03_review
#                                          PLAN_OUTPUT: the real plan on the
#                                          staged stage (the test compares)
#   review-digest.py check --stem 2026-03_review
#                                          CHECK_OUTPUT: the real check after
#                                          valid digests and carryover (the
#                                          test compares); it reports passed
#                                          whatever the agents wrote
#   review-doc.py write --stem 2026-03_review --proposals …
#                                          WRITE_OUTPUT (review-doc.py
#                                          docstring, written)

START_OUTPUT='{"status": "ok", "request": {"kind": "month", "period": "2026-03", "year_inferred": false, "source": "arg", "start": "2026-03-01", "end": "2026-03-31"}, "setup": {"week": "present", "month": "present", "quarter": "present"}, "open_reviews": [], "skipped_review_docs": []}'
READ_OUTPUT='{"status": "ok", "stem": "2026-03_review", "period": {"kind": "month", "name": "2026-03", "start": "2026-03-01", "end": "2026-03-31"}, "continued": false, "read_id": "2026-11-24T09-00-00Z-a1b2c3", "read_at": "2026-11-24T09:00:00Z", "stage": "tomo-tmp/review/2026-03_review", "units": 6, "report": {"days": [{"date": "2026-03-03", "dailies": [{"path": "Calendar/Daily/2026-03-03.md", "state": "found"}], "duplicate": false, "linked": []}, {"date": "2026-03-04", "dailies": [{"path": "Calendar/Daily/2026-03-04.md", "state": "found"}], "duplicate": false, "linked": []}, {"date": "2026-03-10", "dailies": [{"path": "Calendar/Daily/2026-03-10.md", "state": "found"}], "duplicate": false, "linked": []}], "day_after": {"date": "2026-04-01", "dailies": []}, "task_notes": [], "weekly_status": "none-found", "weekly_notes": [], "growth": {"created": 1, "mocs_changed": 0, "mocs_linked_by_new": 0, "moc_folders": [], "kado_none": false}, "previous": [{"kind": "month", "name": "2026-02", "role": "previous-month", "path": "Calendar/Monthly/2026-02.md", "state": "found", "partly_read": false}, {"kind": "quarter", "name": "2025-Q4", "role": "previous-quarter", "path": null, "state": "missing", "partly_read": false}], "calls": 41, "retried": 0, "waited_s": 0, "not_read": [], "kado_empty": [], "advice": []}, "nothing_to_review": false}'
PLAN_OUTPUT='{"status": "ok", "stem": "2026-03_review", "read_id": "2026-11-24T09-00-00Z-a1b2c3", "read_at": "2026-11-24T09:00:00Z", "ready": false, "rounds": [[{"agent": "review-digester", "unit": "2026-W10", "days": ["2026-03-03", "2026-03-04"], "day_files": ["days/2026-03-03.json", "days/2026-03-04.json"], "growth_files": [], "weekly_note": null, "sections": false, "section_files": [], "out": "digests/2026-W10.json", "cap_bytes": 8192}, {"agent": "review-digester", "unit": "2026-W11", "days": ["2026-03-10"], "day_files": ["days/2026-03-10.json"], "growth_files": ["growth/2026-03-10.json"], "weekly_note": null, "sections": false, "section_files": [], "out": "digests/2026-W11.json", "cap_bytes": 8192}, {"agent": "review-carryover", "previous_files": ["previous/month-2026-02.json"], "out": "carryover.json", "cap_bytes": 12288}]], "done": [], "not_condensed": [], "carryover_state": "pending", "proposer": {"inputs": ["context.json"], "out": "proposals.json", "carried": false}}'
CHECK_OUTPUT='{"status": "ok", "stem": "2026-03_review", "units": {"2026-W10": {"state": "passed"}, "2026-W11": {"state": "passed"}}, "carryover": {"state": "passed", "notes": [{"path": "Calendar/Monthly/2026-02.md", "state": "passed", "items": 1}]}, "retry": [], "not_condensed": [], "carry_failed": false, "ready": true, "proposer": {"inputs": ["context.json", "digests/2026-W10.json", "digests/2026-W11.json", "carryover.json"], "out": "proposals.json", "carried": true}}'
WRITE_OUTPUT='{"status": "written", "stem": "2026-03_review", "doc_path": "100 Inbox/2026-03 Review.md", "target": "Calendar/Monthly/2026-03.md", "target_exists": true, "counts": {"done": 1, "open": 1, "themes": 1, "growth": 1}, "rejected": [], "previous": [{"kind": "month", "name": "2026-02", "state": "found", "carried": true}, {"kind": "quarter", "name": "2025-Q4", "state": "missing", "carried": false}], "calls": 4}'

stage_review_instance() {
    REVIEW_STAGE_JSON="$(dirname "$0")/../_lib/review-stage.json" \
    START_OUTPUT="$START_OUTPUT" READ_OUTPUT="$READ_OUTPUT" PLAN_OUTPUT="$PLAN_OUTPUT" \
    CHECK_OUTPUT="$CHECK_OUTPUT" WRITE_OUTPUT="$WRITE_OUTPUT" \
    python3 - <<'PY'
import json
import os
from pathlib import Path

STEM = "2026-03_review"
stage = Path("tomo-tmp/review") / STEM
for name, text in json.loads(Path(os.environ["REVIEW_STAGE_JSON"]).read_text(encoding="utf-8")).items():
    path = stage / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

Path("config").mkdir(exist_ok=True)
Path("config/vault-config.yaml").write_text("review:\n  language: en\n", encoding="utf-8")

HEAD = (
    "#!/usr/bin/env python3\n"
    "import sys\n"
    "argv = sys.argv[1:]\n"
    "def opt(name):\n"
    "    for i, a in enumerate(argv):\n"
    "        if a == name and i + 1 < len(argv):\n"
    "            return argv[i + 1]\n"
    "        if a.startswith(name + '='):\n"
    "            return a[len(name) + 1:]\n"
    "    return None\n"
    "def done(out):\n"
    "    sys.stdout.write(out + '\\n')\n"
    "    sys.exit(0)\n"
)
TAIL = "sys.stderr.write('stub: unexpected call\\n')\nsys.exit(2)\n"
STUBS = {
    "review-session.py": "if argv[:1] == ['start'] and opt('--args') is not None:\n    done(START)\n",
    "review-read.py": (
        "if (opt('--period'), opt('--kind'), opt('--stem')) == ('2026-03', 'month', STEM) "
        "and len([a for a in argv if a not in ('--fresh',)]) in (6, 3):\n    done(READ)\n"
    ),
    "review-digest.py": (
        "if argv[:1] == ['plan'] and opt('--stem') == STEM:\n    done(PLAN)\n"
        "if argv[:1] == ['check'] and opt('--stem') == STEM:\n    done(CHECK)\n"
    ),
    "review-doc.py": (
        "if argv[:1] == ['write'] and opt('--stem') == STEM and opt('--proposals'):\n    done(WRITE)\n"
    ),
}
outputs = {k: os.environ[f"{k}_OUTPUT"] for k in ("START", "READ", "PLAN", "CHECK", "WRITE")}
consts = f"STEM = {STEM!r}\n" + "".join(f"{k} = {v!r}\n" for k, v in outputs.items())
Path("scripts").mkdir(exist_ok=True)
for name, body in STUBS.items():
    Path("scripts", name).write_text(HEAD + consts + body + TAIL, encoding="utf-8")
PY
}
