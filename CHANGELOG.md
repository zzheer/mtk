# Changelog

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
