set shell := ["bash", "-cu"]

# Show available recipes
default:
    @just --list

# Verify all dependencies and system health
doctor:
    ./bin/mtk doctor

# Check syntax and run test suites locally
test:
    bash -n bin/mtk bin/mpp libexec/mtk-core.sh share/mtk/mtk-aliases.sh scripts/release.sh
    python3 -m py_compile libexec/mtk-ai libexec/mtk-media
    ./bin/mtk doctor
    ./bin/mtk env >/dev/null
    ./bin/mtk --version
    ./bin/mtk generate-image --help >/dev/null
    @echo "All tests passed!"

# Audit Homebrew formula locally
audit:
    brew audit --tap=zzheer/tap zzheer/tap/mtk

# Build local release tarball and update formula (0 GitHub Actions)
release version="0.1.0":
    ./scripts/release.sh {{version}}

# Install local package via Homebrew (points to local archive for pre-release testing)
install-local version="0.1.0": (release version)
    sed -i '' 's|https://github.com/zzheer/mtk/archive/refs/tags/v.*\.tar\.gz|file://{{justfile_directory()}}/dist/mtk-v{{version}}.tar.gz|' /opt/homebrew/Library/Taps/zzheer/homebrew-tap/Formula/mtk.rb
    HOMEBREW_NO_AUTO_UPDATE=1 brew reinstall --build-from-source zzheer/tap/mtk
    git -C /opt/homebrew/Library/Taps/zzheer/homebrew-tap checkout Formula/mtk.rb

# Install published package from GitHub
install:
    HOMEBREW_NO_AUTO_UPDATE=1 brew reinstall --build-from-source zzheer/tap/mtk

# Test installed Homebrew package
test-brew:
    brew test zzheer/tap/mtk
