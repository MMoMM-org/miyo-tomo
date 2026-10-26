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
#   delete notice        tomo/scripts/lib/render_md.py:838-854 (_render_withdrawn_delete_notice)
#                        reasons: tomo/scripts/lib/render_helpers.py:213-219
#   attachment notice    tomo/scripts/lib/render_md.py:857-890 (_render_skipped_asset_notice);
#                        reason (kind vault_collision_held, owner chose keep_in_inbox):
#                        tomo/scripts/lib/attachment_plan.py:150-154;
#                        remedy: tomo/scripts/lib/refusal_sentences.py:157,211-217
#                        (withheld_attachment_remedy)
#   relay files          tomo/scripts/instruction-render.py:270-271,981,1005 (next to the
#                        output dir; unlinked when empty, :317-320)
#   render success       tomo/scripts/instruction-render.py:1232-1241 (stderr; stdout empty);
#                        files: manifest.json :657, instructions.json :1171,
#                        instructions.md :1209, note <YYYY-MM-DD_HHMM>_<slug>.md :463,607
#   upload success       tomo/scripts/upload-rendered.py:207,215,224 (per-file lines),
#                        :241-249 (summary), all stderr, stdout empty; missing input
#                        :150-154 exit 2; timestamp from `generated` :99-113,170
#   state flip success   tomo/scripts/state-promoter.py _cli_flip: exit 0, prints nothing
#   routing plan         tomo/schemas/routing-plan.schema.json
# The conductor's argv comes from tomo/dot_claude/agents/synthesis-conductor.md
# Steps 1-3; the stubs accept any argv and only log it.
# bash 3.2 compatible.

stage_instance() {
  AUDIT_RESULT="${AUDIT_RESULT:-ok}"
  WITHHELD_DELETES="${WITHHELD_DELETES:-0}"
  WITHHELD_ATTACH="${WITHHELD_ATTACH:-0}"
  case "$AUDIT_RESULT" in ok|fail) ;; *)
    echo "stubs.sh: AUDIT_RESULT must be ok|fail, got '$AUDIT_RESULT'" >&2; return 1 ;; esac
  case "$WITHHELD_DELETES" in 0|1|2) ;; *)
    echo "stubs.sh: WITHHELD_DELETES must be 0|1|2, got '$WITHHELD_DELETES'" >&2; return 1 ;; esac
  case "$WITHHELD_ATTACH" in 0|1) ;; *)
    echo "stubs.sh: WITHHELD_ATTACH must be 0|1, got '$WITHHELD_ATTACH'" >&2; return 1 ;; esac
  local _stub_head
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
    "- ⚠️ **Attachment not filed:** `100 Inbox/whiteboard.png` — kept in inbox: the owner chose not to file it over the occupied destination `Attachments/whiteboard.png`. No action needed unless you change your mind. To file it after all, tick Rename in the suggestions document and run `/inbox --pass2 --force` before you apply. If you have already applied, rename the attachment in the inbox and run `/inbox` again.",
]
out_dir = pathlib.Path("tomo-tmp/rendered")
if "--output-dir" in sys.argv:
    out_dir = pathlib.Path(sys.argv[sys.argv.index("--output-dir") + 1])
out_dir.mkdir(parents=True, exist_ok=True)
note = "2026-10-24_0000_example.md"
(out_dir / note).write_text("# Example\n", encoding="utf-8")
(out_dir / "manifest.json").write_text(json.dumps([{"rendered_file": note}]), encoding="utf-8")
(out_dir / "instructions.json").write_text(json.dumps({"generated": "2026-10-24T00:00:00Z", "instructions": [{"id": "i1", "source": "s1"}]}), encoding="utf-8")
(out_dir / "instructions.md").write_text("# Instructions\n", encoding="utf-8")
for name, lines, n in (("withheld-deletes.md", DELETES, N_DELETES), ("withheld-attachments.md", ATTACH, N_ATTACH)):
    p = out_dir.parent / name
    if n > 0:
        p.write_text("\n".join(lines[:n]) + "\n", encoding="utf-8")
    else:
        p.unlink(missing_ok=True)
sys.stderr.write("[warn] withdrew delete act-LEAK7a1 (guard validate_destinations) run_id: 2026-10-25T00-00-00Z-c0ffee\n")
sys.stderr.write("[attach] skipped_assets kind=vault_collision_held action=act-LEAK7a2\n")
sys.stderr.write(
    f"instruction-render: rendered=1 actions=1 errors=0 out={out_dir}\n"
    f"  manifest={out_dir / 'manifest.json'}\n"
    f"  instructions.json={out_dir / 'instructions.json'}\n"
    f"  instructions.md={out_dir / 'instructions.md'}\n"
)
PY

  printf '%s' "$_stub_head" > scripts/instructions-diff.py
  if [ "$AUDIT_RESULT" = "fail" ]; then
    cat >> scripts/instructions-diff.py <<'PY'
# COVERAGE-GAP-91c2 is a synthetic marker (the real mismatch output is a [DIFF]/[MISSING]
# table, instructions-diff.py:719-752); only the two RESULT: lines are copied (:762-765).
print("COVERAGE-GAP-91c2: suggestion s1 has no matching instruction (expected 1, found 0)")
print("RESULT: FAIL — count or coverage mismatch above.")
sys.exit(1)
PY
  else
    cat >> scripts/instructions-diff.py <<'PY'
print("RESULT: OK — 1/1 actions reconciled.")
PY
  fi

  # upload-rendered: reads what the render stub wrote; uploads nothing.
  printf '%s' "$_stub_head" > scripts/upload-rendered.py
  cat >> scripts/upload-rendered.py <<'PY'
import pathlib
def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default
rendered = pathlib.Path(arg("--rendered-dir", "tomo-tmp/rendered"))
inbox = arg("--inbox", "100 Inbox/")
for required in ("manifest.json", "instructions.md", "instructions.json"):
    if not (rendered / required).is_file():
        sys.stderr.write(f"error: required file missing: {rendered / required}\n")
        sys.exit(2)
def join(name):
    return inbox.rstrip("/") + "/" + name
manifest = json.loads((rendered / "manifest.json").read_text(encoding="utf-8"))
generated = json.loads((rendered / "instructions.json").read_text(encoding="utf-8"))["generated"]
timestamp = generated[:10] + "_" + generated[11:13] + generated[14:16]
for entry in manifest:
    body = (rendered / entry["rendered_file"]).read_text(encoding="utf-8")
    sys.stderr.write(f"  [note] {join(entry['rendered_file'])} ({len(body)} chars)\n")
md_body = (rendered / "instructions.md").read_text(encoding="utf-8")
sys.stderr.write(f"  [note] {join(timestamp + '_instructions.md')} ({len(md_body)} chars)\n")
json_bytes = (rendered / "instructions.json").read_bytes()
sys.stderr.write(f"  [file] {join(timestamp + '_instructions.json')} ({len(json_bytes)} bytes)\n")
sys.stderr.write(f"upload-rendered: {len(manifest)} note(s) + 2 instruction artefact(s) written under {inbox}\n")
sys.stderr.write(f"  ↳ {timestamp}_instructions.md / .json\n")
PY

  # state-promoter: a successful flip prints nothing (exit 0).
  printf '%s' "$_stub_head" > scripts/state-promoter.py

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
