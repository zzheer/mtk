#!/usr/bin/env bash

# libexec/mtk-core.sh - Core library functions for mtk

mtk_core_run() {
  if [[ $# -eq 0 ]]; then
    echo "mtk: missing command" >&2
    echo "Try 'mtk --help' for available commands." >&2
    return 2
  fi

  if ! command -v rtk >/dev/null 2>&1; then
    echo "mtk: required dependency 'rtk' not found in PATH" >&2
    echo "Please install rtk via Homebrew: brew install rtk" >&2
    return 127
  fi

  local has_help=0
  for arg in "$@"; do
    if [[ "$arg" == "--help" || "$arg" == "-h" || "$arg" == "help" ]]; then
      has_help=1
      break
    fi
  done

  if [[ $has_help -eq 1 ]]; then
    command rtk "$@" | sed -e 's/rtk/mtk/g' -e 's/RTK/MTK/g'
  else
    command rtk "$@"
  fi
}
