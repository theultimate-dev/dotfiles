# Decision records

Why the delivery model is what it is, one decision per file, in Michael Nygard's format: Title,
Status, Context, Decision, Consequences, plus the alternatives that lost. A record is written once
and not edited afterwards; a reversal is a new record that supersedes the old one. Numbers are
assigned append-only.

Read this table first. Open a record when you need the argument, the rejected alternatives, or
the cost that was accepted.

| No. | Decision | Status |
|---|---|---|
| [0001](0001-deliver-configs-as-include-stubs-not-symlinks.md) | Deliver configs as include stubs, not symlinks — a real file at each destination redirects into the repo using the tool's own include directive | Accepted |
| [0002](0002-include-git-config-from-xdg-never-gitconfig.md) | Include git config from `~/.config/git/config`, never `~/.gitconfig` — your own settings win by construction | Accepted |
| [0003](0003-install-daily-tools-through-homebrew.md) | Install daily tools through Homebrew — one `Brewfile`, no vendor curl scripts | Accepted |
| [0004](0004-let-auto-updating-casks-manage-their-own-versions.md) | Let auto-updating casks manage their own versions — never `--greedy` | Accepted |
| [0005](0005-install-agent-tooling-without-managing-its-config.md) | Install agent tooling without managing its config — tools that rewrite their own settings stay unmanaged | Accepted |
| [0006](0006-manage-shared-destinations-with-delimited-blocks.md) | Manage shared destinations with named delimited blocks — own one BEGIN/END block, preserve every other byte | Accepted |
| [0007](0007-leave-pre-existing-apps-unadopted-by-default.md) | Leave pre-existing apps unadopted by default — `--adopt` opts in after checking the macOS permission | Accepted |
| [0008](0008-keep-one-agent-notification-channel-across-hosts.md) | Keep one agent notification channel across Zed, Ghostty and Herdr — `iterm2_with_bell` | Accepted |
| [0009](0009-insert-the-ghostty-block-first.md) | Insert the Ghostty block first in the destination file — Ghostty applies includes last, later wins | Accepted |
| [0010](0010-export-a-config-directory-variable-from-zshenv.md) | Export a config-directory variable from `~/.zshenv` — Yazi reads the repo directory itself | Accepted |
| [0011](0011-copy-the-hunk-config-and-report-drift.md) | Copy the hunk config and report drift — no include mechanism, and TOML forbids a shared block | Accepted |
| [0012](0012-replace-glow-with-leaf-for-markdown.md) | Replace Glow with Homebrew-installed Leaf for Markdown reading and previews, using the dark Ocean theme | Accepted |

Three of these are the ones to know before editing anything: 0001 for the delivery model, 0002 for
why git is the exception that avoids sharing a file at all, and 0009 for the precedence trap where
git and Ghostty behave in opposite ways.

Adding a record: next number, `NNNN-kebab-title.md`, and a row here. The `writing-adrs` skill
produces the format.
