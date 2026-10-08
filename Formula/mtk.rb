class Mtk < Formula
  include Language::Python::Shebang

  desc "Bounded CLI and developer toolkit with RTK summaries"
  homepage "https://github.com/zzheer/mtk"
  url "https://api.github.com/repos/zzheer/mtk/tarball/0e920b91adc4e25000bcbe08296a57966734a4d4"
  version "0.3.5"
  sha256 "0402a1f2c9e44d6c5a729d4f4ed8821432fe2e5af9a170b222ef56d4c266fe16"
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

  def install
    system "bash", "-c", "ulimit -t 120; exec make -j2 -C vendor/cpulimit/src CFLAGS='-Wall -O2 -D_GNU_SOURCE'"
    libexec.install "vendor/cpulimit/src/cpulimit" => "mtk-cpulimit"
    libexec.install "libexec/mtk-ai", "libexec/mtk-media", "libexec/mtk-core.sh", "libexec/mtk-runner.py", "libexec/mtk-output.py", "libexec/mtk-search", "libexec/mtk-fetch", "libexec/mtk_jobs.py"
    bin.install "bin/mtk", "bin/mpp"
    pkgshare.install "share/mtk/mtk-aliases.sh", "share/mtk/justfile", "share/mtk/filters.toml", "vendor/cpulimit/COPYING", "vendor/cpulimit/LICENSE", "vendor/cpulimit/PROVENANCE.md"
    rewrite_shebang detected_python_shebang, libexec/"mtk-ai", libexec/"mtk-media", libexec/"mtk-runner.py", libexec/"mtk-output.py"
  end

  def caveats
    <<~EOS
      To enable mtk shell aliases (e.g., mr, mrg, mgit, mpd), add to your shell profile:
        eval "$(mtk env)"
      or:
        source #{opt_pkgshare}/mtk-aliases.sh
    EOS
  end

  test do
    ENV["XDG_CONFIG_HOME"] = (testpath/"config").to_s
    ENV["XDG_STATE_HOME"] = (testpath/"state").to_s
    (testpath/"config/mtk").mkpath
    (testpath/"config/mtk/config.json").write('{"max_lines":1,"max_bytes":"32KiB","truncate":true}')
    assert_match "[truncated by mtk]", shell_output("#{bin}/mtk printf 'one\\ntwo\\n' 2>&1", 0)
    refute_match "[truncated by mtk]", shell_output("#{bin}/mtk printf 'one\\ntwo\\n' -- --max-lines 2 2>&1", 0)
    (testpath/"config/mtk/config.json").delete
    assert_match "Checking mtk dependencies", shell_output("#{bin}/mtk doctor 2>&1", 0)
    assert_match "Usage: mtk", shell_output("#{bin}/mtk --help 2>&1", 0)
    refute_match "Usage: rtk", shell_output("#{bin}/mtk --help 2>&1")
    refute_match(/^\s+proxy\s+/, shell_output("#{bin}/mtk --help 2>&1", 0))
    refute_match(/^\s+run\s+/, shell_output("#{bin}/mtk --help 2>&1", 0))
    assert_match "usage: mtk generate-", shell_output("#{bin}/mtk generate-image --help 2>&1", 0)
    assert_match "rtk", shell_output("#{bin}/mtk --version 2>&1", 0)
    assert_match "test_ok", shell_output("#{bin}/mtk echo test_ok -- --time 5s --memory 120M --cpu 100 --root-only 2>&1", 0)
    assert_match "No active MTK jobs", shell_output("#{bin}/mtk jobs 2>&1", 0)
    assert_match "Stopped 0 MTK jobs", shell_output("#{bin}/mtk stop --all 2>&1", 0)
    assert_predicate libexec/"mtk_jobs.py", :file?
    assert_match "Usage: mtk fetch", shell_output("#{bin}/mtk fetch --help 2>&1", 0)
  end
end
