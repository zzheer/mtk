# Changelog

## 0.3.5

- Document command-first MTK options after the final `--`, including disabled
  resource-limit defaults and the combined output caps: 80 lines, 1500 words,
  8000 Unicode characters, and a shared 32 KiB cap with head and tail context.
- Keep legacy command handlers available internally without listing them as public commands.
- Keep the external provider optional; return a clear 404 when its endpoint is missing.

## Unreleased
- Clean governed workers after outer initial process discovery fails, including
  failures during governor initialization and near-timeout snapshots. Install
  governor signal handlers before worker creation and bound emergency grace.

- Preserve outer capture SIGTERM status when process discovery is interrupted,
  while reporting incomplete capture and restoring terminal state.
- Remove obsolete command dispatch from the root Python shell helper and cover
  argument preservation in Bash and Zsh.

- Keep emergency cleanup available when process discovery fails, restore
  terminal settings even if finalization fails, and preserve termination
  status when a forwarded signal interrupts the process snapshot itself.
- Prepare Homebrew 0.3.4 from pinned public source `0e920b9`, with the
  checksum derived from the exact served archive and installed job helpers.
- Track current-user workloads with `mtk jobs` and terminate tracked workloads
  and observed descendants with `mtk stop --all`, using private records and
  UID/birth-time checks before signaling. Retain observed orphans; document
  polling limitations.
- Accept display limits alongside resource limits at the end of commands,
  and preserve last-value precedence before native RTK global options.
- Limit CPU-heavy grandchildren on Darwin and reset CPU history on PID reuse.
  Document interference between independently nested CPU controllers.
- Finish workload cleanup after live or initial job-record failures, and
  preserve forwarded TERM status during escalation without forcing SIGINT
  handlers to terminate.
- Package the job registry helper through the shared installation manifest;
  exercise installed helpers and management commands in Homebrew tests.
- Accept time, memory, and CPU limits as a final command suffix while preserving
  native RTK dispatch and last-value precedence. Use the final `--` to separate
  child arguments from MTK options.
- Route everyday aliases and Python helpers through automatic dispatch, and
  document command-first limits after the final `--`.
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
- Keep package dependencies, installed helpers, licensed source, and release archive checksums consistent.
- Publish a pinned source archive checksum for reproducible Homebrew installation.
