#!/usr/bin/env bash
set -euo pipefail

# mtk.sh - Root repository wrapper delegating to bin/mtk
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/bin/mtk" "$@"
