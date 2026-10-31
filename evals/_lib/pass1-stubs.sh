#!/bin/bash
# pass1-stubs.sh — stub kit for the Pass 1 (action: suggest) eval cases under
# evals/. Sourced by each Pass 1 case's scaffold.sh, which sets two variables
# first:
#   SHARED_CTX_WARN=0|1   DUPLICATES=0|1
# then calls `stage_pass1_instance`. cwd = the eval workspace; nothing outside
# it is written and nothing under tomo/ is read (the workspace has no tomo/
# tree). The conductor file is copied from the assembled plugin: $0 is the
# case's scaffold.sh at <plugin>/evals/<case>/scaffold.sh, so the agents dir is
# $(dirname "$0")/../../agents/ (spec 043 ADR-6).
#
# Output formats below are COPIED from Tomo's scripts, not generated; when one
# of those changes, re-check the copy:
#   triage argv          tomo/dot_claude/commands/inbox.md:25 ($ARGUMENTS: the
#                        /inbox flags :14-19); plan file tomo/scripts/inbox-triage.py:1925
#   triage summary       tomo/scripts/inbox-triage.py:1950-1965 (stderr)
#   routing plan         tomo/schemas/routing-plan.schema.json
#   read-routing-plan    tomo/scripts/read-routing-plan.py:111-153 (modes, stdout),
#                        :135 (inbox_path loses its trailing /), :64 and :93-96
#                        (errors, exit 1), :86-87 (--size)
#   read-config-field    tomo/scripts/read-config-field.py:64-72 (stdout; ERROR to stderr, exit 1)
#   run id               tomo/scripts/run-id.py:22-31 (--out file + stdout)
#   shared-ctx WARN      tomo/scripts/shared-ctx-builder.py:731-738 (stderr)
#   shared-ctx lines     tomo/scripts/shared-ctx-builder.py:855-859 (reconcile, stderr),
#                        :903-920 (summary, stderr); ctx keys :880-888
#   item result file     tomo/scripts/lib/item_key.py:39-70 (to_filename, copied
#                        into analyst-stub.py); keys tomo/schemas/item-result.schema.json
#                        plus the SDD's run_id/status/sections
#   state line           tomo/scripts/state-update.py:91-101 (entry), :122 (append),
#                        :125-128 (stderr line)
#   suggestions doc      tomo/scripts/suggestions-reducer.py:2891-2911 (doc),
#                        :2775-2780 (section), :2552 (S<nn> ids)
#   reducer summary      tomo/scripts/suggestions-reducer.py:2963-2978 (stderr)
#   rendered markdown    tomo/scripts/suggestions-render.py:33-57 (frontmatter; tomo
#                        block tomo/scripts/lib/doc_frontmatter.py:120-125), :60-72
#                        (header), :88-104 (summary), :148-160 (suggestions),
#                        :163-198 (proposed MOCs)
#   wire JSON            tomo/scripts/suggestions-render.py:293-333 (_wire_note), :545-557
#                        (payload); digest tomo/scripts/lib/render_md.py:396-412; keys and
#                        schema_version tomo/schemas/suggestions-wire.schema.json
#   render summary       tomo/scripts/suggestions-render.py:597-606 (stderr)
#   kado-write-file      tomo/scripts/kado-write-file.py:164-165 (op by --vault
#                        extension), :205-209 (stderr), :139-144 (input errors, exit 2)
#   mark-captured        tomo/scripts/mark-captured.py:171 (per item), :237-241
#                        (summary, stderr), :133 (no done items)
# Each stub's argv is checked against what tomo/dot_claude/skills/suggest-handling/
# SKILL.md steps 1-6 pass (and inbox.md:25 for triage); anything else prints
# `stub <name>: unexpected argv: …` and exits 2. The stand-in agent
# evals/_lib/inbox-analyst.stub.md runs scripts/analyst-stub.py "<path>"
# "<item_key>" "<run_id>".
# bash 3.2 compatible.

stage_pass1_instance() {
  SHARED_CTX_WARN="${SHARED_CTX_WARN-0}"
  DUPLICATES="${DUPLICATES-0}"
  case "$SHARED_CTX_WARN" in 0|1) ;; *)
    echo "pass1-stubs.sh: SHARED_CTX_WARN must be 0|1, got '$SHARED_CTX_WARN'" >&2; return 1 ;; esac
  case "$DUPLICATES" in 0|1) ;; *)
    echo "pass1-stubs.sh: DUPLICATES must be 0|1, got '$DUPLICATES'" >&2; return 1 ;; esac
  local _conductor _stub_head
  _conductor="$(dirname "$0")/../../agents/suggestion-conductor.md"
  if [ ! -f "$_conductor" ]; then
    echo "pass1-stubs.sh: conductor not found at $_conductor" >&2; return 1
  fi
  mkdir -p scripts tomo-tmp config profiles .claude/agents
  cp "$_conductor" .claude/agents/suggestion-conductor.md

  # Every stub starts with the same header: log name + argv, strict argv check.
  _stub_head='import json, os, sys
NAME = os.path.basename(sys.argv[0])[:-3]
os.makedirs("tomo-tmp", exist_ok=True)
with open("tomo-tmp/calls.log", "a") as _f:
    _f.write(os.path.basename(sys.argv[0]) + " " + " ".join(sys.argv[1:]) + "\n")


def unexpected():
    print("stub %s: unexpected argv: %s" % (NAME, " ".join(sys.argv[1:])), file=sys.stderr)
    sys.exit(2)


def parse(valued=(), switches=(), required=()):
    args, out, i = sys.argv[1:], {}, 0
    while i < len(args):
        a = args[i]
        if a in valued and i + 1 < len(args) and a not in out:
            out[a] = args[i + 1]
            i += 2
        elif a in switches and a not in out:
            out[a] = True
            i += 1
        else:
            unexpected()
    for r in required:
        if r not in out:
            unexpected()
    return out


RUN_ID = "2026-10-30T00-00-00Z-c0ffee"
GENERATED = "2026-10-30T00:00:00Z"
'
  # $2 (optional) is one constant line placed right after the header.
  _write_stub() {
    printf '%s' "$_stub_head" > "scripts/$1"
    if [ -n "${2-}" ]; then printf '%s\n' "$2" >> "scripts/$1"; fi
    cat >> "scripts/$1"
  }

  cat > tomo-tmp/routing-plan.fixture.json <<'JSON'
{
  "action": "suggest",
  "timestamp": "2026-10-30T00:00:00Z",
  "inbox_path": "100 Inbox/",
  "fresh_sources": [
    {"path": "100 Inbox/Alpha.md"},
    {"path": "100 Inbox/Places/Dresden.md"},
    {"path": "100 Inbox/Gamma.md"}
  ],
  "has_audio": false,
  "approved_suggestions": [],
  "approved_fan": [],
  "approved_moc_proposals": [],
  "force_atomic_items": [],
  "pending_approval": [],
  "idle_reasons": [],
  "drift_indicators": [],
  "handled": []
}
JSON

  _write_stub inbox-triage.py <<'PY'
import shutil
parse(switches=("--pass1", "--force", "--recover"))
shutil.copy("tomo-tmp/routing-plan.fixture.json", "tomo-tmp/routing-plan.json")
print(
    "[inbox-triage] suggest in 412ms — md=3 audio=0 new=3 to_process=3 "
    "approved_sugg=0 approved_fan=0 approved_moc=0 fan_items=0 pending=0 "
    "drift=0 kado_calls=4 docs_cached=0",
    file=sys.stderr,
)
PY

  _write_stub read-routing-plan.py <<'PY'
o = parse(valued=("--field", "--size", "--batch"), switches=("--sources", "--batch-count"))
mode = set(o)
if mode not in ({"--field"}, {"--batch-count", "--size"}, {"--sources", "--batch", "--size"}):
    unexpected()
for flag in ("--size", "--batch"):
    if flag in o and not o[flag].isdigit():
        unexpected()
plan = json.load(open("tomo-tmp/routing-plan.json"))
if "--field" in o:
    node = plan
    for seg in o["--field"].split("."):
        if not isinstance(node, dict) or seg not in node:
            raise SystemExit("read-routing-plan: no such field: " + o["--field"])
        node = node[seg]
    if o["--field"] == "inbox_path" and isinstance(node, str):
        node = node.rstrip("/")
    if isinstance(node, bool):
        node = "true" if node else "false"
    elif node is None:
        node = ""
    elif isinstance(node, (dict, list)):
        node = json.dumps(node, ensure_ascii=False)
    print(node)
    sys.exit(0)
size = int(o["--size"])
if size < 1:
    raise SystemExit("read-routing-plan: --size must be 1 or greater")
paths = [s["path"] for s in plan.get("fresh_sources") or []]
total = (len(paths) + size - 1) // size
if "--batch-count" in o:
    print(total)
    sys.exit(0)
n = int(o["--batch"])
if n < 1 or n > total:
    raise SystemExit("read-routing-plan: --batch %d out of range (1..%d)" % (n, total))
for p in paths[(n - 1) * size: n * size]:
    print(p)
PY

  _write_stub read-config-field.py <<'PY'
o = parse(valued=("--field", "--default"), required=("--field",))
values = {"tomo.suggestions.parallel": "2", "profile": "miyo"}
field = o["--field"]
if field in values:
    sys.stdout.write(values[field] + "\n")
elif "--default" in o:
    sys.stdout.write(o["--default"] + "\n")
else:
    print("ERROR: field not found: " + field, file=sys.stderr)
    sys.exit(1)
PY

  _write_stub run-id.py <<'PY'
o = parse(valued=("--out",), required=("--out",))
with open(o["--out"], "w") as f:
    f.write(RUN_ID + "\n")
sys.stdout.write(RUN_ID + "\n")
PY

  _write_stub shared-ctx-builder.py "SHARED_CTX_WARN = $SHARED_CTX_WARN" <<'PY'
o = parse(
    valued=("--cache", "--vault-config", "--profiles-dir", "--run-id", "--output"),
    required=("--cache", "--vault-config", "--profiles-dir", "--run-id", "--output"),
)
mocs = [
    {"path": "Atlas/Maps/Places MOC.md", "title": "Places MOC", "topics": ["places", "cities"],
     "is_classification": False},
    {"path": "Atlas/Maps/Travel MOC.md", "title": "Travel MOC", "topics": ["travel"],
     "is_classification": False},
]
ctx = {
    "schema_version": "1",
    "run_id": o["--run-id"],
    "mocs": mocs,
    "tag_prefixes": [],
    "classification_keywords": {},
    "asset_folder": "Attachments",
    "placeholder_targets": [],
}
data = (json.dumps(ctx, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
with open(o["--output"], "wb") as f:
    f.write(data)
print("[shared-ctx] reconcile: cache clean (2 MOC(s) verified)", file=sys.stderr)
if SHARED_CTX_WARN:
    print(
        "WARN: 2 active tracker field(s) have no keywords; matching falls back to "
        "guesswork and cannot suppress false positives: mood, sleep. Run /tomo-setup "
        "trackers to fill them, or set active: false on the ones you do not use.",
        file=sys.stderr,
    )
names_bytes = len(json.dumps([m["title"] for m in mocs]))
detail_bytes = len(json.dumps(mocs, separators=(",", ":")))
print(
    "mocs_total=2 mocs_after_reconcile=2 mocs_reconcile_dropped=0 eligible=2 "
    "excluded=0 collisions=0 names_bytes=%d detail_bytes=%d tag_prefixes_included=0 "
    "classification_categories=0 placeholder_targets=0 daily_notes_enabled=False "
    "asset_folder=Attachments bytes=%d run_id=%s"
    % (names_bytes, detail_bytes, len(data), o["--run-id"]),
    file=sys.stderr,
)
PY

  _write_stub analyst-stub.py <<'PY'
import hashlib
import re

if len(sys.argv) != 4 or any(a.startswith("-") or not a for a in sys.argv[1:]):
    unexpected()
path, item_key, run_id = sys.argv[1:]

# Copy of tomo/scripts/lib/item_key.py:30-31,39-70 (to_filename).
_FORBIDDEN_CHARS = frozenset('\\/:*?"<>|\x00')
_READABLE_MAX_LEN = 40


def to_filename(key):
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
    stem = key.rsplit("/", 1)[-1]
    stem = re.sub(r"\.[^.]+$", "", stem)
    stem = "".join("-" if c in _FORBIDDEN_CHARS or c.isspace() else c for c in stem)
    stem = stem.lower().strip("-") or "item"
    readable = stem[:_READABLE_MAX_LEN].strip("-") or "item"
    return "%s-%s.result.json" % (readable, digest)


stem = path.rsplit("/", 1)[-1]
if stem.endswith(".md"):
    stem = stem[:-3]
result = {
    "schema_version": "1",
    "stem": stem,
    "item_key": item_key,
    "path": path,
    "run_id": run_id,
    "status": "done",
    "type": "atomic_note",
    "type_confidence": 0.9,
    "sections": [{
        "kind": "create_atomic_note",
        "title": stem,
        "summary": "Notes on %s, worth keeping as one atomic note." % stem,
    }],
}
os.makedirs("tomo-tmp/items", exist_ok=True)
with open(os.path.join("tomo-tmp/items", to_filename(item_key)), "w") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
entry = {
    "run_id": run_id, "stem": stem, "item_key": item_key, "path": path,
    "status": "done", "attempts": 1, "started_at": GENERATED,
    "completed_at": GENERATED, "error": None,
}
with open("tomo-tmp/inbox-state.jsonl", "a") as f:
    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
print("state-update: item_key=%s stem=%s status=done attempts=1 run_id=%s"
      % (item_key, stem, run_id), file=sys.stderr)
PY

  _write_stub suggestions-reducer.py "DUPLICATES = $DUPLICATES" <<'PY'
import glob

o = parse(valued=("--run-id", "--profile", "--output"),
          required=("--run-id", "--profile", "--output"))
state_lines = []
if os.path.exists("tomo-tmp/inbox-state.jsonl"):
    state_lines = [x for x in open("tomo-tmp/inbox-state.jsonl").read().splitlines() if x.strip()]
result_files = sorted(glob.glob("tomo-tmp/items/*.result.json"))
if len(result_files) < len(state_lines):
    print("stub suggestions-reducer: %d result file(s) in tomo-tmp/items for %d state "
          "line(s); the reduce ran before every analyst finished"
          % (len(result_files), len(state_lines)), file=sys.stderr)
    sys.exit(2)
results = {}
for rf in result_files:
    r = json.load(open(rf))
    results[r["item_key"]] = r
last = {}
for line in state_lines:
    e = json.loads(line)
    last[e["item_key"]] = e
done = [e for e in last.values() if e.get("status") == "done" and e.get("run_id") == o["--run-id"]]
failed = [e for e in last.values() if e.get("status") == "failed" and e.get("run_id") == o["--run-id"]]
sections, unreadable = [], 0
for idx, e in enumerate(done, start=1):
    r = results.get(e["item_key"])
    if r is None:
        unreadable += 1
        continue
    sid = "S%02d" % idx
    sec = r["sections"][0]
    rendered = (
        "**Source:** [[%s]]\n"
        "**Suggested name:** %s\n"
        "**Type:** atomic note (confidence %.2f)\n"
        "**Destination:** `Atlas/Notes/`\n"
        "**Parent MOC:** [[Travel MOC]]    ← change the parent MOC if needed\n"
        "**Tags:** #topic/travel\n"
        "**Why:** %s\n"
        "\n"
        "- [x] Accept\n"
        "- [ ] Skip\n"
        "- [ ] Force Atomic Note"
        % (e["path"][:-3], sec["title"], r["type_confidence"], sec["summary"])
    )
    sections.append({
        "id": sid,
        "stem": e["stem"],
        "item_key": e["item_key"],
        "actions": [{"kind": "create_atomic_note", "suggestion_id": sid, "rendered_md": rendered}],
    })
proposed_mocs = [{
    "topic": "Saxony",
    "name": "Saxony MOC",
    "parent": "Travel MOC",
    "items": [s["id"] for s in sections],
    "note_titles": [s["stem"] for s in sections],
    "reason": "Three new notes share the topic and no MOC covers it yet.",
    "tags": ["topic/travel"],
}]
if DUPLICATES:
    proposed_mocs.append({
        "topic": "Places",
        "name": "Places MOC",
        "parent": "Travel MOC",
        "items": [s["id"] for s in sections[1:2]],
        "note_titles": [s["stem"] for s in sections[1:2]],
        "reason": "Places MOC already exists in the vault; offered as an unticked link.",
        "tags": [],
    })
doc = {
    "schema_version": "1",
    "generated": GENERATED,
    "run_id": o["--run-id"],
    "profile": o["--profile"],
    "conventions": {"parent_marker": "up", "peer_marker": "related", "moc_suffix": " MOC"},
    "doc_variant": "primary",
    "source_items": len(done) + len(failed),
    "sections": sections,
    "daily_notes_updates": [],
    "rendered_daily_updates_md": "",
    "decision_precedence_note": "",
    "attachments_preamble": "",
    "proposed_mocs": proposed_mocs,
    "needs_attention": [],
    "folder_listing_calls": 1,
    "distinct_destination_folders": 1,
}
with open(o["--output"], "w") as f:
    json.dump(doc, f, ensure_ascii=False, indent=2)
print(
    "suggestions-reducer: done=%d failed=%d unreadable_results=%d sections=%d "
    "daily_notes_updates=0 daily_notes_missing=0 tag_handler_updates=0 "
    "tag_handler_stale_dropped=0 tag_handler_guards=ok:0/target_missing:0/"
    "marker_missing:0/target_unresolved:0 classification_candidates_dropped=0 "
    "duplicate_proposals_converted=%d proposed_mocs=%d out=%s"
    % (len(done), len(failed), unreadable, len(sections), DUPLICATES,
       len(proposed_mocs), o["--output"]),
    file=sys.stderr,
)
PY

  _write_stub suggestions-render.py <<'PY'
import hashlib

o = parse(valued=("--input", "--output", "--json-output"),
          required=("--input", "--output", "--json-output"))
d = json.load(open(o["--input"]))
rid = d["run_id"]
lines = [
    "---",
    "type: tomo-suggestions",
    "generated: '%s'" % d["generated"],
    "tomo_version: 0.1.0",
    "profile: %s" % d["profile"],
    "source_items: %d" % d["source_items"],
    "run_id: %s" % rid,
    "tomo:",
    "  doc_type: suggestions",
    "  state: pending-approval",
    "  run_id: %s" % rid,
    "  updated_at: '%s'" % d["generated"],
    "---",
    "",
    "# Inbox Suggestions — %s" % d["generated"][:10],
    "",
    "- [ ] Approved — check this box when you have finished reviewing, then run "
    "`/inbox` for Pass 2",
    "",
    "## Summary",
    "",
    "- Items processed: %d" % d["source_items"],
    "- Sections: %d" % len(d["sections"]),
    "- Proposed MOCs: %d" % len(d["proposed_mocs"]),
    "- Needs attention: %d" % len(d["needs_attention"]),
    "",
]
if d["sections"]:
    lines += ["## Suggestions", ""]
    for s in d["sections"]:
        for a in s["actions"]:
            lines.append("### %s — %s" % (a["suggestion_id"], s["stem"]))
            lines.append(a["rendered_md"])
            lines.append("")
if d["proposed_mocs"]:
    lines += ["## Proposed MOCs", ""]
    for pm in d["proposed_mocs"]:
        lines += [
            "### Proposed MOC: %s" % pm["topic"],
            "- **Name:** %s    ← edit this to rename the MOC before approving" % pm["name"],
            "- **Parent:** [[%s]]    ← change parent MOC if needed" % pm["parent"],
            "- **Supporting notes:** %s" % ", ".join(pm["note_titles"]),
            "- **Why:** %s" % pm["reason"],
        ]
        if pm["tags"]:
            lines.append("- **Suggested tags:** %s" % ", ".join(pm["tags"]))
        lines += [
            "- **Decision:**",
            "  - [ ] Approve (create this MOC with the Name above)",
            "",
        ]
with open(o["--output"], "w") as f:
    f.write("\n".join(lines))
wire = {
    "schema_version": "4",
    "generated": d["generated"],
    "run_id": rid,
    "profile": d["profile"],
    "source_items": d["source_items"],
    "suggestions": [
        {"id": a["suggestion_id"], "stem": s["stem"], "item_key": s["item_key"],
         "title": s["stem"], "summary": None, "template": "t_note_tomo",
         "location": "Atlas/Notes", "tags": ["topic/travel"], "audio_peer": None,
         "attachments": [], "decision": "approve", "keep_source": False,
         "delete_source": False, "force_atomic": False, "suppressed": False,
         "worthiness": 0.9,
         "candidate_mocs": [{"path": "Atlas/Maps/Travel MOC.md", "selected": True,
                             "anchor": None, "source": "tomo"}]}
        for s in d["sections"] for a in s["actions"]
    ],
    "proposed_mocs": [
        {"id": "M%02d" % i, "topic": pm["topic"], "name": pm["name"], "parent": pm["parent"],
         "member_ids": pm["items"], "tags": pm["tags"], "reason": pm["reason"],
         "decision": "skip"}
        for i, pm in enumerate(d["proposed_mocs"], start=1)
    ],
    "daily_updates": [],
    "tag_handler_groups": [],
    "attachment_conflicts": [],
}
wire["emit_digest"] = "sha256:" + hashlib.sha256(
    json.dumps(wire, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    .encode("utf-8")).hexdigest()
with open(o["--json-output"], "w") as f:
    json.dump(wire, f, ensure_ascii=False, indent=2)
print(
    "suggestions-render: sections=%d daily=0 tag_handler=0 mocs=%d out=%s"
    % (len(d["sections"]), len(d["proposed_mocs"]), o["--output"]),
    file=sys.stderr,
)
PY

  _write_stub kado-write-file.py <<'PY'
o = parse(valued=("--local", "--vault"), required=("--local", "--vault"))
try:
    data = open(o["--local"], "rb").read()
except OSError as exc:
    print("error: cannot read input: %s" % exc, file=sys.stderr)
    sys.exit(2)
if not data:
    print("error: input is empty, refusing to write", file=sys.stderr)
    sys.exit(2)
op = "note" if o["--vault"].lower().endswith(".md") else "file"
print("kado-write-file: %s (%d bytes, op=%s) → %s" % (o["--local"], len(data), op, o["--vault"]),
      file=sys.stderr)
PY

  _write_stub mark-captured.py <<'PY'
o = parse(valued=("--state", "--run-id"), required=("--state", "--run-id"))
last = {}
if os.path.exists(o["--state"]):
    for line in open(o["--state"]).read().splitlines():
        if line.strip():
            e = json.loads(line)
            last[e["item_key"]] = e
done = [e for e in last.values() if e.get("status") == "done" and e.get("run_id") == o["--run-id"]]
if not done:
    print("mark-captured: no done items to mark", file=sys.stderr)
    sys.exit(0)
for e in done:
    print("  [%s] marking %s" % (e["stem"], e["path"]), file=sys.stderr)
print("mark-captured: marked=%d errors=0 declined=0 skipped_non_md=0 squelched=0" % len(done),
      file=sys.stderr)
PY

  printf 'profile: miyo\ntomo:\n  suggestions:\n    parallel: 2\n' > config/vault-config.yaml
  printf 'version: 1\nmap_notes:\n  - path: Atlas/Maps/Places MOC.md\n  - path: Atlas/Maps/Travel MOC.md\n' \
    > config/discovery-cache.yaml
  printf 'name: miyo\n' > profiles/miyo.yaml
  unset -f _write_stub
}
