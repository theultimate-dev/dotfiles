# Yazi: a file manager that opens in micro, reads in glow, and shows git status

How [Yazi](https://yazi-rs.github.io) is configured here, how the configuration reaches it without
a symlink or a copy, and the three traps met on the way.

Verified against **Yazi 26.9.1**, **glow 3.0.0**, **micro 2.0.15** and **Ghostty 1.3.1** on
macOS 26.

## What you get

Inside a repository, `yazi` shows:

- a preview pane that renders Markdown through glow while you hover, before anything is opened;
- **Enter** on a `.md` file opens it full-screen in glow's pager; **Shift+Enter** (or `O`) opens
  a pick menu whose second entry is micro, for when reading turns into editing. glow's standard
  styles keep the `##` markers on second-level and deeper headings on purpose, coloured and
  bold; only the top heading is drawn as a block. That is the rendered view, not the source;
- **Enter** on any other text file opens micro;
- a git status mark next to every file, and a rolled-up mark on every directory that contains
  changed files: `M` modified, `A` added, `?` untracked, `D` deleted, and so on.

`Q` quits without changing the shell's directory. The `y` wrapper that makes `q` change directory
on quit is a shell function, and arrives with the zsh port, together with `$EDITOR`.

## How the config reaches Yazi

Yazi reads `yazi.toml`, `keymap.toml`, `theme.toml` and `init.lua` from one configuration
directory, and none of those files can include another. The stub mechanism this repo uses for git
and Ghostty has nothing to hook into, and a byte copy would have made the repo stop being live.

Yazi does honour one thing: the `YAZI_CONFIG_HOME` environment variable names the configuration
directory, and it is checked before the default `~/.config/yazi`. So the redirect here is not a
file but a variable: `install.sh` appends a named block to `~/.zshenv` that exports
`YAZI_CONFIG_HOME=<repo>/yazi`, and the repository directory *is* Yazi's configuration directory.
Every edit takes effect the next time Yazi starts, and `git diff` audits all of it.

Why `~/.zshenv`: zsh reads it for every shell, login or not, interactive or not. A Yazi started
from a Ghostty tab, from Zed's terminal, or inside a Herdr pane sees the variable. `~/.zshrc` only
reaches interactive shells, and on the maintainer's machine it belongs to a second dotfiles
installer anyway. The block is appended rather than prepended because in a shell the last export
wins, which keeps this repo a defaults layer: an export you type below the block survives every
re-run and overrides it.

Two costs come with the variable, and both are accepted in
[ADR 0010](decisions/0010-export-a-config-directory-variable-from-zshenv.md):

- **There is no machine-local override file for Yazi.** Git has `~/.gitconfig`, Ghostty has
  `local.ghostty`; Yazi reads exactly one directory. A local tweak is an edit to the repo, or a
  different `YAZI_CONFIG_HOME` exported below the block.
- **Only a zsh that has read `~/.zshenv` passes the variable on.** Open a new shell after
  `./install.sh`. A Yazi launched by something that never ran zsh looks in `~/.config/yazi`,
  finds nothing, and runs with defaults, silently.

Check which directory Yazi resolves with `ya env`; its `Config` section lists every file it looked
for and which ones it found.

### Trap: the shell you installed from

The first `yazi` after `./setup.sh` and `./install.sh` will misbehave if you type it into the
shell that ran them, and it misbehaves in two ways that look unrelated:

- **Enter opens `vi`, not glow.** That shell started before the `~/.zshenv` block existed, so it
  has no `YAZI_CONFIG_HOME`. Yazi looks in `~/.config/yazi`, finds nothing, and runs with its
  defaults, where a text file goes to `$EDITOR` and `$EDITOR` falls back to `vi`.
- **Inside this repo, `yazi` changes into the `yazi/` directory instead of starting.** zsh's
  `auto_cd` option (on by default with Oh My Zsh) is consulted *before* the fallback that searches
  `$PATH`, and it looks only at the shell's command hash. A shell that hashed Homebrew's `bin`
  before Yazi was installed there believes there is no `yazi` command, sees a directory called
  `yazi` in the current directory, and does what `auto_cd` does. One directory up there is no such
  directory, the `$PATH` fallback runs, and Yazi starts, which is what makes it look random.

Both have the same cure: open a new shell. A new Ghostty tab, a new Herdr pane or a new Zed
terminal all start a fresh zsh that reads `~/.zshenv` and has an empty hash. To repair the shell
you are in instead, run `source ~/.zshenv; rehash`. Neither Ghostty nor Herdr needs restarting.

## Openers: micro for text, glow for Markdown

Yazi decides what "open" means with `[open]` rules, matched first to last, each naming a list of
`[opener]` entries. **Enter** runs the first opener in the matched list; **Shift+Enter** and `O`
show all of them in a menu. That single feature is what makes "read in glow *and* edit in micro"
a configuration rather than a compromise.

`yazi/yazi.toml` prepends four rules to the defaults:

| File | Enter | Menu, in order |
|---|---|---|
| `*.md` | glow, pager mode | glow, micro, `$EDITOR`, Reveal in Finder |
| any `text/*` mime | micro | micro, `$EDITOR`, Reveal |
| empty file | micro | micro, `$EDITOR`, Reveal |
| JSON, JavaScript, `.ini` | micro | micro, `$EDITOR`, Reveal |

Both openers are `block = true`: Yazi hides itself, hands the terminal to the program, and returns
when it exits. The default `edit` opener, which runs `$EDITOR` and falls back to `vi`, stays in
every list on purpose. Nothing sets `$EDITOR` yet, so micro is named explicitly rather than
relied on through the variable; when the zsh port sets `EDITOR=micro`, the two entries will
simply do the same thing.

**Trap: match Markdown by name, not by mime type.** Yazi asks `file --mime-type` what a file is,
and on macOS that command reports a `.md` file as `text/plain`. A rule on `text/markdown` is
correct, looks right, and never fires. The Markdown rule therefore matches `url = "*.md"`, and it
is listed before the `text/*` rule because the first match wins.

glow renders one document, so its opener passes `%s1`, the first selected file, where micro's
passes `%s`, all of them.

## The preview pane

Yazi's built-in previewer shows Markdown as syntax-highlighted source. The official
[piper](https://github.com/yazi-rs/plugins/tree/main/piper.yazi) plugin pipes any shell command
into the pane instead, and the config uses it to run glow:

```toml
[[plugin.prepend_previewers]]
url = "*.md"
run = 'piper -- CLICOLOR_FORCE=1 glow -w=$w -s=$t "$1"'
```

Three details in that line, each learned the hard way by someone:

- `CLICOLOR_FORCE=1`: glow 2.0 and later drop colour when stdout is not a terminal, and inside
  piper it never is. Without the variable the preview is plain text.
- `$w` is the pane width, so glow wraps to fit rather than to its default 80 columns.
- `$t` is the terminal theme Yazi detected, `dark` or `light`, so glow's style follows the macOS
  appearance the same way the Ghostty theme does. When a terminal does not report its background
  the value is `auto` and glow falls back to its own detection.

Scroll the preview with `J` and `K`.

## Git status marks

The official [git](https://github.com/yazi-rs/plugins/tree/main/git.yazi) plugin runs
`git status` for the directory in view and paints the result into the file list. Two pieces of
config make it work, and both are needed:

- `init.lua` calls `require("git"):setup { order = 1500 }`. The number places the mark after the
  file name in Yazi's line mode.
- `yazi.toml` registers the plugin as a *fetcher* twice, once for files (`url = "*"`) and once
  for directories (`url = "*/"`), in one `group` so that Yazi runs it once per directory rather
  than once per entry.

The signs and their colours are Yazi theme keys under `[git]` in a `theme.toml`; this repo ships
none, so the plugin's defaults apply.

## Icons: two hosts, two answers

Yazi's file icons and the git plugin's signs are Nerd Font glyphs. Whether they render depends on
the terminal, not on Yazi:

- **Ghostty** ships the Nerd Font symbols built in and falls back to them for any glyph the
  configured font lacks, so `JetBrains Mono` in `ghostty/config.ghostty` needs nothing extra.
- **Zed's terminal** has no such fallback. The `Brewfile` installs the
  `font-symbols-only-nerd-font` cask for it, and Zed still has to be told to fall back to that
  font. Zed's settings are unmanaged here
  ([ADR 0005](decisions/0005-install-agent-tooling-without-managing-its-config.md)), so the
  edit is a manual step, in [Manual setup](manual-setup.md#7-yazi-icons-in-zeds-terminal).

Without the font, the icons show as empty boxes; Yazi itself works.

## Plugins: fetched into the repo, restored by `setup.sh`

Because the repo directory is the configuration directory, Yazi's package manager writes there
too. `ya pkg add` records each plugin in `yazi/package.toml` (its source, a commit and a content
hash) and deploys the code into `yazi/plugins/<name>.yazi/`. The lockfile is tracked; the plugin
code is third-party, so `.gitignore` excludes `yazi/plugins/` and `yazi/flavors/`.

On a fresh clone the plugins are therefore missing until `./setup.sh` runs `ya pkg install`,
which restores every locked revision. That step lives in `setup.sh`, not `install.sh`, because it
clones from GitHub, and config placement never touches the network. Re-running it redeploys the
locked revisions; it is convergent, not a no-op.

To add or upgrade a plugin, run `ya pkg add` or `ya pkg upgrade` from a shell that has
`YAZI_CONFIG_HOME` set, then commit the changed `package.toml`. **Trap:** in a shell without the
variable, the same command writes `~/.config/yazi/package.toml` instead, and Yazi never reads it.

## What is deliberately not here

- **`$EDITOR`**, the **`y` cd-on-quit wrapper**, and the **zoxide** and **fzf** shell hooks all
  belong to the zsh configuration and arrive with that port. Yazi's own `z` jump already works:
  Yazi adds every directory it visits to zoxide's database itself.
- **glow's own config** (`glow.yml` under `~/Library/Preferences/glow/`) stays unmanaged. Every
  setting this repo needs is passed on the command line, which overrides the file.
- **`keymap.toml` and `theme.toml`**: the default keys already cover open, open-with-menu and
  preview scrolling, and the default theme is fine. Either file can be added to `yazi/` later
  with no installer change, which is the point of the variable.
