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
- **Media generation stubs**:
  ```bash
  mtk generate-image --help
  mtk generate-audio --help
  mtk generate-video --help
  ```

See [mtk.md](mtk.md) for full documentation of commands, runners, and token-saving analytics.

## Releasing (Owned Devices Only)

Release archives and formula checksums are generated 100% locally without cloud CI:

```bash
./scripts/release.sh 0.1.0
```
