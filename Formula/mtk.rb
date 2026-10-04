class Mtk < Formula
  include Language::Python::Shebang

  desc "Optimized CLI proxy and AI developer toolkit wrapping rtk"
  homepage "https://github.com/zzheer/mtk"
  url "https://github.com/zzheer/mtk/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "49a072f85ca3d6d17cf6edd4704606a10de42e50043f4e530a9f8ddda12b5fd3"
  license "MIT"

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
    # Install internal python and shell helpers into libexec
    libexec.install "libexec/mtk-ai", "libexec/mtk-media", "libexec/mtk-core.sh"

    # Install user binaries into bin
    bin.install "bin/mtk", "bin/mpp"

    # Rewrite python hashbangs to brewed python
    rewrite_shebang detected_python_shebang, libexec/"mtk-ai", libexec/"mtk-media"

    # Install alias and justfile template into share/mtk
    pkgshare.install "share/mtk/mtk-aliases.sh", "share/mtk/justfile"
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
    assert_match "Checking mtk dependencies", shell_output("#{bin}/mtk doctor 2>&1", 0)
    assert_match "usage: mtk generate-", shell_output("#{bin}/mtk generate-image --help 2>&1", 0)
    assert_match "rtk", shell_output("#{bin}/mtk --version 2>&1", 0)
  end
end
