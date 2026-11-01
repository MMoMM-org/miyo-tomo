#!/bin/bash
# pass1-suggest-pipeline — SHARED_CTX_WARN=0 DUPLICATES=0 — a clean Pass 1 run, graded step by step from triage to the report.
set -e
SHARED_CTX_WARN=0
DUPLICATES=0
. "$(dirname "$0")/../_lib/pass1-stubs.sh"
stage_pass1_instance
