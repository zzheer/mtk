# MTK review contract

- Review the full pull-request diff and preserve existing command handlers for compatibility. Do not introduce public commands, flags, or plugins unless explicitly requested.
- Output limits share one budget across stdout and stderr: first 40 plus last 40 lines without overlap, 1,500 words, 8,000 Unicode characters including newlines, and a 32 KiB byte ceiling. Line and word boundaries are shared across streams; a stream switch adds no separator. UTF-8 decoding remains per stream. Retained bytes preserve their destination stream.
- Preserve head-first streaming, exact argument forwarding, child exit codes, and complete private logs. Never inject `--ultra-compact` automatically.
- `mtk bun` runs JavaScript/TypeScript; `mtk zx` uses zx's own runtime for shell orchestration. zx is a required dependency.
- Codex hook migration must preserve unrelated handlers and explicit options, avoid duplicates, rewrite supported ordinary and RTK-prefixed commands through MTK, and leave existing MTK commands unchanged.
- Verify source archive pins, checksums, packaged helpers, and matching tap metadata. Unit tests and Python typechecks must pass via sequential `just validate` on Magnet. Required reviews and resolved conversations remain merge gates.
- Report confirmed defects with a reproducer and source location. Do not change credentials, provider settings, or code as part of a review request.
