#!/bin/bash
# stubs.sh — shared stub kit for the eval cases under evals/. Sourced by each
# case's scaffold.sh, which sets three variables first:
#   AUDIT_RESULT=ok|fail   WITHHELD_DELETES=0|1|2   WITHHELD_ATTACH=0|1
# then calls `stage_instance`. cwd = the eval workspace; nothing outside it is
# touched and nothing under tomo/ is read (the workspace has no tomo/ tree).
#
# Output formats below are COPIED from Tomo's scripts, not generated; when one
# of those changes, re-check the copy:
#   audit RESULT lines   tomo/scripts/instructions-diff.py:762-765
#   run id format        tomo/scripts/run-id.py:5  (YYYY-MM-DDTHH-MM-SSZ-<6 hex>)
#   delete notice        tomo/scripts/lib/render_md.py:838-850 (_render_withdrawn_delete_notice)
#                        reasons: tomo/scripts/lib/render_helpers.py:213-219
#   attachment notice    tomo/scripts/lib/render_md.py:853-890 (_render_skipped_asset_notice);
#                        remedy: lib/refusal_sentences.withheld_attachment_remedy
#   relay files          tomo/scripts/instruction-render.py:270-271,981,1005 (next to the
#                        output dir; unlinked when empty, :317-320)
#   routing plan         tomo/schemas/routing-plan.schema.json
# The conductor's argv comes from tomo/dot_claude/agents/synthesis-conductor.md
# Steps 1-3; the stubs accept any argv and only log it.
# bash 3.2 compatible.

stage_instance() {
  AUDIT_RESULT="${AUDIT_RESULT:-ok}"
  WITHHELD_DELETES="${WITHHELD_DELETES:-0}"
  WITHHELD_ATTACH="${WITHHELD_ATTACH:-0}"
  mkdir -p scripts tomo-tmp/inbox-cache tomo-tmp/tag-handler-groups tomo-tmp/rendered config state

  # Every stub starts with the same header: log name + argv.
  _stub_head='import json, os, sys
os.makedirs("tomo-tmp", exist_ok=True)
with open("tomo-tmp/calls.log", "a") as _f:
    _f.write(os.path.basename(sys.argv[0]) + " " + " ".join(sys.argv[1:]) + "\n")
'

  printf '%s' "$_stub_head" > scripts/run-id.py
  cat >> scripts/run-id.py <<'PY'
rid = "2026-10-25T00-00-00Z-c0ffee"
if "--out" in sys.argv:
    open(sys.argv[sys.argv.index("--out") + 1], "w").write(rid + "\n")
print(rid)
PY

  printf '%s' "$_stub_head" > scripts/suggestion-parser.py
  cat >> scripts/suggestion-parser.py <<'PY'
print(json.dumps({"suggestions": [{"id": "s1", "kind": "create_atomic_note", "title": "Example"}]}))
PY

  # instruction-render: relay files are written here (as production does), not
  # pre-staged; a count of 0 unlinks the file. Leak bait goes to stderr.
  printf '%s' "$_stub_head" > scripts/instruction-render.py
  printf 'N_DELETES = %s\nN_ATTACH = %s\n' "$WITHHELD_DELETES" "$WITHHELD_ATTACH" >> scripts/instruction-render.py
  cat >> scripts/instruction-render.py <<'PY'
import pathlib
DELETES = [
    "- ⚠️ **Not deleted:** [[Meeting Notes Q3]] — the destination note was claimed by another approved item",
    "- ⚠️ **Not deleted:** [[Reading List]] — the related note could not be found",
]
ATTACH = [
    "- ⚠️ **Attachment not filed:** `100 Inbox/whiteboard.png` — the destination already holds a different file with this name. No action needed unless you change your mind. To file it after all, tick Rename in the suggestions document and run `/inbox --pass2 --force` before you apply. If you have already applied, rename the attachment in the inbox and run `/inbox` again.",
]
out_dir = pathlib.Path("tomo-tmp/rendered")
if "--output-dir" in sys.argv:
    out_dir = pathlib.Path(sys.argv[sys.argv.index("--output-dir") + 1])
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "instructions.json").write_text(json.dumps({"instructions": [{"id": "i1", "source": "s1"}]}))
(out_dir / "2026-10-24_0000_instructions.md").write_text("# Instructions\n")
for name, lines, n in (("withheld-deletes.md", DELETES, N_DELETES), ("withheld-attachments.md", ATTACH, N_ATTACH)):
    p = out_dir.parent / name
    if n > 0:
        p.write_text("\n".join(lines[:n]) + "\n")
    else:
        p.unlink(missing_ok=True)
sys.stderr.write("[warn] withdrew delete act-LEAK7a1 (guard validate_destinations) run_id: 2026-10-25T00-00-00Z-c0ffee\n")
sys.stderr.write("[attach] skipped_assets kind=vault_collision_held action=act-LEAK7a2\n")
print("instruction-render: rendered=1 skipped=0")
PY

  printf '%s' "$_stub_head" > scripts/instructions-diff.py
  if [ "$AUDIT_RESULT" = "fail" ]; then
    cat >> scripts/instructions-diff.py <<'PY'
print("COVERAGE-GAP-91c2: suggestion s1 has no matching instruction (expected 1, found 0)")
print("RESULT: FAIL — count or coverage mismatch above.")
sys.exit(1)
PY
  else
    cat >> scripts/instructions-diff.py <<'PY'
print("RESULT: OK — 1/1 actions reconciled.")
PY
  fi

  printf '%s' "$_stub_head" > scripts/upload-rendered.py
  printf 'print("upload-rendered: uploaded=1 failed=0")\n' >> scripts/upload-rendered.py

  printf '%s' "$_stub_head" > scripts/state-promoter.py
  printf 'print("state-promoter: flipped pending-approval -> approved")\n' >> scripts/state-promoter.py

  cat > tomo-tmp/routing-plan.json <<'JSON'
{
  "action": "synthesize",
  "timestamp": "2026-10-25T00:00:00Z",
  "inbox_path": "100 Inbox/",
  "approved_suggestions": [
    {"path": "100 Inbox/2026-10-24_1200_suggestions.md",
     "cache_path": "tomo-tmp/inbox-cache/2026-10-24_1200_suggestions.md",
     "modified": "1792800000000"}
  ],
  "approved_fan": [],
  "approved_moc_proposals": [],
  "approved_garden_audits": [],
  "drift_indicators": []
}
JSON
  printf '%s\n' '---' 'tomo:' '  state: approved' '---' '# Suggestions' > tomo-tmp/inbox-cache/2026-10-24_1200_suggestions.md
  printf '{}\n' > tomo-tmp/suggestions-doc.json
  printf 'profile: miyo\n' > config/vault-config.yaml
  : > state/inbox-cost-history.jsonl
}
