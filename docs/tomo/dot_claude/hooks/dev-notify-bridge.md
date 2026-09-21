# dev-notify-bridge.sh — WHY

Forwards Claude Code notification events from inside the container to the
`dev-notify-bridge` process on the host, so a session waiting for input raises
a desktop notification.

## The Body Is Built With `jq`, Never Interpolation (v0.3.0)

WHY the `curl -d` payload goes through `jq -n --arg`:

`$MESSAGE` and `$TITLE` both originate from Claude, and both were pasted into a
JSON string literal by shell interpolation. A double quote or a backslash in
either one produces malformed JSON, the bridge answers HTTP 400, and the
trailing `|| true` swallows it. There is no log line, no stderr, no retry — the
notification simply never arrives and nothing records that one was lost.

Reported by Kouzou on 2026-09-03 (their `f3efda8` fixes the same defect in the
hook Tomo's was copied from), verified against the running bridge with the
message `pfad C:\temp und "zitat" hier`:

```
{"title": "[Tomo] Claude Code", "message": "pfad C:\temp und "zitat" hier"}
→ HTTP 400
```

WHY the silence is the real defect and the escaping only its trigger: both
failure paths are mute by design. `curl -s` prints nothing on a 4xx, and
`|| true` guarantees exit 0 so the hook never disturbs the session. That is the
right posture for a notification hook — a broken bridge must not break the
session — but it means any body-construction bug is invisible forever. `jq`
removes the only way the body can be malformed rather than adding a report path
that would have to stay quiet anyway.

WHY `jq` specifically: it is already a hard dependency two lines above, where
the hook parses `$INPUT`. The fix adds nothing to the container.

## Two Flags Folded Into The Same Change

WHY `--max-time 3`: the previous `curl -s` had no timeout at all. A host bridge
that is reachable but wedged blocks the hook — and therefore the session — for
curl's default connect timeout.

WHY `> /dev/null` on stdout: `-s` silences curl's progress meter, not the
response body, which otherwise lands in the hook's own output.

## Testing It Requires A Stub

WHY `tests/test-notify-bridge-hook.sh` asserts on a captured body rather than an
exit code: the hook ends in `|| true` and always exits 0, so an exit-code
assertion passes against the broken version too. Kouzou made exactly that point
when reporting the defect. The test puts a stub `curl` first on `PATH`, captures
whatever followed `-d`, and validates that with `jq` — which also means it needs
no bridge running.

Proven RED against the pre-fix hook: 10 of 13 assertions fail, including both
round-trip families and the two flag checks.

## Instance Labelling Is Deliberate And Unchanged

WHY the `TOMO_INSTANCE_NAME` → `basename $TOMO_INSTANCE_DIR` → bare `[Tomo]`
chain stays as it is: it resolves the label the same way the statusline does, so
a multi-instance user can tell which Tomo is waiting. Kouzou copied this
approach for their own host-session hook rather than the reverse.

## Delivery

`update-tomo.sh` ships hooks through `add_versioned`, keyed on this file's own
`# version:` header (`scripts/update-tomo.sh:399`). Bumping the header is what
makes an existing instance receive a change — there is no launcher or template
version gating it.
