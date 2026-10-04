#!/usr/bin/env bash
set -euo pipefail

# scripts/release.sh - Local owned-device release packager for mtk Homebrew formula
# Zero GitHub Actions required.

VERSION="${1:-0.1.0}"
VERSION="${VERSION#v}" # Strip leading v if present
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$REPO_ROOT/dist"
ARCHIVE_NAME="mtk-v${VERSION}.tar.gz"
ARCHIVE_PATH="$DIST_DIR/$ARCHIVE_NAME"
FORMULA_PATH="$REPO_ROOT/Formula/mtk.rb"
TAP_FORMULA_PATH="/opt/homebrew/Library/Taps/zzheer/homebrew-tap/Formula/mtk.rb"
GITHUB_REPO="zzheer/mtk"

echo "=== Packaging mtk v${VERSION} ==="
mkdir -p "$DIST_DIR"

# Create a clean temporary directory for archiving
TMP_BUILD="$(mktemp -d)"
trap 'rm -rf "$TMP_BUILD"' EXIT

TARGET_DIR="$TMP_BUILD/mtk-${VERSION}"
mkdir -p "$TARGET_DIR"

# Copy required package files
cp -R "$REPO_ROOT/bin" "$TARGET_DIR/"
cp -R "$REPO_ROOT/libexec" "$TARGET_DIR/"
cp -R "$REPO_ROOT/share" "$TARGET_DIR/"
cp "$REPO_ROOT/mtk.md" "$TARGET_DIR/"
[[ -f "$REPO_ROOT/README.md" ]] && cp "$REPO_ROOT/README.md" "$TARGET_DIR/"
[[ -f "$REPO_ROOT/LICENSE" ]] && cp "$REPO_ROOT/LICENSE" "$TARGET_DIR/"

# Create tarball
tar -czf "$ARCHIVE_PATH" -C "$TMP_BUILD" "mtk-${VERSION}"

# Calculate SHA256
SHA256="$(shasum -a 256 "$ARCHIVE_PATH" | awk '{print $1}')"
echo "Archive: $ARCHIVE_PATH"
echo "SHA256:  $SHA256"

# Generate Formula/mtk.rb template
cat <<EOF > "$FORMULA_PATH"
class Mtk < Formula
  include Language::Python::Shebang

  desc "Optimized CLI proxy and AI developer toolkit wrapping rtk"
  homepage "https://github.com/${GITHUB_REPO}"
  url "https://github.com/${GITHUB_REPO}/archive/refs/tags/v${VERSION}.tar.gz"
  sha256 "${SHA256}"
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

    # Install alias files into share/mtk
    pkgshare.install "share/mtk/mtk-aliases.sh"
  end

  def caveats
    <<~EOS
      To enable mtk shell aliases (e.g., mr, mrg, mgit, mpd), add to your shell profile:
        eval "\$(mtk env)"
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
EOF

# If the local tap exists, copy formula there too
if [[ -d "$(dirname "$TAP_FORMULA_PATH")" ]]; then
  cp "$FORMULA_PATH" "$TAP_FORMULA_PATH"
  echo "Synced to local tap: $TAP_FORMULA_PATH"
fi

echo "Updated $FORMULA_PATH successfully."
echo "=== Done ==="
