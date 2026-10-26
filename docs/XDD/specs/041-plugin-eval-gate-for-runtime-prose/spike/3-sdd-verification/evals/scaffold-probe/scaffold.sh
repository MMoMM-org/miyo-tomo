#!/bin/bash
{
  echo "dollar0=$0"
  echo "bash_source=${BASH_SOURCE[0]}"
  echo "pwd=$(pwd)"
  d="$(dirname "$0")"
  echo "dirname_listing:"; ls -la "$d" 2>&1
  echo "sibling:"; cat "$d/sibling.txt" 2>&1
} > probe.txt
