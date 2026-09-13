#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-all}" in
  syntax) python3 scripts/validate-source.py ;;
  python|go) python3 scripts/run-integration.py "$1" ;;
  all) python3 scripts/validate-source.py; python3 scripts/run-integration.py ;;
  *) echo 'Usage: scripts/ci.sh [syntax|python|go|all]' >&2; exit 2 ;;
esac
