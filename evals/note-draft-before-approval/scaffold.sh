#!/bin/bash
# note-draft-before-approval — NOTE_DRAFTS=none NOTE_DELIVER=delivered — the source note fills every point of the one candidate template, so /note asks no question round; the draft (note.md) and its header must be printed before the approval question, and deliver must never run without approval.
set -e
NOTE_DRAFTS=none
NOTE_DELIVER=delivered
. "$(dirname "$0")/../_lib/note-stubs.sh"
stage_note_instance
