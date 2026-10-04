class Mtk < Formula
  include Language::Python::Shebang

  desc "Optimized CLI proxy and AI developer toolkit wrapping rtk"
  homepage "https://github.com/zzheer/mtk"
  url "https://api.github.com/repos/zzheer/mtk/tarball/65057849764fffa7414f510397fa0f82a5eda7da"
  version "0.2.1"
  sha256 "2d3ab2b403bc7da8ac59d5ccc47798d0e2afb5d1d8365c9974ebe7c051cc5855"
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
    ENV["XDG_CONFIG_HOME"] = (testpath/"config").to_s
    (testpath/"config/mtk").mkpath
    (testpath/"config/mtk/config.json").write('{"max_lines":1,"max_bytes":"32KiB","truncate":true}')
    assert_match "[truncated by mtk]", shell_output("#{bin}/mtk proxy printf 'one\\ntwo\\n' 2>&1", 0)
    refute_match "[truncated by mtk]", shell_output("#{bin}/mtk --max-lines 2 proxy printf 'one\\ntwo\\n' 2>&1", 0)
    (testpath/"config/mtk/config.json").delete
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
