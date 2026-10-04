## Installation

brew install rtk

## Repo

https://github.com/rtk-ai/rtk

## Git

rtk ls . # Compact directory tree
rtk read file.rs # Smart file reading
rtk read file.rs -l aggressive # Signatures only (strips bodies)
rtk smart file.rs # 2-line heuristic code summary
rtk find "\*.rs" . # Compact find results
rtk grep "pattern" . # Grouped search results
rtk diff file1 file2 # Condensed diff (exit 0: identical, 1: different, 2: read error)

## GitHub CLI

rtk gh pr list # Compact PR listing
rtk gh pr view 42 # PR details + checks
rtk gh issue list # Compact issue listing
rtk gh run list # Workflow run status

## Test Runners

rtk jest # Jest compact (failures only)
rtk vitest # Vitest compact (failures only)
rtk playwright test # E2E results (failures only)
rtk pytest # Python tests (-90%)
rtk phpt # PHP .phpt tests (run-tests.php, -99%)
rtk go test # Go tests (NDJSON, -90%)
rtk cargo test # Cargo tests (-90%)
rtk rake test # Ruby minitest (-90%)
rtk rspec # RSpec tests (JSON, -60%+)
rtk err <cmd> [args...] # Direct argv execution, errors/warnings only
rtk test <cmd> [args...] # Direct argv execution, failures only (-90%)
rtk err --shell fish '<script>' # Explicit shell for shell-specific syntax

## Build & Lint

rtk lint # ESLint grouped by rule/file
rtk lint biome # Supports other linters
rtk sqlfluff lint # SQL linting (JSON, -75%)
rtk sqlfluff lint models/ # Lint a specific directory (pass path after `lint`)
rtk tsc # TypeScript errors grouped by file
rtk next build # Next.js build compact
rtk prettier --check . # Files needing formatting
rtk cargo build # Cargo build (-80%)
rtk cargo clippy # Cargo clippy (-80%)
rtk ruff check # Python linting (JSON, -80%)
rtk golangci-lint run # Go linting (JSON, -85%)
rtk rubocop # Ruby linting (JSON, -60%+)
rtk mvnd verify # Maven Daemon (same filters as rtk mvn)
rtk sbt test # ScalaTest output (-90%)
rtk sbt compile # Compilation errors only (-75%)
rtk sbt run # Strip SBT preamble noise

## Package Managers

rtk pnpm list # Compact dependency tree
rtk uv run pytest # Preserve uv env, keep program output
rtk pip list # Python packages (auto-detect uv)
rtk pip outdated # Outdated packages
rtk bundle install # Ruby gems (strip Using lines)
rtk prisma generate # Schema generation (no ASCII art)

## Containers

rtk docker ps # Compact container list
rtk docker images # Compact image list
rtk docker logs <container> # Deduplicated logs
rtk docker compose ps # Compose services

## Data & Analytics

rtk json config.json # Structure without values
rtk deps # Dependencies summary
rtk env -f AWS # Filtered env vars
rtk log app.log # Deduplicated logs
rtk curl <url> # Truncate + save full output
rtk wget <url> # Download, strip progress bars
rtk summary <cmd> [args...] # Direct argv execution + heuristic summary
rtk run <cmd> [args...] # Raw direct execution (no filtering/tracking)
rtk run -c '<script>' # Shell string via sh (cmd on Windows)
rtk run --shell fish -c '<script>' # Explicit shell for shell-specific syntax
rtk proxy <command> # Raw passthrough + tracking

## Token Savings Analytics

rtk gain # Summary stats
rtk gain --graph # ASCII graph (last 30 days)
rtk gain --history # Recent command history
rtk gain --daily # Day-by-day breakdown
rtk gain --all --format json # JSON export for dashboards

rtk discover # Find missed savings opportunities
rtk discover --all --since 7 # All projects, last 7 days

rtk session # Show RTK adoption across recent sessions
