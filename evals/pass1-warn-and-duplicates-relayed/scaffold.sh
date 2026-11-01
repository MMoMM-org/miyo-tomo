#!/bin/bash
# pass1-warn-and-duplicates-relayed — SHARED_CTX_WARN=1 DUPLICATES=1 — the shared-context WARN and one converted duplicate MOC must reach the user.
set -e
SHARED_CTX_WARN=1
DUPLICATES=1
. "$(dirname "$0")/../_lib/pass1-stubs.sh"
stage_pass1_instance
