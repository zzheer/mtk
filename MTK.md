# MTK agent guide

Canonical public guide: <https://raw.githubusercontent.com/zzheer/mtk/refs/heads/preview/MTK.md>.

Prefer Homebrew-installed `mtk`, resolved through PATH, for routine shell and
terminal commands: `mtk COMMAND ... [resource and display limits]`. Use native handlers for
Git, ripgrep, GitHub CLI, tests, and builds. Unknown commands execute directly, preserving output and exit status within
MTK limits; use `mtk just`, `mtk python3`, `mtk fd`, `mtk node`, and `mtk ssh`. Do not substitute a source-checkout wrapper.
When unavailable or incompatible wrapping, filtered diagnostics, changed exit status, or wrapper
limits block authorized work, run the underlying command directly. No additional
permission is required solely to bypass MTK.

Keep output concise and preserve complete diagnostics. Apply CPU, memory,
concurrency, runtime, and storage limits separately from display filtering.

## Files

mtk ls . # Compact directory tree
mtk read file.rs # Smart file reading
mtk read file.rs -l aggressive # Signatures only (strips bodies)
mtk smart file.rs # 2-line heuristic code summary
mtk fd
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
mtk run <cmd> [args...] # Raw argv without RTK summaries; MTK logs/limits remain
mtk run -c '<script>' # Shell string via sh (cmd on Windows)
mtk run --shell fish -c '<script>' # Explicit shell for shell-specific syntax

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

Append resource and display limits to the command:

```bash
# Time limit (s, m, h)
mtk npm test --time-limit 30s
mtk cargo build --time-limit=5m

# Memory limit (RSS polling every 500ms)
mtk python3 data_processor.py --memory-limit 2G
mtk node script.js --mem-limit=500M

# CPU throttling (bundled corrected limiter; children included by default)
mtk ffmpeg -i input.mp4 output.mp4 --cpu-limit 50%
mtk python3 script.py --cpu-limit=50 --exclude-children

# Singleton (terminates previous instance with up to 5 retries)
mtk --singleton=server_sync ./sync.sh
mtk --singleton npm run dev  # Auto-derives lock key from command

# Singleton Wait (blocks until existing instance finishes)
mtk --singleton-wait=deploy ./deploy.sh
```

Only a final contiguous MTK flag suffix is extracted: `--time-limit`,
`--memory-limit` (alias `--mem-limit`), `--cpu-limit`, `--exclude-children`,
`--max-lines`, `--max-bytes`, and `--no-truncate`. Value flags accept both
separate values and `=VALUE`. Legacy prefix flags still work.
Duplicate limits use the last value, and suffix values override prefix values:

```bash
mtk --time-limit 60s cargo build --time-limit 30s # MTK uses 30s
```

A standalone `--` anywhere after `COMMAND` disables suffix extraction for that
invocation and preserves the wrapped arguments:

```bash
mtk python3 script.py -- --time-limit 30s # Passed through to the command
```

Keep trailing resource and display flags together at the end. Singleton flags
remain prefix-only:

```bash
mtk python3 worker.py --time-limit 60s --max-lines 100 --cpu-limit 50
```

CPU limits include the full descendant-tree depth on Darwin by default.
`--exclude-children` limits only the root process; timeout and memory cleanup
still cover the workload and its descendants.

Avoid nesting CPU-limited MTK commands: independent stop/resume controllers
can interfere with each other. When running the governor test suite, apply
`--exclude-children` to the outer test runner so each regression owns its CPU
controller; retain the outer timeout and memory limits.

## Device-local jobs

```bash
mtk jobs       # List this user's tracked workloads on this device
mtk stop --all # Stop tracked workloads and observed descendants
```

The private registry lives under `$XDG_STATE_HOME/mtk/jobs`, or
`~/.local/state/mtk/jobs` when unset, with `0700` directories and `0600` records.
It is separate from singleton coordination and needs no daemon. Before
signaling, MTK verifies the UID and high-resolution PID birth time. Cleanup
excludes unrelated processes, the managing command, and its ancestors, sends
TERM, then KILL to verified survivors, and waits only for a bounded interval.
Emergency signaling uses kernel group and identity checks independently of
process snapshots; capture errors still restore terminal settings.

Descendants are captured periodically. Observed surviving descendants remain
tracked after the root exits. Rapid detach/reparent between samples, or children
born after observers exit, can escape observation; this is not an absolute
guarantee of tracking every detached process.

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
mtk git diff --max-lines 500 --max-bytes 128KiB
mtk python3 script.py --no-truncate
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
`--max-bytes`, and `--no-truncate`. Resource
limits remain separate CLI flags; this config controls output display only.

Defaults: 200 lines / 32 KiB per stream. Each MTK clipping region has exact
`[truncated by mtk]`. Unique private `/tmp/mtk-*.log` contains complete wrapped
output only; stdout/stderr bytes follow observed arrival order. The final
filepath is on stderr. The log contains bytes after RTK processing: content RTK
removed cannot be recovered. `--no-truncate` still logs output and prints the
filepath. Display limits do not cap log size; manage retention and storage
separately.

Codex resolves Homebrew `/opt/homebrew/bin/mtk` through PATH. Existing hooks
need not be enabled; verify `command -v mtk` and `mtk --help` from its shell.

## Advanced exact output

Use `mtk run COMMAND ...` to bypass a native handler's RTK summary while
retaining MTK logging and resource limits. For complete displayed bytes:

```bash
mtk run git diff --no-truncate --time-limit 30s
```

The stderr log filepath footer still prints. `mp` aliases `mtk`; `mr` aliases
`mtk run`.

## Preferences

Prefer `mtk bun` for everyday tasks when Bun is appropriate.
Prefer `mtk fd` over `find`. Prefer `mtk rg` over `grep`.
Any unknown command not recognized as an internal mtk or native rtk subcommand
executes directly with its output and exit status preserved within MTK limits.

# Aliases

mr = mtk run
mpf = mtk fd
mrg = mtk rg
md = mtk docker
mpj = mtk just
mpnpm = mtk pnpm
mgh = mtk gh
mgit = mtk git
mp = mtk
mb = mtk bun
mpn = mtk node
mpd = mtk pnpm dlx
mpe = mtk pnpm exec
mnpm = mtk npm
mnpx = mtk npx
mssh = mtk ssh
mmd = mtk markitdown

mpp = mtk python3 # Standalone Python shortcut
