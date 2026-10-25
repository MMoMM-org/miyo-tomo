"""Render real relay lines with Tomo's own renderers, for the relay probe fixture."""
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[6] / "tomo" / "scripts"))
from lib import render_helpers, render_md  # noqa: E402

guards = list(render_helpers._USER_FACING_WITHDRAWAL_REASONS)
print("GUARDS", guards)
w1 = {"source_path": "100 Inbox/Meeting Notes Q3.md", "causes": [{"guard": guards[0]}]}
w2 = {"source_path": "100 Inbox/Reading List.md", "causes": [{"guard": guards[-1]}]}
print(render_md._render_withdrawn_delete_notice(w1))
print(render_md._render_withdrawn_delete_notice(w2))
asset = {"source": "100 Inbox/whiteboard.png", "reason": "the destination already holds a different file with this name",
         "kind": "vault_collision_held", "destination": "Attachments/whiteboard.png"}
print(render_md._render_skipped_asset_notice(asset))
