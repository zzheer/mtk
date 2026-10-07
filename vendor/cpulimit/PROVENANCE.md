# MTK cpulimit source provenance

Upstream: https://github.com/opsengine/cpulimit.git, tag `v0.2`, commit
`f4d2682804931e7aea02a869137344bb5452a3cd`.

Imported into MTK packaging on 2026-10-04 from the owned
`resource-governor/vendor/cpulimit` source. Existing Moruk Darwin corrections
convert Mach CPU-time ticks using `mach_timebase_info`, retain 64-bit CPU
milliseconds, correct PID byte/count handling and child enumeration, and
compile against current macOS SDK headers. The original correction dates
were not recovered; the import date above records this distribution update.

MTK updates on 2026-10-06 follow the full Darwin ancestor chain when child
limiting is enabled and reset CPU samples when a PID has a different birth
time. Local regressions cover a CPU-heavy grandchild and reused PID history.

Upstream GPL-2.0-or-later notices are preserved in `LICENSE`, `COPYING`, and
source headers. MTK invokes this separate executable rather than linking it.

Build with at most two workers and a 120-second CPU limit:

```sh
ulimit -t 120
make -C vendor/cpulimit/src -j2 CFLAGS="-Wall -O2 -D_GNU_SOURCE"
```

Install the resulting `src/cpulimit` beside `mtk-runner.py` as `mtk-cpulimit`.
Distribute this complete source and license/provenance with the executable.
