# Changelog

## Unreleased

- Read global config as UTF-8 and cover symlink-to-regular success plus device
  and FIFO rejection with a specific stderr assertion; invalid UTF-8 bytes fail
  closed before the wrapped command. Directories and other nonregular paths are
  rejected before wrapping the open descriptor.
- Rewrote the README with a working truncation demo, Homebrew setup, global
  configuration, machine-readable output guidance, and resource-limit semantics.
- Fixed a hang when the global configuration path is a FIFO or another
  nonregular file. MTK now rejects it before starting the wrapped command,
  preserving bounded execution.
- Clarified accepted configuration file types in the MTK guide and global
  agent instructions, including support for symlinks to regular JSON files.

## 0.2.1 — 2026-10-04

- Load global display defaults from `~/.config/mtk/config.json`, respecting
  `XDG_CONFIG_HOME` and CLI overrides. Validate settings before command execution
  and bound configuration reads.
- Publish canonical `MTK.md` with global configuration and agent operating rules.
- Preserve the requested version when generating release formulas; verify
  configuration and overrides using installed Homebrew binaries.
- Validate changes with local RED-to-GREEN regressions and 48 offline tests.

## 0.2.0 — 2026-10-04

- Save complete wrapped-command output in private `/tmp` logs and print the log path last on stderr.
- Mark each MTK output omission with `[truncated by mtk]`; configure line/byte limits or disable clipping.
- Include CPU-consuming children by default, with an option to cap only the root process.
- Bundle a corrected Apple Silicon CPU limiter and stop workloads when enforcement fails.
- Complete timeout and memory cleanup even when the root exits before resistant descendants; return distinct failure statuses.
- Preserve interactive terminals, input, signals, and resize through resource governance.
- Reject failed or invalid fetch responses without replacing an existing output file.
- Allow noninteractive, idempotent Codex hook configuration while preserving other hook commands.
- Use independently published Homebrew `duckduckgo-tools` for search; remove bundled source and hidden fallback.
- Keep package dependencies, installed helpers, licensed source, and release archive checksums consistent.
- Publish a pinned source archive checksum for reproducible Homebrew installation.
