# MTK — Moruk Token Killer

**Less terminal noise. Complete logs. Bounded workloads.**

MTK wraps RTK with explicit output limits, private logs, and optional CPU,
memory, and time limits. Keep everyday terminal output compact while retaining
complete wrapped output for investigating failures.

```bash
mtk COMMAND [ARGS] [-- MTK OPTIONS]
mtk git status
mtk npm test -- --time 60s --memory 2G --cpu 100
mtk bun script.ts -- --no-truncate
```

[Install](#install) · [Try it](#try-it) · [Output and logs](#output-and-logs) ·
[Global config](#global-config) · [Resource limits](#resource-limits) ·
[Agent guide](MTK.md)

## Install

Homebrew installs MTK and its declared dependencies, including `zx` for
JavaScript-based shell orchestration:

```bash
brew install zzheer/tap/mtk
mtk doctor
```

Use `mtk zx` for shell orchestration with zx's own runtime. Use `mtk bun` for
ad hoc scripts and file processing:

```bash
mtk zx ./scripts/task.mjs
mtk bun ./scripts/process-data.ts
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
mtk bun -e 'for (let i = 1; i <= 8; i++) console.log(`line ${i}`)' -- --max-lines 3
```

Displayed output:

```text
line 1
line 2
line 8
[truncated by mtk]

/tmp/mtk-<unique-id>.log
```

The marker indicates output was omitted. The final path is
printed on **stderr**. Open that file to see all eight lines; the log has
neither the marker nor the filepath footer.

For common development commands:

```bash
mtk ls .
mtk git diff
mtk cargo test
mtk just test
mtk bun script.ts
```

Use native handlers for Git, ripgrep, GitHub CLI, tests, and builds to retain
RTK's summaries. Unknown commands execute directly, preserving their output
and exit status within MTK's display and resource limits, so `mtk just`,
`mtk bun`, and `mtk fd` work directly.
Interactive passthrough keeps a terminal attached.

## Output and logs

Default output caps share one budget across stdout and stderr: **80 lines,
1500 words, 8000 Unicode characters, and 32 KiB**. Clipped output keeps the
up to the first 40 and last 40 lines. The tail may be absent if the head
consumes the shared word, character, or byte budget. MTK keeps draining output
after the display limit and writes it to a unique private `/tmp/mtk-*.log` with
permissions `0600`.

- Clipped output gets one exact `[truncated by mtk]` marker after its tail.
- The log retains complete raw wrapped-command output.
- stdout and stderr share the display budget and are captured in observed arrival order, without labels.
- Display line and word boundaries are shared across streams; switching streams adds no separator, UTF-8 decoding stays per stream, and retained bytes go to their original stream.
- The log filepath prints last on stderr, after output drains.
- Normal exit codes and shell-compatible signal statuses are preserved.
- Capture failures are reported explicitly.

**Complete means complete wrapped output.** If RTK already summarized or
removed text, MTK cannot reconstruct it. Run the underlying command directly
when you need its unsummarized output.

Noninteractive stdout and stderr share one display budget. When stdin, stdout,
and stderr are terminals, MTK uses a PTY. Output order follows observed arrival;
stdin, signals, and resize are forwarded.

Put display options after the final `--`:

```bash
mtk git diff -- --max-lines 500 --max-bytes 128KiB
mtk bun script.ts -- --no-truncate
```

**For JSON and other machine-readable pipelines, use `--no-truncate`.**
A truncation marker in stdout would otherwise break the data format. Logging
and the stderr footer remain enabled.

Display limits do not limit log size. `/tmp` logs can contain sensitive command
output; manage retention and available disk space separately.

## Global config

Create `~/.config/mtk/config.json` to set display defaults. If `XDG_CONFIG_HOME`
is set, MTK reads `$XDG_CONFIG_HOME/mtk/config.json` instead.

```json
{
  "max_lines": 80,
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
mtk bun worker.ts -- --time 60s --memory 2G --cpu 100
mtk cargo build -- --time=5m --memory=2G --cpu=100
```

- `--time DURATION`: timeout; disabled by default and always covers descendants.
- `--memory SIZE`: sampled workload memory limit; disabled by default and covers descendants.
- `--cpu PERCENT`: CPU limit, disabled by default and includes descendants.
- `--root-only`: restrict CPU limiting to the root process; false by default.
- `--max-lines`, `--max-bytes`, `--no-truncate`: output controls; defaults are 80 lines and 32 KiB, with truncation enabled. Fixed caps also limit display to 1500 words and 8000 Unicode characters across both streams, even when `--max-lines` or `--max-bytes` is raised. `--no-truncate` disables all display caps.

Put MTK options after the final `--`; value options accept a separate value or
`=VALUE`. Output and singleton flags can also appear in this block. Output
defaults can be overridden in global config. Earlier `--` separators remain
child arguments; the final delimiter starts the MTK block:

```bash
mtk bun worker.ts --child-option value -- --time 60s --memory 2G --cpu 100
mtk tool -- --child-option -- --max-lines 100
```

CPU percentage uses one logical core as `100`; `50` means half a core.
MTK ships its corrected CPU limiter, including support for Apple Silicon.
On Darwin, descendant CPU limiting follows the full process-tree depth by default.
Requested CPU enforcement fails explicitly if the limiter is unavailable.

Avoid nesting CPU-limited MTK commands: independent stop/resume controllers
can interfere with each other. When running the governor test suite, apply
`--root-only` to the outer test runner so each regression owns its CPU
controller; retain the outer timeout and memory limits.

Memory is checked periodically; this is a termination threshold, not a hard
allocation cap. Timeout and memory cleanup cover the full workload, including
descendants, even with `--root-only`. MTK waits for cleanup and escalates
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

## Fetch

Fetch web content as Markdown:

```bash
mtk fetch https://example.com -o page.md -- --time 45s
```

Fetch rejects HTTP errors and recognized challenge content, then tries available
fallbacks. If no attempt yields accepted content, it returns nonzero and preserves
an existing destination file.
Local fetching can fall back to the remote Jina service; this is not a
guarantee of browser or JavaScript rendering.

## Shell shortcuts and agents

Optional aliases for bash/zsh:

```bash
# Add to ~/.zshrc or ~/.bashrc
eval "$(mtk env)"
```

Examples: `mgit` → `mtk git`, `mrg` → `mtk rg`, `mpf` → `mtk fd`,
`mpj` → `mtk just`, `mpn` → `mtk node`, `mssh` → `mtk ssh`.
The standalone `mpp` command runs `mtk python3`.
`mp` is an alias for `mtk`; `mr` is a short alias for `mtk`.

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

Setup preserves unrelated hook entries, replaces the legacy RTK handler, and is
idempotent. The private adapter retains RTK's supported-command decisions and
rewrites through MTK, so both `git status` and `rtk git status` become
`mtk git status`. Commands already using MTK are unchanged. Review and trust the
new or changed hook in Codex's `/hooks` screen before relying on it. Hook protocol
JSON bypasses output capture; rewritten workloads retain MTK's caps and logs.

## Development and releases

Run project checks locally:

```bash
mtk just validate
```

Validation uses Python 3.12 and runs the unit suite followed by all Python helper
typechecks using the pinned ty checker through `uvx`. Tests use deterministic fixtures, mocked
executables, and isolated Codex homes.
Governor checks also exercise real child processes. Project policy requires
CI, builds, tests, and automated reviews to run exclusively on owned devices:
no GitHub Actions, hosted reviews, or additional paid GitHub automation.

One [installation manifest](packaging/manifest.json) defines dependencies,
helpers, filters, source files, and the private limiter build. Generate a local
archive and formula with:

```bash
mtk ./scripts/release.sh 0.3.5 --local
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
RTK provides command summaries.
