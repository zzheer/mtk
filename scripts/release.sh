#!/usr/bin/env bash
set -euo pipefail

# Package locally; --url hashes an already-published archive's exact bytes.
# Never writes a tap, source formula, or GitHub build output.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ulimit -t 60
if [[ $# -eq 0 ]]; then
  set -- 0.1.0 --local
fi
exec python3 "$REPO_ROOT/scripts/package.py" "$@"
