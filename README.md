# MTK — Moruk Token Killer

**Less terminal noise. Complete logs. Bounded workloads.**

MTK wraps RTK with explicit output limits, private logs, and optional CPU,
memory, and time limits. Keep everyday terminal output compact while retaining
complete wrapped output for investigating failures.

```bash
mtk COMMAND ... [resource and display limits]
mtk git status
mtk npm test --time-limit 60s --memory-limit 2G --cpu-limit 100
mtk python3 script.py --no-truncate
```

[Install](#install) · [Try it](#try-it) · [Output and logs](#output-and-logs) ·
[Global config](#global-config) · [Resource limits](#resource-limits) ·
[Agent guide](MTK.md)

## Install

Homebrew installs MTK and its declared dependencies:

```bash
brew install zzheer/tap/mtk
mtk doctor
```

Already installed?

```bash
brew update
brew upgrade zzheer/tap/mtk
```

On Apple Silicon macOS, the usual command path is `/opt/homebrew/bin/mtk`.
Verify your shell with `command -v mtk`. Homebrew owns the installation; no
source-checkout wrapper or CPU helper under your home directory is required.

## Try it

Print eight lines with a three-line display limit:

```bash
mtk python3 -c 'for i in range(1, 9): print(f"line {i}")' --max-lines 3
```

Displayed output:

```text
line 1
line 2
line 3
[truncated by mtk]

/tmp/mtk-<unique-id>.log
```

The marker shows where MTK stopped displaying output. The final path is
printed on **stderr**. Open that file to see all eight lines; the log has
neither the marker nor the filepath footer.

For common development commands:

```bash
mtk ls .
mtk git diff
mtk cargo test
mtk just test
mtk python3 script.py
```

Use native handlers for Git, ripgrep, GitHub CLI, tests, and builds to retain
RTK's summaries. Unknown commands execute directly, preserving their output
and exit status within MTK's display and resource limits, so `mtk just`,
`mtk python3`, and `mtk fd` work directly.
Interactive passthrough keeps a terminal attached.

## Output and logs

The default display limit is **200 lines or 32 KiB per stream**, whichever
comes first. MTK keeps draining output after the display limit and writes it
to a unique private `/tmp/mtk-*.log` with permissions `0600`.

- Each MTK clipping region gets the exact marker `[truncated by mtk]`.
- The log contains only bytes emitted by the wrapped command.
- stdout and stderr are captured in observed arrival order, without labels.
- The log filepath prints last on stderr, after output drains.
- Normal exit codes and shell-compatible signal statuses are preserved.
- Capture failures are reported explicitly.

**Complete means complete wrapped output.** If RTK already summarized or
removed text, MTK cannot reconstruct it. See [Exact output](#exact-output) when
you need the command's unsummarized output.

Noninteractive execution uses separate stdout/stderr pipes and separate display
budgets. When stdin, stdout, and stderr are terminals, MTK uses a PTY: combined
terminal output shares one display budget. stdin, signals, and resize are
forwarded.

Append display limits to the command (legacy prefix flags also work):

```bash
mtk git diff --max-lines 500 --max-bytes 128KiB
mtk python3 script.py --no-truncate
```

**For JSON and other machine-readable pipelines, use `--no-truncate`.**
A truncation marker in stdout would otherwise break the data format. Logging
and the stderr footer remain enabled.

Display limits do not limit log size. `/tmp` logs can contain sensitive command
output; manage retention and available disk space separately.

### Exact output

Use `mtk run COMMAND ...` to execute raw argv without command-specific RTK
summaries, while retaining MTK logging and resource limits:

```bash
mtk run git diff --no-truncate --time-limit 30s
```

The log records all emitted output; it cannot recover content removed by a
native RTK summary. `run` bypasses that summary. The stderr log filepath footer
still prints.

## Global config

Create `~/.config/mtk/config.json` to set display defaults. If `XDG_CONFIG_HOME`
is set, MTK reads `$XDG_CONFIG_HOME/mtk/config.json` instead.

```json
{
  "max_lines": 200,
  "max_bytes": "32KiB",
  "truncate": true
}
```

`max_lines` accepts a positive integer. `max_bytes` accepts a positive integer
byte count or a size string, such as `"128KiB"`. `truncate` accepts a JSON
boolean; `false` disables display clipping while retaining the log.

CLI flags override corresponding config values. Missing files and omitted
keys use built-in defaults. Unknown keys, invalid JSON, and invalid values fail
before the wrapped command runs.

Config must be a regular JSON file. FIFOs, devices, and other nonregular files
are rejected before command execution; symlinks to regular files are allowed.
Config reads are bounded to 64 Ki characters. Resource limits remain separate
CLI options.

## Resource limits

Bound a workload independently of how much output you display:

```bash
mtk python3 worker.py --time-limit 60s --memory-limit 2G --cpu-limit 100
mtk cargo build --time-limit=5m --mem-limit=2G --cpu-limit=100
```

- `--time-limit DURATION`: terminate the workload at its deadline.
- `--memory-limit SIZE` (alias `--mem-limit`): terminate when sampled total workload RSS exceeds the limit.
- `--cpu-limit PERCENT`: limit CPU use, including descendants by default.
- `--exclude-children`: apply the CPU limit to the root process only.

Resource flags and display flags (`--max-lines`, `--max-bytes`,
`--no-truncate`) are extracted only from a final contiguous MTK flag suffix
after the command and its arguments. Value flags accept separate values or `=VALUE`.
Legacy prefix flags still work; repeated limits use the last value, and suffix
values override prefix values. A standalone `--` anywhere after `COMMAND`
disables suffix extraction for that invocation and preserves the wrapped
arguments:

```bash
mtk --time-limit 60s python3 worker.py --time-limit 30s
mtk python3 worker.py -- --time-limit 30s
```

The first command has a 30-second MTK limit. The second passes the arguments
through without extracting MTK flags. Singleton flags remain prefix-only.
Keep all trailing MTK flags together at the end:

```bash
mtk python3 worker.py --time-limit 60s --max-lines 100 --cpu-limit 50
mtk run tool -- --max-lines 100 # Pass --max-lines through to tool
```

CPU percentage uses one logical core as `100`; `50` means half a core.
MTK ships its corrected CPU limiter, including support for Apple Silicon.
On Darwin, descendant CPU limiting follows the full process-tree depth by default.
Requested CPU enforcement fails explicitly if the limiter is unavailable.

Avoid nesting CPU-limited MTK commands: independent stop/resume controllers
can interfere with each other. When running the governor test suite, apply
`--exclude-children` to the outer test runner so each regression owns its CPU
controller; retain the outer timeout and memory limits.

Memory is checked periodically; this is a termination threshold, not a hard
allocation cap. Timeout and memory cleanup cover the full workload, including
descendants, even with `--exclude-children`. MTK waits for cleanup and escalates
surviving processes to SIGKILL. Timeout returns `124`; memory breach returns
`137`. With child exclusion, the root may be a shell or RTK wrapper, leaving
the actual worker uncapped.

For workload coordination, `--singleton=NAME` replaces an existing workload
with that name; `--singleton-wait=NAME` waits for it.

## Device-local jobs

```bash
mtk jobs       # List tracked workloads for the current user on this device
mtk stop --all # Stop those workloads and their observed descendants
```

MTK records workloads in `$XDG_STATE_HOME/mtk/jobs`, or
`~/.local/state/mtk/jobs` when `XDG_STATE_HOME` is unset. Registry directories
are private (`0700`), and records are private (`0600`). This is a device-local
registry, separate from singleton coordination; it uses no daemon.

Before signaling, MTK checks each process's UID and high-resolution PID birth
time. `stop --all` excludes unrelated processes, itself, and its ancestors.
Cleanup sends TERM, then KILL to verified survivors within a bounded wait.
Emergency signaling uses kernel group and identity checks independently of
process snapshots; capture errors still restore terminal settings.

MTK periodically captures descendants and retains observed surviving descendants
after their root exits. Sampling can miss rapid detach/reparent operations
between samples, or descendants born after observers exit; tracking is not an
absolute guarantee of finding every detached process.

## Search and fetch

Search uses the separately published
[duckduckgo-tools](https://github.com/zzheer/duckduckgo-tools) Homebrew dependency:

```bash
mtk search-web "Rust ownership" --limit 5
mtk --no-truncate search-web "Rust ownership" --limit 5 --json
```

MTK calls the installed provider executable. No bundled source checkout or
Instant Answer fallback is used. A missing provider returns an actionable
nonzero error. Network access and provider availability are required.

Fetch web content as Markdown:

```bash
mtk --time-limit 45s fetch https://example.com -o page.md
mtk markitdown document.pdf -o document.md
```

Fetch rejects HTTP errors and recognized challenge content, then tries available
fallbacks. If no attempt yields accepted content, it returns nonzero and preserves
an existing destination file.
Local fetching/conversion can fall back to the remote Jina service; this is
not a guarantee of browser or JavaScript rendering. MarkItDown runs through
an installed binary or `uvx`.

## Shell shortcuts and agents

Optional aliases for bash/zsh:

```bash
# Add to ~/.zshrc or ~/.bashrc
eval "$(mtk env)"
```

Examples: `mgit` → `mtk git`, `mrg` → `mtk rg`, `mpf` → `mtk fd`,
`mpj` → `mtk just`, `mpn` → `mtk node`, `mssh` → `mtk ssh`.
The standalone `mpp` command runs `mtk python3`.
`mp` is an alias for `mtk`; `mr` remains `mtk run`.

The public [MTK agent guide](MTK.md) describes commands, limits, logs, and when
direct execution is appropriate. For global agent instructions, use the
[canonical raw guide](https://raw.githubusercontent.com/zzheer/mtk/refs/heads/preview/MTK.md).
Prefer the Homebrew command resolved through PATH. If wrapping changes required
behavior or hides necessary diagnostics, run the underlying command directly.

Optional Codex hook configuration:

```bash
mtk hook codex --help
mtk hook codex          # Global ~/.codex/hooks.json
mtk hook codex --local  # Project .codex/hooks.json
```

Setup preserves existing hook entries and is idempotent. Using MTK from the
shell does not require enabling currently disabled Codex hooks.

## Development and releases

Run project checks locally:

```bash
just test
```

Tests use deterministic fixtures, mocked executables, and isolated Codex homes.
Governor checks also exercise real child processes. Project policy requires
CI, builds, tests, and automated reviews to run exclusively on owned devices:
no GitHub Actions, hosted reviews, or additional paid GitHub automation.

One [installation manifest](packaging/manifest.json) defines dependencies,
helpers, filters, source files, and the private limiter build. Generate a local
archive and formula with:

```bash
mtk ./scripts/release.sh 0.2.2 --local
```

For a published formula, pass `--url` with its exact HTTPS source archive URL.
The packager downloads that archive, validates required files, and derives its
SHA256 from those exact bytes. Outputs stay in local `dist/`; the packager does
not overwrite your Homebrew tap. Homebrew formulas must be installed from a tap.

Contributions use `feat/` branches and PRs targeting `preview`.
See [CHANGELOG.md](CHANGELOG.md) for changes.

## License and credits

MTK's own source is [MIT licensed](LICENSE). The vendored CPU limiter retains
its [GPL-2.0-or-later license](vendor/cpulimit/COPYING) and
[provenance](vendor/cpulimit/PROVENANCE.md). The Homebrew formula declares both.
RTK provides command summaries; duckduckgo-tools provides web search.
