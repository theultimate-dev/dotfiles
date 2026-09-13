brew "herdr"              # homebrew-core formula; upstream docs have an "Install with Homebrew" section
brew "terminal-notifier"  # required in practice by docs/herdr-notifications.md
brew "micro"              # terminal editor for quick edits next to a running agent; upstream README lists brew
brew "hunk"               # live working-tree diff viewer for agent panes; modem-dev/hunk, NOT hunk.nvim
brew "gh"                 # GitHub CLI; `gh pr diff N | hunk patch -` is the PR review path, see docs/hunk.md
brew "figlet"             # banner text for screenshots and demos: figlet -f slant "The Ultimate Dev"

brew "yazi"               # terminal file manager; reached through YAZI_CONFIG_HOME, see docs/yazi.md
brew "glow"               # markdown reader; Yazi's *.md opener and its preview pane
brew "fd"                 # Yazi: file-name search
brew "ripgrep"            # Yazi: content search
brew "fzf"                # Yazi: fuzzy jump
brew "zoxide"             # Yazi: directory jump; Yazi feeds the database itself, no shell hook needed
brew "poppler"            # Yazi: PDF preview
brew "ffmpeg"             # Yazi: video thumbnails
brew "imagemagick"        # Yazi: HEIC, AVIF and JXL preview
brew "jq"                 # Yazi: JSON preview
brew "sevenzip"           # Yazi: archive preview and extraction
brew "resvg"              # Yazi: SVG preview

cask "ghostty"
cask "zed"
cask "t3-code"            # alpha GUI control plane, not a CLI — see docs/agent-tooling.md
cask "font-symbols-only-nerd-font"  # Yazi icons in Zed's terminal; Ghostty has them built in

cask "codex"              # OpenAI Codex CLI. NOT cask "codex-app" (discontinued upstream)
cask "copilot-cli"
cask "antigravity-cli"    # the `agy` CLI. NOT cask "antigravity" (app) or "antigravity-ide"
cask "grok-build"         # xAI's `grok`. NOT brew "grok" — that is an unrelated, deprecated regex tool
