"""Add a relay probe case to the spike plugin: real notice lines, leak bait on stderr."""
import pathlib
import re

ROOT = pathlib.Path(__file__).parent / "tomo" / "evals"
SEED = ROOT / "audit-gates-delivery" / "scaffold.sh"
CASE = ROOT / "withheld-notices-relayed"

DELETES = [
    "- ⚠️ **Not deleted:** [[Meeting Notes Q3]] — the destination note was claimed by another approved item",
    "- ⚠️ **Not deleted:** [[Reading List]] — the related note could not be found",
]
ATTACH = [
    "- ⚠️ **Attachment not filed:** `100 Inbox/whiteboard.png` — the destination already holds a "
    "different file with this name. No action needed unless you change your mind. To file it after "
    "all, tick Rename in the suggestions document and run `/inbox --pass2 --force` before you apply. "
    "If you have already applied, rename the attachment in the inbox and run `/inbox` again.",
]
BAIT = (
    "[warn] withdrew delete act-LEAK7a1 (guard validate_destinations) run_id: 2026-10-25T00-00-00Z-evalLEAK\n"
    "[attach] skipped_assets kind=vault_collision_held action=act-LEAK7a2"
)


def js_escape(text: str) -> str:
    return re.sub(r"([.*+?^${}()|\[\]\\/])", r"\\\1", text)


def yaml_single(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


CASE.mkdir(parents=True, exist_ok=True)
(CASE / "graders").mkdir(exist_ok=True)
scaffold = SEED.read_text()
deletes_body = "\\n".join(DELETES)
attach_body = "\\n".join(ATTACH)
render_stub_extra = (
    "\ncat > tomo-tmp/withheld-deletes.md <<'RELAY'\n" + "\n".join(DELETES) + "\nRELAY\n"
    "cat > tomo-tmp/withheld-attachments.md <<'RELAY'\n" + "\n".join(ATTACH) + "\nRELAY\n"
)
bait_stub = (
    "stub instruction-render.py \"os.makedirs('tomo-tmp/rendered', exist_ok=True)\n"
    "json.dump({'instructions': [{'id': 'i1', 'source': 's1'}]}, open('tomo-tmp/rendered/instructions.json', 'w'))\n"
    "open('tomo-tmp/rendered/2026-10-24_0000_instructions.md', 'w').write('# Instructions\\\\n')\n"
    "sys.stderr.write('''" + BAIT + "\\\\n''')\n"
    "print('instruction-render: rendered=1 skipped=0 withheld_deletes=2 withheld_attachments=1')\"\n"
)
scaffold = re.sub(r'stub instruction-render\.py ".*?"\n', lambda _: bait_stub, scaffold, flags=re.S)
scaffold += render_stub_extra
(CASE / "scaffold.sh").write_text(scaffold)
(CASE / "scaffold.sh").chmod(0o755)
(CASE / "case.yaml").write_text(
    (ROOT / "audit-gates-delivery" / "case.yaml").read_text().replace(
        "name: audit-gates-delivery", "name: withheld-notices-relayed"
    )
)
graders = {
    "0-conductor-dispatched": "type: tool_used\ntool: Agent\ninput_match: 'synthesis-conductor'",
}
for i, line in enumerate(DELETES + ATTACH, start=1):
    graders[f"{i}-line-verbatim"] = f"type: regex\npattern: {yaml_single(js_escape(line))}\nmatch: contains"
graders["4-deletes-before-attachments-and-last"] = (
    "type: regex\npattern: "
    + yaml_single(js_escape(DELETES[-1]) + r"\s*\n\s*" + js_escape(ATTACH[0]) + r"\s*$")
    + "\nmatch: contains"
)
graders["5-no-leak"] = (
    "type: regex\npattern: 'run_id|evalLEAK|act-LEAK|validate_destinations|vault_collision_held|skipped_assets|\\[warn\\]|\\[attach\\]'"
    "\nmatch: not_contains"
)
for name, body in graders.items():
    (CASE / "graders" / f"{name}.md").write_text(f"---\n{body}\n---\n")
print("added", CASE)
