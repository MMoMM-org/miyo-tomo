# WHY: hashi-hook-scan.py (script)

> Rationale for decisions in `tomo/scripts/hashi-hook-scan.py`.

## Deterministic Classifier, Not LLM Judgment

WHY: The risk tier of a generated hook is decided by a regex script, not by asking the LLM "is this safe?". An LLM judgment drifts between runs and between models — the same hook could be green one run and red the next, which is unacceptable for a safety classification users rely on. A deterministic scanner gives a stable, auditable verdict and can be unit-tested in both directions (green stays green, dangerous escalates to red) as the MiYo Constitution requires for permission/safety logic.

## Heuristic Tripwire, Not a Security Boundary

WHY: The scanner is a pattern-matcher, not a sandbox or a parser. Obfuscated exfiltration (dynamic dispatch, string-built requires, novel APIs) can slip past it. This is intentional and acceptable because the scanner is one layer: the user-facing disclaimer owns the residual risk, and Hashi's own policy gate (Disabled/Ask/Enabled) plus disclosure modal are the runtime controls. The script's job is to catch the obvious-dangerous cases and force them into the skill's red branch, not to prove safety. The docstring states this limit so no future maintainer mistakes it for a guarantee.

## Comment Stripping Preserves Line Numbers

WHY: Commented-out danger (`// require('child_process')`) must not trip the classifier — that produced false-positive reds in early hand-testing. Block and line comments are blanked before matching, but the blanking preserves newline count so reported finding line numbers still point at the real source line. String literals are deliberately NOT stripped: a dangerous token hidden inside a string is rare, and a false-positive red is the safe direction for a tripwire.

## fs Read vs Write Split

WHY: A bare `require('fs')` is not inherently dangerous — reading a file is yellow, writing/deleting is red. The classifier distinguishes the two by pairing the fs require with the presence of write-family methods (`writeFile`, `unlink`, `rm`, `rename`, `createWriteStream`, …). Treating all fs use as red would over-flag benign read-only hooks; treating it all as yellow would under-flag destructive ones. The split keeps the tier proportional to actual capability.

## Mass-Change Is Orthogonal to Tier

WHY: `mass_change` is reported as a separate boolean, not folded into the tier, because a hook can be tier-green (Obsidian API only) and still be high-impact when it mutates every note in a vault-wide loop. Collapsing it into the tier would either hide the loop risk (if green wins) or falsely brand single-file Obsidian hooks as dangerous (if it forced red). Keeping it orthogonal lets the skill warn on a green-but-sweeping hook without misclassifying its capability.
