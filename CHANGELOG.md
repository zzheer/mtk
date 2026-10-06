# Changelog

## Unreleased

- Keep emergency cleanup available when process discovery fails, restore
  terminal settings even if finalization fails, and preserve termination
  status when a forwarded signal interrupts the process snapshot itself.
- Prepare Homebrew 0.3.2 from pinned public source `b544e20`, with the
  checksum derived from the exact served archive and installed job helpers.
- Track current-user workloads with `mtk jobs` and terminate tracked workloads
  and observed descendants with `mtk stop --all`, using private records and
  UID/birth-time checks before signaling. Retain observed orphans; document
  polling limitations.
- Accept display limits alongside resource limits at the end of commands,
  and preserve last-value precedence before native RTK global options.
- Remove the public `proxy` command; use automatic dispatch or `mtk run`.
  Reject it behind native global flags and remove its inherited RTK help entry.
- Limit CPU-heavy grandchildren on Darwin and reset CPU history on PID reuse.
  Document interference between independently nested CPU controllers.
- Finish workload cleanup after live or initial job-record failures, and
  preserve forwarded TERM status during escalation without forcing SIGINT
  handlers to terminate.
- Package the job registry helper through the shared installation manifest;
  exercise installed helpers and management commands in Homebrew tests.
- Accept time, memory, and CPU limits as a final command suffix while preserving
  native RTK dispatch, prefix syntax, and last-value precedence. Use `--` after
  the command to protect tool-owned flags from suffix extraction.
- Route everyday aliases and Python helpers through automatic dispatch, and
  document command-first limits with explicit `run` dispatch.
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
