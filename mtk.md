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

## Preferences

Instead of using `mtk proxy python3`, I prever that you use bun with `mtk bun` for everyday tasks.
Prefer `mtk proxy fd` over `find`. Prefer `mtk rg` over `grep`.

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
