#!/usr/bin/env bash
# MessageDisplay hook — highlight Obsidian [[wikilinks]] in chat output.
# version: 0.1.0
#
# DISPLAY-ONLY: only what is rendered on screen changes; the transcript and the
# text Claude reads back stay the original (bare) form. This lets the model emit
# bare wikilinks everywhere — including into vault notes via kado-write — while
# the reader still sees them visually set off.
#
# Safe by design: if the input field is unknown/empty, or jq/perl are missing,
# the hook makes NO change (original message shown). It can never blank output.
# It wraps each [[...]] in backticks but skips any already adjacent to a backtick
# so pre-formatted `[[...]]` are not double-wrapped.
set -uo pipefail

command -v jq   >/dev/null 2>&1 || exit 0
command -v perl >/dev/null 2>&1 || exit 0

input="$(cat)"

# Field carrying the assistant text. If wrong/empty -> exit without output ->
# original shown.
text="$(printf '%s' "$input" | jq -r '.delta // empty' 2>/dev/null)"
[ -z "$text" ] && exit 0

# Wrap [[...]] in backticks unless already backticked. UTF-8 aware (-CSAD),
# whole-input slurp (-0777). Link text must not contain ] or a newline.
new="$(printf '%s' "$text" | perl -CSAD -0777 -pe 's/(?<!`)(\[\[[^\]\n]*?\]\])(?!`)/`$1`/g' 2>/dev/null)"
[ -z "$new" ] && exit 0
[ "$new" = "$text" ] && exit 0

jq -cn --arg dc "$new" '{hookSpecificOutput:{hookEventName:"MessageDisplay",displayContent:$dc}}'
