# agent-sync: one manifest for the plugins and skills of every coding agent

How `scripts/agent-sync` keeps Claude Code, Codex and Antigravity (`agy`) holding the same skills:
what it asks each harness to do, what it refuses to do, and the harness behaviour that shaped
both.

Verified against **Claude Code 2.1.332**, **Codex CLI 0.172.0** and **agy 1.5.18** with Python
3.13.2 on macOS, on 2026-11-27; the contract tests were first run against Claude Code 2.1.327,
Codex 0.170.0 and agy 1.5.9. The decision and the alternatives that lost are in
[ADR 0014](decisions/0014-sync-agent-plugins-through-their-own-clis.md). The commands to set it up,
check it and undo it are in [manual setup, step 3](manual-setup.md#3-sync-agent-plugins-and-skills).

## The problem this solves

Each harness finds skills its own way. Claude Code and Codex both install plugins from
Claude-format marketplace catalogs, but through two CLIs with different verbs. Both also read a
folder of flat skills: `~/.claude/skills/` for Claude Code, `~/.agents/skills/` for Codex. agy has
no command to add a third-party marketplace at all; it reads skill folders from
`~/.gemini/config/skills/`.

Keeping three harnesses in step by hand drifts, and the drift is invisible. The usual way it goes
wrong: a skills CLI copies a plugin's skills into `~/.agents/skills/` once, the plugin moves on,
and Codex now offers both the plugin's skill and the old flat copy under the same name. Two
descriptions compete for the model's attention, and when they differ the model can pick the stale
one. Nothing reports it.

agent-sync replaces the hand-keeping with one run: a per-machine manifest names the marketplaces,
plugins and skills you want; agent-sync asks each harness, through its own CLI, to hold exactly
those; it copies the selected skills into agy; and it prints one report of what changed, what was
already current, and what needs you.

## What it does in each harness

| Harness | What agent-sync runs | What lands where |
|---|---|---|
| Claude Code | `claude plugin marketplace add`, `marketplace update`, `plugin install`, `plugin update`, `plugin enable`, all at user scope | Wherever Claude Code keeps its plugins; agent-sync writes none of it |
| Codex | `codex plugin marketplace add [--ref]`, `marketplace upgrade`, `plugin add` | Wherever Codex keeps its plugins and its cache; agent-sync writes none of it |
| agy | `agy plugin list` only, to check names | Copies of the selected skills, one folder each, in `~/.gemini/config/skills/<name>/` |

Three things it never does, in any harness:

- **It writes no harness settings file.** Not `~/.claude/settings.json`, not Codex's
  `config.toml`, not agy's `skills.json`. Those change only as a side effect of the harness's own
  CLI — the same line [ADR 0005](decisions/0005-install-agent-tooling-without-managing-its-config.md)
  draws for every other agent tool here. One file is *read*: Codex's `config.toml`, for a
  marketplace's ref (see [The ref lives only in Codex's settings](#the-ref-lives-only-in-codexs-settings)).
- **It never uninstalls.** A plugin the manifest does not list is reported `unmanaged` and left
  alone. A marketplace whose source or ref differs from the manifest is reported, never removed
  and re-added.
- **It never writes a flat skill into `~/.claude/skills/` or `~/.agents/skills/`.** Claude Code
  and Codex get plugins only. A flat copy there is exactly the duplicate this command exists to
  remove.

## The manifest

The manifest is yours and stays untracked, at `~/.config/agent-sync/manifest.toml`
(`$XDG_CONFIG_HOME` is honoured; `--manifest` points elsewhere, which is also how a second account
is reached). It names marketplaces and the local paths of your checkouts — identity and machine
paths, which this repository never tracks. The repository ships a generic, commented
[`agent-sync/manifest.example.toml`](../agent-sync/manifest.example.toml) to start from.

Four ideas carry the whole format:

- **A marketplace has one source per harness:** `git` (a branch or tag of a Git repository),
  `checkout` (a local working tree, read as it stands and never pulled), or `none`. The usual shape
  is a checkout for Claude Code, which reads it live, and Git for Codex, which copies at install.
- **Enrolment is `listed` by default.** Only the `[[plugin]]` rows you write are managed.
  `plugins = "all"` manages every plugin the catalog declares, minus an `exclude` list. Use it for
  a catalog you own: in someone else's, it installs plugins you have not read about. A plugin the
  catalog has and the manifest leaves out is reported `available`, so a new one is noticed.
- **`agy_skills` picks a subset** of a plugin's skills for agy. agy gets skills, never plugins:
  hooks, MCP servers and agents written for Claude Code stay with the harness that installed them.
- **`[external]` names skills installed some other way** — a skills CLI, a cloud sync, by hand.
  They are reported `external` instead of raising a duplicate.

Loose skills, from no catalog, can go to agy as `[[skill]]` rows with a `path` or a `git` source.
v1 manages no loose skill for Claude Code or Codex.

Every name that reaches a harness CLI — a marketplace, a plugin, a catalog's own plugin names —
must start with a letter or digit and hold only letters, digits, `.`, `_` and `-`, and a Git
source or ref may not start with `-`. A name a CLI could read as an option is refused before any
command runs: in the manifest it exits 2, and in a catalog it is that plugin's `failed` row.

## Where its own files live

| Path | What it is |
|---|---|
| `~/.local/state/agent-sync/state.json` | What was last applied per marketplace and per plugin, and which agy folders agent-sync owns, with their digests |
| `~/.local/state/agent-sync/lock` | One run at a time; holds the running PID |
| `~/.local/state/agent-sync/last-run.log` | Every command the last run executed, with exit codes; credentials in URLs are redacted |
| `~/.local/state/agent-sync/archive/<timestamp>/` | Everything agent-sync ever moved out of the way. Nothing is deleted |
| `~/.cache/agent-sync/sources/` | agent-sync's own clone of each Git source, used to read catalogs and to copy skills for agy. Each folder is named by the SHA-256 of what was asked for: the kind of source, its URL and its ref, never a name, so no two sources share one on any volume; safe to delete |

`$XDG_STATE_HOME` and `$XDG_CACHE_HOME` are honoured. `CLAUDE_CONFIG_DIR` and `CODEX_HOME` pass
through to the harnesses untouched, so the harness homes are whatever those variables say. A
harness home may also be a symlink, set up on purpose to point at another profile. agent-sync
neither checks nor refuses that: those homes are written only by their own CLIs, and cleanup moves
folders in them where the link leads.

**Keep the state directory on the home volume.** Every move agent-sync makes is a single rename,
into or out of the archive under `$XDG_STATE_HOME`. A rename cannot cross volumes, and agent-sync
never falls back to copying and deleting, so nothing can be left half-removed. When the archive is
on another volume, the item is `failed`, the row names both paths, and nothing has moved.

agent-sync writes nothing through a symlink. Every folder on the way to a file it writes — the
state folder, the lock, the archive, the Git cache, agy's skills folder and the staging folders
beside it — is checked component by component, and a link anywhere is an error naming it. A move
checks agent-sync's end of it at the moment it happens. A move never replaces anything: it claims
its destination as a new, empty folder and fails if the name is taken. Temp files are created
exclusively, so a name planted in advance redirects nothing. Git runs with the cache's repository
and work tree named explicitly, and with `GIT_DIR` and the other repository-selection variables
removed from its environment.

The state file is read only after the lock is held, and it is validated before anything uses it.
Folder names must be plain names, every field must have the type it should, and cleanup records
hold names, never paths. Every path agent-sync moves is rebuilt from those names under its own
roots. If the state file fails validation, the run stops with exit 2 and asks you to move the file
aside. A skill whose folder name agent-sync could not record is never copied, and its row is
`failed`, so a catalog cannot poison the state file.

If the state file cannot be written, for example because the disk is full, nothing is lost
silently. A `failed` row names the state file and what went unrecorded, the report still prints,
and the run exits 1. A copy that went unrecorded is picked up on the next run: an agy folder that
already holds exactly what would be copied is recorded again rather than held. A first copy, which
had no record yet, is `held` like any folder agent-sync did not create, and `--adopt <name>` takes
it over.

## The report

Every run prints one table, one row per marketplace, plugin and skill, in a fixed order: Claude
Code's marketplaces, then its plugins; Codex's the same way; then `external` and `available`
names, duplicates, and agy last. This is the report the end-to-end test reproduces from fixtures:

```text
agent-sync 0.1.0 · manifest ~/.config/agent-sync/manifest.toml

HARNESS  ITEM                                   RESULT       DETAIL
claude   marketplace example-skills             live         checkout 3f2a91c (clean), digest unchanged
claude   marketplace example-vendor-plugins     unchanged    v2.3.0: 8e01d4a (catalog refreshed)
claude   planning@example-skills                live         0.4.0, enabled, user
claude   reviewing@example-skills               installed    0.2.0, enabled, user
claude   editor-integration@example-vendor-…    held         declared command awaits confirmation:
                                                               `npx -y editor-helper@1.2 build`
                                                               re-run with --accept-command editor-integration@example-vendor-plugins=5c1e…
codex    marketplace example-skills             updated      main: 77b0c2e → 9d14a6f
codex    planning@example-skills                unchanged    0.4.0, cache digest matches 9d14a6f
codex    reviewing@example-skills               stale        cache differs from 9d14a6f at the same version; see "Codex stale cache" in docs/agent-sync.md
codex    find-skills                            external     ~/.agents/skills/find-skills
-        linting@example-vendor-plugins         available    in the catalog, not in the manifest
codex    shaping-briefs                         duplicate    plugin planning@example-skills (~/.codex/plugins/cache/example-skills/planning/0.4.0/skills/shaping-briefs) and ~/.agents/skills/shaping-briefs; run `agent-sync cleanup`
agy      planning/framing-ideas                 copied       3f2a91c (clean), 4 files
agy      reviewing/reviewing-code-changes       unchanged    3f2a91c
agy      my-local-skill                         held         ~/.gemini/config/skills/my-local-skill exists and is not agent-sync's; --adopt my-local-skill

Summary: 3 changed · 3 unchanged · 2 live · 2 held · 1 stale · 1 duplicate · 0 failed
Next:    restart Claude Code sessions or run /reload-plugins · restart Codex sessions ·
         run /skills reload in agy
Exit 1 (stale items)
```

The hash is shortened here; the report prints all 64 characters, so the line can be copied as it
stands. `--json` prints the same rows as JSON lines, with the summary last. Rows that need you —
`failed`, `stale`, `held`, a mismatch, `unverifiable`, `duplicate`, `orphaned` — are also written
to stderr, so they survive a redirected stdout.

| Result | Meaning |
|---|---|
| `installed`, `updated`, `copied`, `enabled`, `archived` | Changed in this run; counted together as "changed" |
| `unchanged` | Already what the manifest asks for. A Git refresh that leaves the revision where it was is `unchanged`, with "(catalog refreshed)" |
| `live` | A checkout Claude Code reads in place, or a plugin it loads from one (`readFromFolder`); edits reach new sessions with no run at all |
| `held` | Waiting for you: a declared command to accept, or an agy folder to adopt |
| `stale` | A Codex cache that differs from its source at the same version |
| `duplicate` | One skill reachable twice in one harness |
| `source-mismatch`, `ref-mismatch` | The harness has the marketplace from another source or ref; its plugins are `skipped` |
| `failed` | That item did not happen; the rest of the run went on |
| `unverifiable` | A source or cache in a shape agent-sync does not recognise, or `--check` has no applied revision to compare with; nothing was changed on a guess, and a marketplace's plugins are `skipped` |
| `unchecked` | Only in `--dry-run` and `--check`: what a run would do, with the exact command |
| `unknown` | Only in `--dry-run` and `--check`: the harness's home is missing or empty, so it was not called |
| `skipped`, `orphaned`, `external`, `unmanaged`, `available` | Reported, never acted on |

| Exit | Meaning |
|---|---|
| 0 | Everything requested is in place. Warnings do not change this |
| 1 | Something failed, a cache is stale, or a source or ref differs. With `--check`: any drift |
| 2 | Usage or manifest error; nothing ran |
| 3 | Items are held for you, and nothing failed |
| 4 | Prerequisite missing: Python older than 3.11, `git` for a Git source, or another run holds the lock |
| 130 | Interrupted; the report above it is partial, and the state holds what finished |

`stale` outranks `held`: a run with both exits 1, because a stale cache is exactly the silent
drift this exists to surface.

A run that finds nothing to do changes nothing of agent-sync's: not the state file, not the
archive, not a single agy folder. It still records its PID in the lock and rewrites
`last-run.log`. It also still asks each harness to refresh, because only the harness can say
whether its copy has moved: `git fetch` into agent-sync's own cache, Claude Code's
`marketplace update` and `plugin update`, and Codex's `marketplace upgrade`. Those verbs write
whatever the harness writes. A declared command you accepted earlier runs again under
`plugin update`; see [Held commands](#held-commands-and-the-hash-that-accepts-them).

`--dry-run` writes nothing at all, not even the lock and the log, and does not fetch. `--check`
fetches into agent-sync's own cache, changes nothing else, and exits 1 on drift. Neither calls a
harness whose home is missing or empty, because its first list command would initialise that home
(contract test C1). That harness's row is `unknown (home not initialised)`. A harness that is not
installed is `skipped` and is not drift, unless you named it in `--only`.

A harness's list output is checked entry by entry. One entry of the wrong shape, such as a plugin
without an id, fails that harness's row, and nothing it listed is acted on. The other harnesses
carry on.

`--check` compares against the revision agent-sync last *applied*, which the state file records.
It never compares against agent-sync's own cache, which the check's fetch has just moved. A
marketplace has no applied record after a first run on a machine set up by hand, or after you
move the state file aside. It stays `unverifiable` until a run records one. Claude Code's plugins
each carry their own applied revision, never their marketplace's. A plugin agent-sync has not yet
applied, including one whose update was held or failed, has none, and `--check` reports it
`unchecked` until a run applies it.

## Codex stale cache

**Codex has no plugin update verb, and its refresh can skip.** `codex plugin marketplace upgrade`
refreshes a Git marketplace's snapshot and the caches of the plugins installed from it. The first
upgrade after the marketplace is added always refreshes. After that, it refreshes only when the
ref has moved since Codex last looked. With an unmoved ref it reports no upgraded roots and
touches nothing. The verb works on the whole marketplace, so it also refreshes plugins from that
marketplace that the manifest does not manage; Codex has no narrower verb.

Codex copies a plugin into `$CODEX_HOME/plugins/cache/<marketplace>/<plugin>/<version>/` at
install, so a cache written from one revision can sit under the same version number while the
source has moved on: a catalog that changed a skill without bumping the plugin's version, an
upgrade that ran while the ref looked unmoved, or a `checkout` source edited after install.

agent-sync therefore checks rather than trusts. After the refresh, it compares each managed
plugin's skills in the Codex cache with the same plugin in the source, at the revision just
applied, and it decides on what the cache physically holds. A skill the source selects that the
cache lacks is `stale`. So are different skill folders, a different `plugin.json` (it decides
which skills Codex loads from the cache), and different bytes in any selected skill. That catches
a skill added, removed, renamed, or dropped from the plugin's `skills` list upstream. Equal is
`unchanged … cache digest matches <revision>`; different is `stale`. The cache layout is not a
documented interface, so a layout agent-sync does not recognise is `unverifiable`, never a
failure and never a repair.

A successful answer from `codex plugin add` is not taken as proof either. Every install and repair
is settled against the plugin list taken after it. A plugin missing from that list, or listed as
disabled, is `failed`, and the cache is compared at the version the list now reports. A managed
plugin you disabled in Codex is `failed` too, since agent-sync has no verb to enable it.

`--repair` reinstalls the plugins of `stale` rows, and only those, with `codex plugin add`.
Contract test C3 showed that `add` on an installed plugin at the same version replaces the stale
cache with the source's bytes, and that a failed `add` leaves the old cache intact. The
replacement is Codex's own directory swap, which is not shown to be atomic. `codex plugin remove`
followed by `add` is not used: it deletes the cache first, so a failed `add` leaves the plugin
gone.

This is also why Git is the recommended Codex source. A `checkout` source works for Codex, but
every edit makes it `stale` until a `--repair`.

## Held commands, and the hash that accepts them

A catalog can declare that a plugin is installed by running a command on your machine. Claude
Code shows that command and wants it confirmed; its help says `-y` is "required when stdin or
stdout is not a TTY". **agent-sync never passes `-y`**: that runs whatever a catalog declares,
unread.

Instead, the plugin is `held`. The row prints the command and the hash Claude Code computed for
it, and the line to re-run with: `--accept-command <plugin>@<marketplace>=<sha256>` passes that one
hash to that one install. agent-sync refuses a hash for a plugin outside the manifest's
marketplaces.

What contract test C4 established about the result, because it is not what the help suggests:

- **The JSON is the last line of stdout**, after four human-readable lines, even with `--json`.
- **A held command is not a distinct outcome.** It is `outcome: "failed"` with exit 1 — the same
  exit as a real failure — distinguished only by `failureCode: "command_source_refused"` and a
  `shownCommand` carrying the `sha256`. agent-sync classifies on those, never on the exit code.
- **A hash covers the catalog revision.** One shown before the catalog moved is refused for a
  fresh install, and a new hash is shown.
- **An accepted command is remembered.** `update` re-runs it through later catalog moves with no
  hash and no prompt, until the command's text or mode changes. So a plugin you accepted once is
  held again only when its command changes.

## Codex treats a stray word as a prompt

Codex forwards anything it does not parse as a subcommand to its interactive CLI as a prompt. A
misspelt subcommand, or a shell passing `"plugin --help"` as one word, starts a model session
instead of failing. agent-sync runs every harness command as an argument list, never through a
shell, with stdin set to `/dev/null`. With stdin closed, a misparse fails at once with
`Error: stdin is not a terminal`, and that becomes the item's `failed` row.

The same trap bites when reading help by hand: zsh does not word-split `$var`, so a loop doing
`codex $sub --help` passes the subcommand as one argument.

## Claude Code's list commands connect out

`claude plugin list --json` and `claude plugin marketplace list --json` look read-only. Contract
test C1 showed that each one queues a telemetry file under the Claude home and opens an outbound
connection, which would make `--dry-run` neither read-only nor offline. Setting
`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` stops both. agent-sync sets it on those two calls and
nowhere else; its effect on the mutating verbs is unmeasured, so they run with your environment
as it is.

`DISABLE_TELEMETRY=1` is not a substitute: since 2.1.332 it stops the file but not the connection
attempt.

Also since 2.1.332, `plugin list` includes plugins bundled with Claude Code itself, named
`<name>@builtin`, even in an empty home. They come from no marketplace, so agent-sync neither
manages them nor reports them as `unmanaged`.

## The ref lives only in Codex's settings

A manifest `ref` pins a branch or tag. Codex takes it as `marketplace add --ref`. Claude Code's
help lists no ref option, but its `add` accepts the ref as a `#<ref>` suffix on the Git source,
clones that ref, and reports it back in `marketplace list`; agent-sync passes it that way.

Checking the ref later is where the harnesses differ. Claude Code's `marketplace list` reports
it. Codex's does not: each entry carries a name, a root and the source, and the ref is only in
`$CODEX_HOME/config.toml`, under `[marketplaces.<name>]`. agent-sync reads that file, never writes
it, and reports `unverifiable` for that one check if the file or table is not what it expects.

The ref is compared in both directions. Say the manifest drops its `ref` while Codex still
records `ref = "main"`. That is a `ref-mismatch`, not a match, because Codex keeps following the
pin. If the file cannot be read, the table is missing, or the ref is not a string, the marketplace
is `unverifiable` and its plugins are `skipped`. Nothing is upgraded on a guess.

A ref or source that differs is reported with the commands to change it by hand, never fixed.
Credentials in a URL are shown as `***`, there and in every printed command.
Contract test C5 is why: `codex plugin marketplace remove` hides the marketplace's plugins without
uninstalling them, leaving their cache and their enable entry orphaned, and re-adding the source
brings them back as installed. Removing and re-adding is therefore safe to do by hand, and it is
also an uninstall in all but name, which a sync must not do on its own.

## A skill must not appear twice

agent-sync prevents what it could cause, and reports what it finds. On every run, for Claude Code
and Codex, a name can come both from an enabled managed plugin and from that harness's flat
folder. That is a `duplicate` row naming both, with the plugin's skill at the path the harness
actually loads it from. The check runs after the run's own installs, so if a first install
starts to shadow a flat copy, that same run reports it. A name under `[external]` is reported
`external` instead. `~/.agents/skills/synced/`, which an account sync fills, is never looked
inside.

For agy the same clash cannot happen silently, because agent-sync is the one writing the folder:
a selected skill whose name matches a skill bundled with agy, or a skill of an installed agy
plugin, is `failed (name collision)` and nothing is written for it.

**What it cannot see: Claude Code's cloud skills.** Skills synced from a claude.ai account have no
documented location on disk, so a cloud skill with the same name as a plugin skill is neither
reported nor fixed. The fix is on the account: remove one of the two there.

## The one-time cleanup

`agent-sync cleanup` deals with the duplicates already on the machine. It is a separate
subcommand because a confirmation buried in a sync run is one nobody reads.

Its candidates are the flat folders in `~/.claude/skills/` and `~/.agents/skills/` whose name is a
skill of a plugin the manifest manages and that harness has installed and enabled. For each it
shows what the folder shadows and whether its content is identical to the plugin's or differs,
file by file, and asks: yes, no, a diff, all remaining identical copies, or quit. A differing copy
always asks, because the difference may be a customisation you meant; "all remaining identical"
given at a differing copy keeps that copy. End of input counts as
quit, so a script that cannot answer archives nothing; non-interactive use names each folder with
`--yes <name>…`, and there is no blanket yes.

"Identical" means identical to the tree the harness loads: Claude Code's install or checkout
folder, or Codex's cache at the installed version. The catalog does not count, since it may have
moved on. When that tree cannot be found, the comparison is shown against the catalog, and the
copy never counts as identical, so "all remaining identical" passes over it. "Identical" also
needs both trees actually digested: a copy with a file that cannot be read is equal to nothing. A
candidate that is a symlink, or holds one at any depth, is listed and never archived by any
answer, because moving a relative link changes what it points at. The skills CLI's lock file,
`~/.agents/.skill-lock.json`, may have an entry for the name. A `provenance` line then says so;
cleanup reads that file and never writes it.

The copy is read again when you answer. If it changed while the question was open, it is shown
again and asked about again; with `--yes`, it is not archived and cleanup exits 1. A yes is a
rename into `archive/<timestamp>/<harness>/<name>`. The state file records it in the same protected
step, so Ctrl-C cannot leave a moved folder unrecorded. Nothing is deleted, and
`--restore <timestamp>` puts that run's folders back, each at exactly its old name or not at all.
A name that has since reappeared, even during the restore, or whose archived folder is gone, stays
on record; restore reports it and exits 1. `--restore` with
`--dry-run` shows what it would move and moves nothing. Cleanup logs its own listing commands to
`last-run.log`, as a run does. It exits 1 if it could not read a harness's inventory.

**`skills list` will show archived copies as missing.** The skills CLI that made those copies
keeps a lock file of what it installed. That file belongs to that tool, so cleanup does not edit
it, and the tool's own listing then reports the archived folders as missing. Its updater already
skips local entries, so nothing reinstalls them behind your back.

## How a skill reaches agy

agy gets copies, because it has no way to follow a third-party catalog. That makes agy the one
harness where an edit to a checkout arrives on the next run rather than live, and the report's
"Next" line says to run `/skills reload` in agy.

Each copy is careful about what is already there:

- **Staged and verified.** The skill is copied into a staging folder beside agy's, not inside it,
  digested again, and swapped in with two renames: the old copy into the archive, the new one into
  place. A failure rolls back. The swap and the state record of the new copy are one protected
  step. Ctrl-C waits for both, so the next run never mistakes agent-sync's own copy for a hand
  edit. An archive on another volume fails the skill before anything moves; see
  [Keep the state directory on the home volume](#where-its-own-files-live).
- **Owned, or left alone.** agent-sync records every folder it creates, with its digest. A folder
  it did not create is `held` and never replaced without `--adopt <name>`, which archives it
  first. A folder it created but that has since been edited is held the same way, so an edit made
  inside agy is not lost to the next run.
- **Removed only on request, and only when certain.** A skill that leaves the manifest is reported
  `orphaned`, and `--prune` archives it — but only in a run that read every agy source, catalog,
  `plugin.json`, declared path and skill listing without a single error. Any error skips prune
  for the whole run, with one `skipped` row naming what could not be read: a failed fetch, a
  catalog not fetched yet, a malformed `plugin.json`, a declared path that is missing, an
  `agy_skills` name the plugin lacks, or a symlink anywhere in a catalog, dangling or not. An
  unreadable selection says nothing about what was removed. The skills that were read still copy.
- **Names compare the way the volume compares them.** macOS volumes are usually
  case-insensitive, so `Review-note` and `review-note` are one folder. agent-sync probes the
  destination volume and, if it ignores case, folds names for ownership, collisions and prune. A
  case-only rename replaces the copy, and two selected spellings of one name both fail.
- **No symlinks, in either direction.** A source with a symbolic link anywhere in it is refused.
  So is a source reached through a link, such as a plugin folder in a catalog that is a symlink
  to somewhere else. No copy ever creates a link in `$HOME` or brings in a tree from outside its
  catalog. agent-sync's own Git cache is checked out with `core.symlinks=false`, so a tracked
  link arrives as a plain file. If anything on the way to agy's skills folder is a symlink,
  agent-sync refuses to write through it.

## Why it is not part of `install.sh` or `setup.sh`

`install.sh` is offline, bash 3.2 plus coreutils, and places configuration; agent-sync needs
Python 3.11, `git`, the network and signed-in harnesses, and installs plugins. `setup.sh` may use
the network, but agent-sync can stop to ask you to accept a command or adopt a folder, which a
setup run should not do. So you run it by path, `<repo>/scripts/agent-sync`, when you want your
agents brought up to date. Reaching it as plain `agent-sync` waits for the `scripts/` entry on
`$PATH`, which changes `~/.zshenv` and is its own change.

Python 3.11 is the floor because that is where `tomllib` arrived. macOS's `/usr/bin/python3` is
3.9, so the script's first act is a version check that exits 4 and names the fix; the `Brewfile`
installs a current Python.

## The contract tests

Before any of this was relied on, the behaviour the harnesses' help does not state was measured
against the real CLIs, in isolated temporary homes with outbound networking blocked and the real
homes compared before and after.

| Test | Question | Outcome |
|---|---|---|
| C0 | Do the plugin commands work logged out and offline? | Yes, for all three CLIs |
| C1 | Do the list commands write anything? | Claude's do — a telemetry file and an outbound attempt each — until `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`; Codex's and agy's do not |
| C2 | Is a plugin from a Claude directory marketplace read live? | Yes: `plugin list` carries `readFromFolder`, and an uncommitted new skill appears at once |
| C3 | Does `codex plugin add` repair a stale cache at the same version? | Yes; a failed `add` leaves the cache intact; the first `upgrade` after an add refreshes, later ones with an unmoved ref skip |
| C4 | What does a declared command look like without `-y`? | `outcome: failed`, exit 1, `command_source_refused`, the hash in `shownCommand`; see above |
| C5 | What does `codex plugin marketplace remove` do to its plugins? | Hides them, orphans their cache and enable entry; re-adding the source revives them |
| C6 | Does a second `agy plugin install <dir>` pick up a change? | Yes, it replaces the installed copy. Recorded for a later version; v1 installs no agy plugin |

They live in `agent-sync/tests/contract/` and are skipped unless `AGENT_SYNC_CONTRACT=1` is set,
because they need the real CLIs installed. The unit and end-to-end tests run against fake
`claude`, `codex`, `agy` and `git` modelled on those recorded outputs, in a temporary home, and
need nothing but Python:

```sh
python3 -m unittest discover -s agent-sync/tests
```

## Reference

- [ADR 0014](decisions/0014-sync-agent-plugins-through-their-own-clis.md) — the decision, and the
  alternatives that lost.
- [Manual setup, step 3](manual-setup.md#3-sync-agent-plugins-and-skills) — create the manifest,
  run it, run the cleanup; each with a verify and an undo.
- [`agent-sync/manifest.example.toml`](../agent-sync/manifest.example.toml) — the manifest format,
  commented.
- [Agent tooling](agent-tooling.md) — how the harnesses themselves are installed.
