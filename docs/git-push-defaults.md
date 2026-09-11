# git push defaults

Why `git push` on a brand-new branch fails, why the obvious fix does not work, and the two config
keys that actually fix it.

Verified against **git 2.50.1** on macOS. Requires **git 2.37** (June 2022) or newer.

The whole change, as it lands in `git/.gitconfig`:

```
[push]
	autoSetupRemote = true
	default = simple

[branch]
	autoSetupMerge = simple
```

Three lines, of which only two change behaviour — the third pins a value git already defaults to.
The rest of this page is why it takes both of the other two, and why the popular one-key workaround
is worse than the error it silences.

## The failure everyone hits

You branch off the remote's main, do the work, and push:

```sh
git fetch
git switch -c feat/x origin/main
# ... commit ...
git push
```

```
fatal: The upstream branch of your current branch does not match
the name of your current branch.  To push to the upstream branch
on the remote, use

    git push origin HEAD:main

To push to the branch of the same name on the remote, use

    git push origin HEAD

To choose either option permanently, see push.default in 'git help config'.

To avoid automatically configuring an upstream branch when its name
won't match the local branch, see option 'simple' of branch.autoSetupMerge
in 'git help config'.
```

Read that first suggestion again. Git's opening offer is to push your feature branch **onto main**.
It is not wrong to offer it — you did ask for a branch that tracks `origin/main` — but it is the
last thing you want, and it is one keystroke away.

There is a second, friendlier version of this failure. Branch off your *local* main instead and git
says:

```
fatal: The current branch feat/x has no upstream branch.
To push the current branch and set the remote as upstream, use

    git push --set-upstream origin feat/x

To have this happen automatically for branches without a tracking
upstream, see 'push.autoSetupRemote' in 'git help config'.
```

(The branch name is interpolated; everything else is verbatim.)

Two different messages for what feels like one mistake. That difference is the whole story.

## Why `push.autoSetupRemote` alone does not fix it

The second message names the fix, so everyone sets it:

```
[push]
	autoSetupRemote = true
```

And then it does not work. The precondition is stated in `git help config`, and it is easy to read
past: `push.autoSetupRemote` applies **only when the current branch has no upstream.**

`git switch -c feat/x origin/main` gives the branch an upstream. Not the one you want —
`origin/main` — but an upstream all the same, set at creation time by git's default
`branch.autoSetupMerge = true`, which configures tracking whenever the start point is *any*
remote-tracking branch. So on push, git finds an upstream, sees that its name does not match the
branch, and takes the mismatch path. `autoSetupRemote` is never consulted, because the branch was
never in the state it handles.

This is the central trap. Nearly every write-up about this stops at `push.autoSetupRemote = true`,
and it genuinely does work — for people who branch off their local main. Branch off
`origin/main`, which is the safer habit and what most fetch-first workflows teach, and the setting
is inert. You get the same fatal you got before, now with a config key you believe is fixing it.

## The other half: `branch.autoSetupMerge = simple`

```
[branch]
	autoSetupMerge = simple
```

`simple` narrows branch creation: set up tracking **only when the start point is a remote branch
with the same name.** Branching from `origin/main` into `feat/x` no longer configures an upstream at
all, because the names differ.

Which is exactly the state `push.autoSetupRemote` was written for. The two keys compose: one stops
git from attaching a wrong upstream, the other fills in the right one on first push. Note that git's
own error message recommends this key — the last paragraph of the fatal above points at
`branch.autoSetupMerge`. The message tells you both halves; they are just five lines apart and read
like alternatives rather than a pair.

What `simple` does *not* break is the case where the names do match. `git switch feat/x` in a fresh
clone, where `origin/feat/x` exists, still creates a local branch tracking it. Same-name DWIM is
untouched — verified below.

## Why `push.default = simple` is pinned explicitly

It has been git's default since 2.0, so setting it looks redundant. It is pinned for two reasons.

First, the behaviour above is conditional on it. `push.autoSetupRemote` takes effect only under
`simple`, `upstream`, or `current`. Under the old `matching`, everything on this page stops being
true, and nothing in the config would explain why.

Second, a dotfiles repo lands on machines with history. Something older — an ancient global config
carried forward, a corporate default, a half-remembered fix from a decade ago — may have set
`matching` at a scope you are not thinking about. Pinning `simple` makes the file self-explanatory
and makes the other two keys mean what they say.

## Why `push.default = current` is rejected

`current` is the popular workaround: push the current branch to a branch of the same name on the
remote, creating it if needed, upstream or no upstream. The push succeeds. Problem solved.

It is not solved. `current` changes where the push *goes*; it does not touch the upstream. Branch
from `origin/main`, push under `current`, and the remote branch is created correctly — while the
local branch's upstream is still `origin/main`:

```
$ git status -sb
## feat/d...origin/main [ahead 1]
```

Your feature branch now reports itself as **ahead of main**. Every ahead/behind count you read is
against the wrong branch. `git pull` on that branch merges main into it, at whatever moment you
happen to type it, producing a merge commit you never asked for in a branch you are about to open a
PR from. And nothing anywhere reports an error.

A loud failure that stops you is cheaper than a silent wrong answer you act on for a week. That is
the whole argument: `current` trades a `fatal:` you would have fixed in thirty seconds for a
misconfigured branch you will not notice until a review goes strange.

## The evidence

Measured on git 2.50.1 against a throwaway bare remote, isolated via `GIT_CONFIG_GLOBAL`:

| Start point | Config | Push result | Upstream after |
|---|---|---|---|
| local `main` | `autoSetupRemote=true` | creates `origin/feat/a` | `origin/feat/a` |
| `origin/main` | `autoSetupRemote=true` | **fatal**, name mismatch | unchanged |
| `origin/main` | `autoSetupRemote=true` + `autoSetupMerge=simple` | creates `origin/feat/c` | `origin/feat/c` |
| `origin/main` | `push.default=current` | creates `origin/feat/d` | **`origin/main`** |

Row two is the trap; row three is the fix; row four is why the popular workaround was rejected.

Also verified under the chosen pair: pushing from `main` behaves normally, and `git switch feat/c`
in a fresh clone still picks up `origin/feat/c` as its upstream — same-name DWIM is unaffected.

## The one behaviour change to expect

On a freshly created branch, before its first push, `git pull` now errors:

```
There is no tracking information for the current branch.
Please specify which branch you want to merge with.
```

Previously it would have pulled `origin/main`, because that was the inherited upstream. If you are
used to that, this reads like a regression. It is the improvement.

The old behaviour meant `git pull` on an unpublished feature branch silently merged main into your
work. Not because you asked to integrate — because the branch happened to inherit an upstream at
creation and `pull` had somewhere to go. Now the branch has no upstream until you publish it, so
git refuses to guess. Integrating main becomes something you type on purpose:

```sh
git fetch && git rebase origin/main   # or: git merge origin/main
```

The cost is one error message, once per branch, before the first push. What it buys is that
`git pull` never again means "merge some other branch into this one."

## Worktrees

No special handling. Both keys are ordinary global config, and worktrees share the global and repo
config files, so they apply uniformly in every worktree. `git worktree add` uses the same
branch-creation path as `git switch -c` and behaves identically:

| Command | Upstream at creation | After `git push` |
|---|---|---|
| `git worktree add -b feat/w1 ../wt1 origin/main` | none | creates `origin/feat/w1`, tracks it |
| `git worktree add ../feat-w2` (no `-b`) | none | creates `origin/feat-w2`, tracks it |
| `git worktree add ../wt3 feat/w1` (remote exists) | `origin/feat/w1` | normal push |

The second row is the worktree-specific trap, and it is the one thing on this page that gets
*easier* to do wrong. With no `-b`, git names the branch after the **directory basename**. So
`git worktree add ../tmp` creates a branch called `tmp`, and under `autoSetupRemote` a later
`git push` publishes `origin/tmp` without ever asking. Before this change that push would have
failed and made you think about it. Now a throwaway directory name becomes a permanent public
branch name in one command.

Mitigation: name worktree directories deliberately, or always pass `-b` and let the directory be
whatever you like. This is worth a habit, not a config key — there is no setting that can tell a
scratch worktree from a real one.

(The only mechanism by which these keys could vary per worktree is `extensions.worktreeConfig`,
which is not in use here.)

## Requirements

**git 2.37 or newer**, for both `push.autoSetupRemote` and `branch.autoSetupMerge = simple`.
Behaviour on older git is untested here — treat this as a requirement, not an assumption:

```sh
git --version
```

macOS ships a recent enough git on any currently supported release, and `brew install git` is well
ahead of it. The version to worry about is a machine that has been carried forward for years.

## Activation

Run `./install.sh` from the repository root. It writes the include directive into
`${XDG_CONFIG_HOME:-$HOME/.config}/git/config`, and never writes `~/.gitconfig`. That direction
is structure rather than politeness: git reads the XDG file *before* `~/.gitconfig` and the last
value wins, so this repo is a defaults layer that anything of your own overrides automatically,
without either file knowing about the other.

`install.sh` places this include stub inside a named delimited block with pre-modification backups
and atomic writes — see
[ADR 0006](decisions/0006-manage-shared-destinations-with-delimited-blocks.md).

## Reference

- [`git help config`](https://git-scm.com/docs/git-config) — `push.default`, `push.autoSetupRemote`,
  `branch.autoSetupMerge`
- [`git help push`](https://git-scm.com/docs/git-push)
- [`git help worktree`](https://git-scm.com/docs/git-worktree)
