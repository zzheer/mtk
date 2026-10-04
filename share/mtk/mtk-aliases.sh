# share/mtk/mtk-aliases.sh - Productivity aliases and helper functions for mtk
# Source this file in your ~/.zshrc or ~/.bashrc:
#   eval "$(mtk env)"
# or:
#   source $(brew --prefix)/share/mtk/mtk-aliases.sh

alias mr='mtk run'
alias mpf='mtk proxy fd'
alias mrg='mtk rg'
alias md='mtk docker'
alias mpj='mtk proxy just'
alias mpnpm='mtk pnpm'
alias mgh='mtk gh'
alias mgit='mtk git'
alias mp='mtk proxy'
alias mb='mtk bun'
alias mpn='mtk proxy node'
alias mpd='mtk pnpm dlx'
alias mpe='mtk pnpm exec'
alias mnpm='mtk npm'
alias mnpx='mtk npx'
alias mssh='mtk proxy ssh'
alias mmd='mtk markitdown'

# Python proxy helper function
mpp() {
  mtk proxy python3 "$@"
}
