class Mtk < Formula
  include Language::Python::Shebang

  desc "Optimized CLI proxy and AI developer toolkit wrapping rtk"
  homepage "https://github.com/zzheer/mtk"
  url "https://github.com/zzheer/mtk/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "e72dd736dd088d7fafb078840d2abcc5042137911976ca808a1d0a5552856e1a"
  license all_of: ["MIT", "GPL-2.0-or-later"]

  depends_on "ast-grep"
  depends_on "bun"
  depends_on "fd"
  depends_on "gh"
  depends_on "just"
  depends_on "node"
  depends_on "pnpm"
  depends_on "python@3.12"
  depends_on "ripgrep"
  depends_on "rtk"
  depends_on "uv"
  depends_on "zzheer/tap/duckduckgo-tools"

  def install
    system "bash", "-c", "ulimit -t 120; exec make -j2 -C vendor/cpulimit/src CFLAGS='-Wall -O2 -D_GNU_SOURCE'"
    libexec.install "vendor/cpulimit/src/cpulimit" => "mtk-cpulimit"
    libexec.install "libexec/mtk-ai", "libexec/mtk-media", "libexec/mtk-core.sh", "libexec/mtk-runner.py", "libexec/mtk-output.py", "libexec/mtk-search", "libexec/mtk-fetch"
    bin.install "bin/mtk", "bin/mpp"
    pkgshare.install "share/mtk/mtk-aliases.sh", "share/mtk/justfile", "share/mtk/filters.toml", "vendor/cpulimit/COPYING", "vendor/cpulimit/LICENSE", "vendor/cpulimit/PROVENANCE.md"
    rewrite_shebang detected_python_shebang, libexec/"mtk-ai", libexec/"mtk-media", libexec/"mtk-runner.py", libexec/"mtk-output.py"
  end

  def caveats
    <<~EOS
      To enable mtk shell aliases (e.g., mr, mrg, mgit, mpd, mmd), add to your shell profile:
        eval "$(mtk env)"
      or:
        source #{opt_pkgshare}/mtk-aliases.sh
    EOS
  end

  test do
    assert_match "Checking mtk dependencies", shell_output("#{bin}/mtk doctor 2>&1", 0)
    assert_match "Usage: mtk", shell_output("#{bin}/mtk --help 2>&1", 0)
    refute_match "Usage: rtk", shell_output("#{bin}/mtk --help 2>&1")
    assert_match "usage: mtk generate-", shell_output("#{bin}/mtk generate-image --help 2>&1", 0)
    assert_match "rtk", shell_output("#{bin}/mtk --version 2>&1", 0)
    assert_match "test_ok", shell_output("#{bin}/mtk --time-limit 5s echo test_ok 2>&1", 0)
    assert_match "Usage: mtk search-web", shell_output("#{bin}/mtk search-web --help 2>&1", 0)
    assert_match "Usage: mtk fetch", shell_output("#{bin}/mtk fetch --help 2>&1", 0)
  end
end
