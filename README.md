# mtk

> Optimized developer toolkit and proxy wrapping `rtk`, with AI routing, media stubs, and token-saving workflow aliases.

## Installation

Install via Homebrew tap:

```bash
brew tap zzheer/tap
brew install mtk
```

Or install directly from this repository:

```bash
brew install --build-from-source Formula/mtk.rb
```

## Shell Integration

To activate productivity shortcuts and shell aliases (`mr`, `mrg`, `mgit`, `mpd`, etc.):

```bash
# Add to ~/.zshrc or ~/.bashrc:
eval "$(mtk env)"
```

Or source directly:

```bash
source $(brew --prefix)/share/mtk/mtk-aliases.sh
```

## Quick Start

- **System health & dependencies**:
  ```bash
  mtk doctor
  ```
- **File operations & git**:
  ```bash
  mtk ls .
  mtk git status
  mtk diff file1 file2
  ```
- **Python proxy shortcut**:
  ```bash
  mpp script.py  # Standalone binary shortcut for `mtk proxy python3`
  ```
- **AI model router**:
  ```bash
  mtk ai --provider openrouter --model anthropic/claude-3.5-sonnet --prompt "Hello"
  ```
- **Resource limits & governance**:
  ```bash
  mtk --time-limit 30s npm test
  mtk --memory-limit 2G python3 process.py
  mtk --cpu-limit 50% ffmpeg -i in.mp4 out.mp4
  mtk --singleton=myserver ./run_server.sh  # Auto-kills previous instance
  mtk --singleton-wait ./deploy.sh          # Waits for active instance
  ```
- **MarkItDown conversion**:
  ```bash
  mtk markitdown doc.pdf -o doc.md
  mmd presentation.pptx  # Using alias
  ```
- **Codex CLI hook setup**:
  ```bash
  mtk hook codex         # Configures ~/.codex/hooks.json
  mtk hook codex --local # Configures .codex/hooks.json
  ```
- **Web search & resilient fetch**:
  ```bash
  mtk search-web "rust programming" --limit 5  # DuckDuckGo search (free, 0 tokens)
  mtk fetch https://news.ycombinator.com       # Stealth browser fetch -> clean Markdown
  mtk fetch https://example.com -o page.md     # Save markdown to file
  ```
- **Proxy fallback**:
  Any command not built into `mtk` or `rtk` (e.g., `mtk date`, `mtk fd`) automatically executes under `rtk proxy`.

## Output limits and complete logs

Every invocation saves complete wrapped output in a private `/tmp/mtk-*.log`.
The file contains only the output emitted by the wrapped command, including RTK
summaries. MTK markers and the filepath footer never enter the log. stdout and
stderr are logged in observed arrival order, without extra labels.

Display defaults: 200 lines or 32 KiB per stream, whichever comes first. Each
MTK omission has `[truncated by mtk]`. The log filepath prints last on stderr,
so ordinary stdout remains suitable for pipes and JSON. Existing RTK summaries
are unchanged; the log cannot recover text RTK removed before emitting output.

```bash
mtk --max-lines 500 --max-bytes 128KiB git diff
mtk --no-truncate proxy python3 script.py
mtk --time-limit 30s --memory-limit 2G --cpu-limit 150 npm test
mtk --cpu-limit 50 --exclude-children proxy python3 script.py
```

CPU limits include children by default. MTK packages a corrected limiter for
Apple Silicon; no user-home helper is required. Timeout/memory termination
cleans the full workload before returning 124/137 respectively. Interactive
passthrough uses a PTY and forwards stdin, signals, and terminal resize.

## Dependencies

Homebrew manages runtimes and utilities. The search provider is separate:
[duckduckgo-tools](https://github.com/zzheer/duckduckgo-tools), installed through
`zzheer/tap/duckduckgo-tools`. No bundled checkout or Instant Answer fallback.
Search is enabled only after provider publication and installation validation.

MarkItDown runs via its installed binary or `uvx markitdown`. Fetch uses local
converters with a Jina fallback, checks final HTTP/content validity, and keeps
an existing output file intact when fetching fails.

Run `mtk doctor` for dependency paths. Run `just test` for deterministic local
regression tests; no hosted CI, live search, or shared Codex hook writes.

See [mtk.md](mtk.md) for full documentation of commands, runners, and token-saving analytics.

## Releasing (Owned Devices Only)

Release archives and formula checksums are generated 100% locally without cloud CI:

```bash
mtk proxy ./scripts/release.sh 0.2.0 --local
```

For published formulas, pass `--url https://api.github.com/repos/zzheer/mtk/tarball/v0.2.0`. The packager hashes those exact downloaded bytes and writes `dist/mtk.rb`; it never overwrites your tap.
