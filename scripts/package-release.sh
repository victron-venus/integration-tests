#!/usr/bin/env bash
# Local source-package adapter for the shared release CLI.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/package_source.py "$@"
