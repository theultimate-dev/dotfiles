# hunk: watching an agent edit, live

How [hunk](https://hunk.dev) is configured here, why its configuration is the one file in this
repository that gets copied rather than included, and the two traps that follow from that.

Verified against **hunk 0.22.0** and **Herdr** in **Ghostty 1.3.1** on macOS 26.

## What you get

A pane that shows what a coding agent is doing to the working tree while it does it:

```sh
hunk diff --watch
```

That renders the whole working-tree diff — untracked files included — with syntax highlighting and
a file sidebar, and redraws itself whenever the tree changes underneath it. Put it in a Herdr pane
next to the agent and the review stops being something you do afterwards. You watch a file appear,
watch the hunk you care about land, and catch a wrong turn while it is still one edit deep instead
of forty.

The layout follows the pane. A wide pane gets a side-by-side diff; a narrow one drops to unified,
because a split diff in a half-width pane is two columns of wrapped noise. That is `mode = "auto"`,
and it is why a monitoring pane can be narrow without becoming useless.

## Reviewing something other than the working tree

The watch pane is one command. hunk mirrors git's diff-shaped commands generally, and opens each
one in the same review UI instead of the pager:

| To review | Command |
|---|---|
| the last commit, or any commit | `hunk show`, `hunk show HEAD~1`, `hunk show <sha>` |
| what a branch adds to main | `hunk diff main...HEAD` |
| two revisions | `hunk diff <from> <to>` |
| what you are about to commit | `hunk diff --staged` |
| history, as a browsable workspace | `hunk log` |
| a stash entry | `hunk stash show` |
| a patch file, or a patch on stdin | `hunk patch <file>`, `hunk patch -` |

`hunk log` is the one worth trying first. It browses commits with a graph, and a selected range
carries into a review rather than dumping a wall of text. It takes git's own filters —
`--author`, `--grep`, `--since`, `-n` — and `--static` or `--oneline` when you want plain output
to pipe somewhere.

### A pull request

There is no GitHub integration, and none is needed. The GitHub CLI produces the patch and hunk
reads it:

```sh
gh pr diff 42 | hunk patch -
```

That needs neither a clone nor a checkout, and it runs from anywhere on the machine — the patch
carries its own context, so an unfamiliar repository can be reviewed without ever fetching it. When
you also want to run the code, check the branch out and diff it instead:

```sh
gh pr checkout 42
hunk diff main...HEAD
```

Three dots, not two: it shows what the branch adds since it diverged, rather than mixing in what
`main` did in the meantime.

The boundary is worth stating, because it is what you give up. **hunk is a local review layer, not
a replacement for the hosted pull request system.** Nothing it does posts a comment, an approval,
or a review back to GitHub. It gets you a readable changeset in the terminal; the conversation
still happens where it always did.

### The aliases, and the trap that shapes them

`git/.gitconfig` ships three, so the review commands sit next to the git commands they mirror:

```sh
git hdiff        # hunk diff
git hshow        # hunk show
git hlog         # hunk log
```

They arrive through the `[include]` in `~/.config/git/config`, so they are live as soon as the file
changes. No `./install.sh` re-run — which is exactly the property hunk's own config gave up, and a
good illustration of why an include beats a copy wherever a tool offers one.

The definition looks over-built, and is not:

```gitconfig
hdiff = "!f() { cd \"${GIT_PREFIX:-.}\" && hunk diff \"$@\"; }; f"
```

Git runs a `!` alias from the top level of the worktree, never from where you typed it. The obvious
`hdiff = !hunk diff` therefore resolves a relative pathspec against the repo root: run
`git hdiff -- hunk.md` inside `docs/` and you get an empty review, no error, no hint that the path
was the problem. Git exports the directory you were in as `GIT_PREFIX`, and cd-ing back to it
restores the pathspec behaviour every other git command has.

Nothing here sets `core.pager`, so `git diff`, `git show` and `git log` keep their normal output.
See below for why.

## Why a viewer and not a git client

lazygit and gitui show the same diff and are already good. Neither is what belongs in this pane.

They are interactive clients: the pane is focused, the keyboard is live, and a single keystroke
stages, discards, or commits. Sharing a window with an agent that is itself writing to the tree,
that is a footgun with no upside — the pane is there to be read, not driven. hunk has no write
path at all. Worst case, you quit it.

lazygit also polls, every ten seconds by default, rather than watching the filesystem. hunk
reloads on the change. Next to an agent that edits in bursts, ten seconds is the difference
between watching and checking.

## How the config reaches hunk

Every other configuration in this repository is *included* from its destination, so the repo file
is live and an edit takes effect with no reinstall. hunk is the exception, and not by choice.

hunk reads `~/.config/hunk/config.toml`. It has no include directive, no `--config` flag, and no
config-directory variable — so the stub mechanism has nothing to hook into, and the
`YAZI_CONFIG_HOME` trick has no variable to export. The remaining idea, a named BEGIN/END block
sharing the destination the way `~/.config/git/config` is shared, does not survive contact with
TOML:

```
hunk: TOML Parse error: Cannot redefine key 'theme'
```

TOML forbids a repeated key outright. Every other destination here relies on later-wins semantics
to let a user's own line override the repo's; TOML has no such semantics, so a `theme` in the block
and a `theme` typed above it is not an override but a hunk that refuses to start. A block would
have been a trap that fires on the day someone edits their own config.

So `install.sh` copies `hunk/config.toml` to `~/.config/hunk/config.toml` and owns it outright,
which is the fallback the delivery model has always named for a tool with no include mechanism.
See [ADR 0011](decisions/0011-copy-the-hunk-config-and-report-drift.md).

Two costs come with the copy, and both are accepted:

- **The repository is no longer live for this one file.** Edit `hunk/config.toml` and nothing
  changes until you re-run `./install.sh`. `./install.sh --check` is what tells you the two have
  drifted apart; it reports the gap and cannot prevent it.
- **There is no machine-local override layer.** Git has `~/.gitconfig`, Ghostty has
  `local.ghostty`; hunk has one user config, and this repo owns it. The layer that does exist is
  per-project, below.

Anything already sitting at the destination is copied into `~/.dotfiles-backup/` and recorded in
its manifest before the first overwrite. Nothing is replaced silently.

## Trap: hunk wants to write to that same file

Change the layout or the theme during a session and hunk offers, on quit, to remember it — by
writing to the user config, which is the file `install.sh` owns.

Accept that prompt once and the destination is permanently at odds with the repo. `--check` starts
reporting drift you did not cause, and the next `./install.sh` silently discards the preference you
asked hunk to keep. Neither side is wrong; they are two managers of one file.

The shipped config closes it:

```toml
prompt_save_view_preferences = false
```

That line is load-bearing, not cosmetic. A view preference worth keeping is an edit to
`hunk/config.toml` followed by `./install.sh` — the same loop as every other setting here. For a
one-off, the flags win over the file anyway: `--mode split`, `--theme`, `-x4`.

## The override layer that does exist

A `.hunk/config.toml` at a repository root overrides the user config for that repository alone,
and hunk reads it before anything this installer placed. That is the right home for a
project-specific tab width or an exclusion, and it travels with the project rather than with the
machine.

It is worth knowing about for the other direction too: if hunk ignores a key you just set in this
repo, look for one of those before suspecting the copy.

## What is deliberately not here

- **hunk as git's pager.** `git config --global core.pager "hunk pager"` routes every `git diff`,
  `git show` and `git log` on the machine through hunk. That is a real option and a bigger
  decision than a watch pane — it changes the output of commands used by scripts and by muscle
  memory — so it is left to you, and it belongs in `~/.gitconfig` rather than in anything this
  repo writes. The `git hdiff` aliases above are the lighter half of the same idea: opt in per
  command, and leave the originals alone. `hunk difftool <left> <right>` is there for the
  `git difftool` route if you prefer it.
- **The bundled Claude Code skill.** hunk ships one that drives a live review session over
  `hunk session`, letting an agent navigate hunks and leave inline notes beside the code they
  describe. `hunk skill path` prints where it lives. Nothing here installs it; agent configuration
  stays unmanaged, per
  [ADR 0005](decisions/0005-install-agent-tooling-without-managing-its-config.md).
- **`hunk update`.** Homebrew is the single install channel here, per
  [ADR 0003](decisions/0003-install-daily-tools-through-homebrew.md). Upgrade with `brew upgrade`
  along with everything else.
