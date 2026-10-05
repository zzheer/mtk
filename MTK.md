# MTK agent guide

Canonical public guide: <https://raw.githubusercontent.com/zzheer/mtk/refs/heads/preview/MTK.md>.

Prefer Homebrew-installed `mtk`, resolved through PATH, for routine shell and
terminal commands. Use `mtk proxy` when it preserves command behavior and useful
diagnostics. Do not substitute a source-checkout wrapper. When unavailable or
incompatible wrapping, filtered diagnostics, changed exit status, or wrapper
limits block authorized work, run the underlying command directly. No additional
permission is required solely to bypass MTK.

Keep output concise and preserve complete diagnostics. Apply CPU, memory,
concurrency, runtime, and storage limits separately from display filtering.

## Files

mtk ls . # Compact directory tree
mtk read file.rs # Smart file reading
mtk read file.rs -l aggressive # Signatures only (strips bodies)
mtk smart file.rs # 2-line heuristic code summary
mtk proxy fd
mtk diff file1 file2 # Condensed diff (exit 0: identical, 1: different, 2: read error)
mtk rg Compact ripgrep - runs rg natively, same output filter as grep
mtk ast-grep Compact ast-grep - runs ast-grep natively, groups matches by file

## Git

mtk git status # Compact status
mtk git log -n 10 # One-line commits
mtk git diff # Condensed diff
mtk git add # -> "ok"
mtk git commit -m "msg" # -> "ok abc1234"
mtk git push # -> "ok main"
mtk git pull # -> "ok 3 files +10 -2"

## GitHub CLI

mtk gh pr list # Compact PR listing
mtk gh pr view 42 # PR details + checks
mtk gh issue list # Compact issue listing
mtk gh run list # Workflow run status

## Test Runners

mtk jest # Jest compact (failures only)
mtk vitest # Vitest compact (failures only)
mtk playwright test # E2E results (failures only)
mtk pytest # Python tests (-90%)
mtk go test # Go tests (NDJSON, -90%)
mtk cargo test # Cargo tests (-90%)
mtk rspec # RSpec tests (JSON, -60%+)
mtk err <cmd> [args...] # Direct argv execution, errors/warnings only
mtk test <cmd> [args...] # Direct argv execution, failures only (-90%)
mtk err --shell fish '<script>' # Explicit shell for shell-specific syntax

## Build & Lint

mtk lint # ESLint grouped by rule/file
mtk lint biome # Supports other linters
mtk sqlfluff lint # SQL linting (JSON, -75%)
mtk sqlfluff lint models/ # Lint a specific directory (pass path after `lint`)
mtk tsc # TypeScript errors grouped by file
mtk next build # Next.js build compact
mtk prettier --check . # Files needing formatting
mtk cargo build # Cargo build (-80%)
mtk cargo clippy # Cargo clippy (-80%)
mtk ruff check # Python linting (JSON, -80%)
mtk golangci-lint run # Go linting (JSON, -85%)

## Package Managers

mtk pnpm list # Compact dependency tree
mtk npm run with filtered output (strip boilerplate)
mtk uv run pytest # Preserve uv env, keep program output
mtk pip list # Python packages (auto-detect uv)
mtk pip outdated # Outdated packages
mtk bundle install # Ruby gems (strip Using lines)
mtk prisma generate # Schema generation (no ASCII art)

## Containers

mtk docker ps # Compact container list
mtk docker images # Compact image list
mtk docker logs <container> # Deduplicated logs
mtk docker compose ps # Compose services

## Data & Analytics

mtk json config.json # Structure without values
mtk deps # Dependencies summary
mtk env -f AWS # Filtered env vars
mtk log app.log # Deduplicated logs
mtk curl <url> # Truncate + save full output
mtk wget <url> # Download, strip progress bars
mtk summary <cmd> [args...] # Direct argv execution + heuristic summary
mtk run <cmd> [args...] # Raw direct execution (no filtering/tracking)
mtk run -c '<script>' # Shell string via sh (cmd on Windows)
mtk run --shell fish -c '<script>' # Explicit shell for shell-specific syntax
mtk proxy <command> # Raw passthrough + tracking

## Others

mtk go Go commands with compact output
bun Bun runtime commands with compact output
bunx bunx with passthrough + auto-filter
npx npx with intelligent routing (tsc, eslint, prisma -> specialized filters)

## Token Savings Analytics

mtk gain # Summary stats
mtk gain --graph # ASCII graph (last 30 days)
mtk gain --history # Recent command history
mtk gain --daily # Day-by-day breakdown
mtk gain --all --format json # JSON export for dashboards

mtk discover # Find missed savings opportunities
mtk discover --all --since 7 # All projects, last 7 days

mtk session # Show mtk adoption across recent sessions

## Resource Governance & Limits

Apply process constraints to any mtk, rtk, or proxied command:

```bash
# Time limit (s, m, h)
mtk --time-limit 30s npm test
mtk --time-limit 5m cargo build

# Memory limit (RSS polling every 500ms)
mtk --memory-limit 2G python3 data_processor.py
mtk --memory-limit 500M node script.js

# CPU throttling (bundled corrected limiter; children included by default)
mtk --cpu-limit 50% ffmpeg -i input.mp4 output.mp4
mtk --cpu-limit 50 --exclude-children proxy python3 script.py

# Singleton (terminates previous instance with up to 5 retries)
mtk --singleton=server_sync ./sync.sh
mtk --singleton npm run dev  # Auto-derives lock key from command

# Singleton Wait (blocks until existing instance finishes)
mtk --singleton-wait=deploy ./deploy.sh
```

## Conversion & MarkItDown

mtk markitdown document.pdf # Convert PDF/Word/Excel/Audio to Markdown (via uvx/binary)
mtk markitdown document.docx -o doc.md # Save converted markdown
mmd presentation.pptx # Alias for `mtk markitdown`

## Assistant Hooks

mtk hook codex # Configure global Codex CLI PreToolUse hook (~/.codex/hooks.json)
mtk hook codex --local # Configure project-local Codex hook (.codex/hooks.json)

## Web Search & Resilient Fetch

mtk search-web "rust language" # DuckDuckGo web search (free, 0 tokens, native binary)
mtk search-web "query" --limit 10 # Up to 50 results (default 5)
mtk search-web "query" --json # Output raw search-cli/v1 JSON envelope
mtk fetch https://example.com # Stealth browser fetch (curl-cffi) -> Markdown (markitdown)
mtk fetch https://news.ycombinator.com -o hn.md # Save markdown directly to file

## Dependency Architecture & Health

mtk doctor # Audits all runtimes, proxies, limiters, and scrapers
just install-search # Installs independent zzheer/tap/duckduckgo-tools
just test # Offline, bounded regression tests
just audit # Audits Homebrew formula locally

- Homebrew formula/dependency installation is defined by `packaging/manifest.json`.
- Search uses installed `duckduckgo-tools`; no source checkout or Instant Answer fallback.
- Corrected GPL limiter source and notices ship with MTK; Homebrew builds private `mtk-cpulimit`.
- MarkItDown runs on demand through installed binary or `uvx`.

## Output and logs

```bash
mtk --max-lines 500 --max-bytes 128KiB git diff
mtk --no-truncate proxy python3 script.py
```

Display settings load from `~/.config/mtk/config.json`. When `XDG_CONFIG_HOME` is
set, MTK uses `$XDG_CONFIG_HOME/mtk/config.json` instead. Create the directory and
JSON file to change defaults globally:

```json
{
  "max_lines": 500,
  "max_bytes": "128KiB",
  "truncate": true
}
```

`max_lines` accepts a positive integer. `max_bytes` accepts a positive integer
number of bytes or a size string such as `"32KiB"` or `"128KiB"`. `truncate`
accepts a JSON boolean; `false` disables display clipping. Keys are optional.
A missing config file uses 200 lines, 32 KiB, and truncation enabled. Invalid
JSON or invalid settings exit nonzero before the wrapped command starts.
Config must be a regular JSON file: FIFOs, devices, and other nonregular files
are rejected before command execution; symlinks to regular files are allowed.
CLI flags override the corresponding config settings: `--max-lines`,
`--max-bytes`, and `--no-truncate`. Flags must precede the command. Resource
limits remain separate CLI flags; this config controls output display only.

Defaults: 200 lines / 32 KiB per stream. Each MTK clipping region has exact
`[truncated by mtk]`. Unique private `/tmp/mtk-*.log` contains complete wrapped
output only; stdout/stderr bytes follow observed arrival order. The final
filepath is on stderr. RTK summaries remain unchanged in the log. Flags must
precede the command; `--no-truncate` still logs output and prints the filepath.

Codex resolves Homebrew `/opt/homebrew/bin/mtk` through PATH. Existing hooks
need not be enabled; verify `command -v mtk` and `mtk --help` from its shell.

## Preferences

Instead of using `mtk proxy python3`, I prever that you use bun with `mtk bun` for everyday tasks.
Prefer `mtk proxy fd` over `find`. Prefer `mtk rg` over `grep`.
Any unknown command not recognized as an internal mtk or native rtk subcommand automatically falls back to `mtk proxy <command>`.

# Aliases

mr = mtk run
mpf = mtk proxy fd
mrg = mtk rg
md = mtk docker
mpj = mtk proxy just
mpnpm = mtk pnpm
mgh = mtk gh
mgit = mtk git
mp = mtk proxy
mb = mtk bun
mpn = mtk proxy node
mpd = mtk pnpm dlx
mpe = mtk pnpm exec
mnpm = mtk npm
mnpx = mtk npx
mssh = mtk proxy ssh
mmd = mtk markitdown
