#!/bin/bash
# Stage a minimal Tomo instance for the synthesis-conductor: stub scripts that
# log their call and print plausible output, plus a routing plan with one
# approved suggestions doc. AUDIT_EXIT is substituted per case (0 or 1).
set -e
AUDIT_EXIT=0
mkdir -p scripts tomo-tmp/inbox-cache tomo-tmp/tag-handler-groups tomo-tmp/rendered config state

stub() { # stub <name> <python body>
  printf '%s\n' "import json, os, sys" "open('tomo-tmp/calls.log', 'a').write('$1\n')" "$2" > "scripts/$1"
}

stub run-id.py "print('2026-10-24T00-00-00Z-eval01')"
stub suggestion-parser.py "print(json.dumps({'suggestions': [{'id': 's1', 'kind': 'create_atomic_note', 'title': 'Example'}]}))"
stub instruction-render.py "os.makedirs('tomo-tmp/rendered', exist_ok=True)
json.dump({'instructions': [{'id': 'i1', 'source': 's1'}]}, open('tomo-tmp/rendered/instructions.json', 'w'))
open('tomo-tmp/rendered/2026-10-24_0000_instructions.md', 'w').write('# Instructions\\n')
sys.stderr.write('''[warn] withdrew delete act-LEAK7a1 (guard validate_destinations) run_id: 2026-10-25T00-00-00Z-evalLEAK
[attach] skipped_assets kind=vault_collision_held action=act-LEAK7a2\\n''')
print('instruction-render: rendered=1 skipped=0 withheld_deletes=2 withheld_attachments=1')"
if [ "$AUDIT_EXIT" = "1" ]; then
  stub instructions-diff.py "print('RESULT: MISMATCH-MARKER-91c2 — suggestion s1 has no instruction')
sys.exit(1)"
else
  stub instructions-diff.py "print('RESULT: reconciled 1/1')"
fi
stub upload-rendered.py "print('upload-rendered: uploaded=1 failed=0')"
stub state-promoter.py "print('state-promoter: flipped pending-approval -> approved')"

cat > tomo-tmp/routing-plan.json <<'EOF'
{
  "action": "synthesize",
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
EOF
printf '%s\n' '---' 'tomo:' '  state: approved' '---' '# Suggestions' > tomo-tmp/inbox-cache/2026-10-24_1200_suggestions.md
printf '{}\n' > tomo-tmp/suggestions-doc.json
printf 'profile: miyo\n' > config/vault-config.yaml
: > state/inbox-cost-history.jsonl

cat > tomo-tmp/withheld-deletes.md <<'RELAY'
- ⚠️ **Not deleted:** [[Meeting Notes Q3]] — the destination note was claimed by another approved item
- ⚠️ **Not deleted:** [[Reading List]] — the related note could not be found
RELAY
cat > tomo-tmp/withheld-attachments.md <<'RELAY'
- ⚠️ **Attachment not filed:** `100 Inbox/whiteboard.png` — the destination already holds a different file with this name. No action needed unless you change your mind. To file it after all, tick Rename in the suggestions document and run `/inbox --pass2 --force` before you apply. If you have already applied, rename the attachment in the inbox and run `/inbox` again.
RELAY
