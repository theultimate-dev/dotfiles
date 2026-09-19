# Yazi: a file manager that opens in micro, reads in Leaf, and shows git status

How [Yazi](https://yazi-rs.github.io) is configured here, how the configuration reaches it without
a symlink or a copy, and the traps met on the way.

Verified against **Yazi 26.9.1**, **Leaf 1.28.2**, **micro 2.0.15** and **Ghostty 1.3.1** on
macOS 26.

## What you get

Inside a repository, `yazi` shows:

- a preview pane that renders Markdown through Leaf while you hover, including supported Mermaid
  diagrams and math, using the dark Ocean theme;
- **Enter** on a `.md` file opens Leaf full-screen in Ocean; **Shift+Enter** (or `O`) opens a
  pick menu whose second entry is micro. Inside Leaf, `Ctrl+E` opens micro and `q` returns to Yazi;
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
reaches interactive shells, and it is the file every shell framework and vendor installer wants to
edit anyway. The block is appended rather than prepended because in a shell the last export
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

- **Enter opens `vi`, not Leaf.** That shell started before the `~/.zshenv` block existed, so it
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

## Openers: micro for text, Leaf for Markdown

Yazi decides what "open" means with `[open]` rules, matched first to last, each naming a list of
`[opener]` entries. **Enter** runs the first opener in the matched list; **Shift+Enter** and `O`
show all of them in a menu. That single feature is what makes "read in Leaf *and* edit in micro"
a configuration rather than a compromise.

`yazi/yazi.toml` prepends four rules to the defaults:

| File | Enter | Menu, in order |
|---|---|---|
| `*.md` | Leaf, full-screen | Leaf, micro, `$EDITOR`, Reveal in Finder |
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

Leaf reads one document, so its opener passes `%s1`, the first selected file, where micro's
passes `%s`, all of them. `--` ends Leaf's option parsing, protecting dash-prefixed filenames.
`--editor micro` makes `Ctrl+E` use the same editor as Yazi's menu.

## The preview pane

Yazi's built-in previewer shows Markdown as syntax-highlighted source. The official
[piper](https://github.com/yazi-rs/plugins/tree/main/piper.yazi) plugin pipes any shell command
into the pane instead, and the config uses Leaf's noninteractive renderer:

```toml
[[plugin.prepend_previewers]]
url = "*.md"
run = 'piper -- leaf --theme ocean --inline "ansi:$w" -- "$1"'
```

The interactive reader needs the terminal; starting it inside a preview pipe is the wrong mode.
`--inline` writes the rendered document to stdout without entering the TUI, and `ansi` forces
colour even though stdout is a pipe. No `CLICOLOR_FORCE` environment variable is needed.
`$w` supplies the pane width instead of Leaf's default 80-column non-terminal width. Leaf clamps
inline widths below 20 columns to 20, so a narrower pane clips the result. Large diagrams can
wrap across lines and lose their layout; open the reader in a wider terminal to inspect them.
`"$1"` preserves the filename as one argument, and `--` ends option parsing.

Both the reader and preview pass `--theme ocean` explicitly: Markdown stays dark even when the
terminal reports a light background. Ocean is a built-in dark palette; no custom theme or managed
Leaf config is needed. CLI flags override personal Leaf theme settings for these Yazi commands.
Standalone Leaf also defaults to Ocean, but a personal config or `LEAF_THEME` can override that.
This choice does not change Ghostty's own appearance settings.

Scroll the preview with `J` and `K`. Leaf's TOC, search, and editor integration belong to the
full-screen reader; the pane displays rendered text only.

## Leaf and Glow

[ADR 0012](decisions/0012-replace-glow-with-leaf-for-markdown.md) records why Leaf replaces Glow.
Both render Markdown tables and highlighted code; table support alone is not the distinction.
The added value is reading diagrams and math alongside prose, then navigating a long document or
opening its editor without leaving the reader.

| Capability | Leaf | Glow |
|---|---|---|
| Tables and highlighted code | Rendered tables and code frames | Rendered tables and highlighted code |
| Mermaid | Terminal text diagrams for supported syntax | Fenced source in the standard renderer |
| Math | Terminal formula rendering | No dedicated formula renderer |
| Reading workflow | TOC, heading jumps, search, watch mode, `Ctrl+E` editor | Markdown discovery, TUI, external pager |
| Input | Local files, picker, stdin | Local files, stdin, HTTP URLs and GitHub/GitLab README shortcuts |
| Appearance here | Ocean forced in both Yazi commands | Previously followed the terminal's light/dark appearance |

Leaf's diagrams are text, not browser-rendered SVGs. Unsupported Mermaid syntax and complex
layouts need checking against the original document; do not assume complete Mermaid or LaTeX
compatibility. A prettier table is a visual preference, not a capability missing from Glow.
Glow's URL shortcuts and pager workflow remain useful outside Yazi.

Sources: [Leaf's usage and features](https://github.com/RivoLink/leaf#usage),
[its Mermaid renderer](https://github.com/RivoLink/leaf/blob/main/src/markdown/mermaid.rs),
[Glow's CLI and pager](https://github.com/charmbracelet/glow#the-cli), and
[Glamour's table renderer](https://github.com/charmbracelet/glamour/blob/master/ansi/table.go).

Homebrew's [leaf-markdown-viewer](https://formulae.brew.sh/formula/leaf-markdown-viewer) formula
installs the `leaf` executable. The unrelated `leaf` and `leaf-proxy` formulae conflict with it.
Updates stay with Homebrew; do not run Leaf's self-updater on a Homebrew-managed binary. Removing
Glow from the Brewfile does not uninstall an existing copy. Installation, verification, optional
cleanup, and rollback live in [Manual setup](manual-setup.md#switch-an-existing-installation-from-glow-to-leaf).

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
- **Leaf's own config** (`~/.config/leaf/config.toml`, or under `$XDG_CONFIG_HOME`) stays
  unmanaged. Yazi passes the required theme, editor, and preview mode on the command line.
  Personal Leaf settings can still control other behavior, such as watch mode and history.
- **`keymap.toml` and `theme.toml`**: the default keys already cover open, open-with-menu and
  preview scrolling, and the default theme is fine. Either file can be added to `yazi/` later
  with no installer change, which is the point of the variable.
