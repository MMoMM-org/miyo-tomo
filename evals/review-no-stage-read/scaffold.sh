#!/bin/bash
# review-no-stage-read — /review 2026-03 on a small synthetic month stage: setup present, no open review, a new read, one round of two digesters and one carryover. The main session must read no stage file and dispatch the round as typed, foreground Agent() calls in one message; every agent replies one line.
set -e
. "$(dirname "$0")/../_lib/review-stubs.sh"
stage_review_instance
