#!/bin/bash
# Spike 043: stage a Pass 1 (action: suggest) instance with every script the
# Pass 1 path calls stubbed. Formats are copied from the real scripts (see the
# spec 043 research, Decisions Log 2026-10-30). bash 3.2 compatible.
set -e
mkdir -p scripts tomo-tmp config profiles state

HEAD='import json, os, sys
os.makedirs("tomo-tmp", exist_ok=True)
with open("tomo-tmp/calls.log", "a") as _f:
    _f.write(os.path.basename(sys.argv[0]) + " " + " ".join(sys.argv[1:]) + "\n")
def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default
'

stub() { printf '%s' "$HEAD" > "scripts/$1"; cat >> "scripts/$1"; }

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
  "drift_indicators": []
}
JSON

stub inbox-triage.py <<'PY'
import shutil
shutil.copy("tomo-tmp/routing-plan.fixture.json", "tomo-tmp/routing-plan.json")
print("[inbox-triage] suggest in 12ms — md=3 new=3", file=sys.stderr)
PY

stub read-routing-plan.py <<'PY'
plan = json.load(open("tomo-tmp/routing-plan.json"))
size = int(arg("--size", "5"))
paths = [s["path"] for s in plan.get("fresh_sources", [])]
if "--field" in sys.argv:
    field = arg("--field")
    if field not in plan:
        raise SystemExit("read-routing-plan: no such field: " + field)
    value = plan[field]
    print(value.rstrip("/") if field == "inbox_path" else value)
elif "--batch-count" in sys.argv:
    print((len(paths) + size - 1) // size)
elif "--sources" in sys.argv:
    n = int(arg("--batch"))
    chunk = paths[(n - 1) * size: n * size]
    if not chunk:
        raise SystemExit("read-routing-plan: batch %d out of range" % n)
    print("\n".join(chunk))
PY

stub read-config-field.py <<'PY'
values = {"tomo.suggestions.parallel": "2", "profile": "miyo"}
field = arg("--field")
if field in values:
    print(values[field])
elif "--default" in sys.argv:
    print(arg("--default"))
else:
    print("ERROR: field not found: " + field, file=sys.stderr)
    sys.exit(1)
PY

stub run-id.py <<'PY'
rid = "2026-10-30T00-00-00Z-c0ffee"
if "--out" in sys.argv:
    open(arg("--out"), "w").write(rid + "\n")
print(rid)
PY

stub shared-ctx-builder.py <<'PY'
open(arg("--output"), "w").write("{}\n")
print("WARN: 2 active tracker field(s) have no keywords; matching falls back to guesswork and cannot suppress false positives: mood, sleep. Run /tomo-setup trackers to fill them, or set active: false on the ones you do not use.", file=sys.stderr)
print("[shared-ctx] reconcile: cache clean (12 MOC(s) verified)", file=sys.stderr)
print("mocs_total=12 bytes=2048 run_id=" + str(arg("--run-id")), file=sys.stderr)
PY

stub analyst-stub.py <<'PY'
PY

stub suggestions-reducer.py <<'PY'
open(arg("--output"), "w").write("{}\n")
print("suggestions-reducer: done=3 failed=0 unreadable_results=0 sections=3 daily_notes_updates=0 daily_notes_missing=0 tag_handler_updates=0 tag_handler_stale_dropped=0 tag_handler_guards=ok:0/target_missing:0/marker_missing:0/target_unresolved:0 classification_candidates_dropped=0 duplicate_proposals_converted=1 proposed_mocs=1 out=" + arg("--output"), file=sys.stderr)
PY

stub suggestions-render.py <<'PY'
open(arg("--output"), "w").write("# Suggestions\n")
open(arg("--json-output"), "w").write("{}\n")
print("suggestions-render: sections=3 daily=0 tag_handler=0 mocs=1 out=" + arg("--output"), file=sys.stderr)
PY

stub kado-write-file.py <<'PY'
local, vault = arg("--local"), arg("--vault")
op = "file" if local.endswith(".json") else "note"
print("kado-write-file: %s (%d bytes, op=%s) → %s" % (local, os.path.getsize(local), op, vault), file=sys.stderr)
PY

stub mark-captured.py <<'PY'
print("mark-captured: marked=3 errors=0 declined=0 skipped_non_md=0 squelched=0", file=sys.stderr)
PY

printf 'profile: miyo\n' > config/vault-config.yaml
printf 'version: 1\n' > config/discovery-cache.yaml
printf 'name: miyo\n' > profiles/miyo.yaml
mkdir -p .claude/agents
cp "$(dirname "$0")/../../agents/suggestion-conductor.md" .claude/agents/suggestion-conductor.md
