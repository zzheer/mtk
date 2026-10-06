#!/usr/bin/env bash

# libexec/mtk-core.sh - Core library functions for mtk

is_rtk_subcommand() {
  case "$1" in
    ls|tree|read|smart|git|gh|glab|aws|psql|pnpm|err|test|json|deps|env|find|diff|log|\
    dotnet|docker|kubectl|oc|summary|grep|rg|ast-grep|init|wget|wc|gain|cc-economics|\
    config|jest|vitest|ctest|prisma|tsc|next|lint|prettier|format|playwright|cargo|npm|\
    npx|bun|bunx|curl|discover|session|telemetry|learn|run|recall|pipe|trust|\
    untrust|verify|ruff|sqlfluff|pytest|mypy|php|phpunit|phpstan|pest|paratest|ecs|pint|\
    phpt|rake|rubocop|rspec|pip|uv|deno|go|sbt|gt|golangci-lint|gradlew|mvn|mvnd|hook-audit|\
    rewrite|hook|help|-h|--help|-v|-vv|-vvv|--verbose|--ultra-compact|--skip-env|--version|-V)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

mtk_core_run() {
  if [[ $# -eq 0 ]]; then
    echo "mtk: missing command" >&2
    echo "Try 'mtk --help' for available commands." >&2
    return 2
  fi

  if [[ "$1" == "proxy" ]]; then
    echo "mtk: proxy was removed; use 'mtk COMMAND ...' or 'mtk run COMMAND ...'." >&2
    return 2
  fi

  if ! is_rtk_subcommand "$1"; then
    command "$@"
    return $?
  fi

  if ! command -v rtk >/dev/null 2>&1; then
    echo "mtk: required dependency 'rtk' not found in PATH" >&2
    echo "Please install rtk via Homebrew: brew install rtk" >&2
    return 127
  fi

  # Check if subcommand is an official native RTK command
  if is_rtk_subcommand "$1"; then
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
  else
    command "$@"
  fi
}
