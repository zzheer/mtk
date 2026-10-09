set shell := ["bash", "-cu"]

# Show available recipes
default:
    @just --list

# Verify all dependencies and system health
doctor:
    ./bin/mtk doctor

# Search provider is a separately published Homebrew dependency
install-search:
    HOMEBREW_NO_AUTO_UPDATE=1 brew install zzheer/tap/duckduckgo-tools

# Check syntax and run test suites locally
test:
    bash -n bin/mtk bin/mpp libexec/mtk-core.sh libexec/mtk-search libexec/mtk-fetch share/mtk/mtk-aliases.sh scripts/release.sh
    python3.12 -m unittest discover -s tests -p 'test_*.py'

# Check every Python helper with a pinned checker
typecheck:
    uvx --from ty==0.0.85 ty check --python "$(command -v python3.12)" --output-format concise libexec libexec/mtk-ai libexec/mtk-media scripts/package.py

# Validate sequentially; fail before starting the next check
validate:
    just test
    just typecheck

# Audit Homebrew formula locally
audit:
    brew audit --tap=zzheer/tap zzheer/tap/mtk

# Build local release tarball and matching file URL formula (0 GitHub Actions)
release version="0.1.0":
    ./scripts/release.sh {{version}} --local

# Install local formula without changing source formula or user's tap
install-local version="0.1.0": (release version)
    HOMEBREW_NO_AUTO_UPDATE=1 brew reinstall --build-from-source {{justfile_directory()}}/dist/mtk.rb

# Install published package from GitHub
install:
    HOMEBREW_NO_AUTO_UPDATE=1 brew reinstall --build-from-source zzheer/tap/mtk

# Test installed Homebrew package
test-brew:
    brew test zzheer/tap/mtk
