#!/usr/bin/env bash
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [[ -L "$SOURCE" ]]; do
  DIR="$(cd "$(dirname "$SOURCE")" && pwd)"
  TARGET="$(readlink "$SOURCE")"
  if [[ "$TARGET" == /* ]]; then
    SOURCE="$TARGET"
  else
    SOURCE="$DIR/$TARGET"
  fi
done
ROOT="$(cd "$(dirname "$SOURCE")/.." && pwd)"
# shellcheck source=mtk.sh
source "$ROOT/scripts/mtk.sh"
if [[ "${1:-}" == "ai" ]]; then
  shift
  exec python3 "$ROOT/scripts/mtk-ai" "$@"
fi
case "${1:-}" in
  generate-image|generate-audio|generate-video)
    MEDIA_COMMAND="$1"
    shift
    exec python3 "$ROOT/scripts/mtk-media" "$MEDIA_COMMAND" "$@"
    ;;
esac
mtk "$@"
