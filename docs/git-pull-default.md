# git pull default

Why a bare `git pull` here only fast-forwards, which commands still rebase and merge, and the one
place where this key overrides a setting of your own.

Verified against **git 2.54.0** on macOS. Behaviour on git older than the 2.37 this repository
already requires is untested.

The whole change, as it lands in `git/.gitconfig`:

```
[pull]
	ff = only
```

## What it does

A bare `git pull` now has two outcomes, and neither of them changes your commits:

| Your branch against its upstream | `git pull` |
|---|---|
| Only behind | fast-forwards |
| Ahead and behind | stops: `fatal: Not possible to fast-forward, aborting.` |

When it stops, nothing has been touched. You pick how to integrate and say so:

```sh
git pull --rebase      # replay your commits on top of the upstream
git pull --no-rebase   # merge the upstream into your branch
```

## Why pin it when git already stops

With no pull setting at all, git also refuses to pull a diverged branch. It prints
`fatal: Need to specify how to reconcile divergent branches.` under a dozen lines of hints that
offer three `git config` commands. So the key looks redundant. It is pinned for the reason
`push.default = simple` is pinned in the [push defaults](git-push-defaults.md): a dotfiles repo
lands on machines with history.

That refusal exists only while no pull setting exists anywhere. One `pull.rebase = false` carried
forward in an old config, set at system scope, or left behind by a tutorial, and a bare `git pull`
merges without asking. With `pull.rebase = true` it rewrites your unpushed commits without asking.
`pull.ff = only` wins over both, from any file, so a bare pull does the same thing on every machine
this repository is installed on.

`pull.rebase = true` was rejected as the default for the same reason. Rebase or merge is a choice
about one branch at one moment. A default makes that choice for every pull, and the day it is the
wrong one you find out afterwards.

## What still rebases and merges

Measured on a branch one commit ahead and one behind, with `pull.ff = only` in effect:

| Command | Result |
|---|---|
| `git pull` | stops |
| `git pull --rebase` | rebases |
| `git pull --no-rebase` | merges |
| `git rebase origin/main` | rebases |
| `git merge origin/main` | merges |

A flag on the command line beats the key. `git rebase` and `git merge` never read it: the key
belongs to `git pull` alone.

## The trap: it beats your own `pull.rebase`

Everything in this repository's git layer is a default that your `~/.gitconfig` overrides. That
rule holds key by key: a `pull.ff` of your own beats this one. But `pull.rebase` is a different
key, and git settles the two against each other after reading every file. Fast-forward-only wins.

So a `pull.rebase` you set years ago stops working for diverged branches the day this layer is
installed, and nothing reports it. Measured with this key in `~/.config/git/config` and the left
column in `~/.gitconfig`, on a diverged branch:

| Your own config | Bare `git pull` |
|---|---|
| nothing | stops |
| `pull.rebase = true` | **stops** |
| `pull.rebase = false` | **stops** |
| `branch.<name>.rebase = true`, in the repository | **stops** |
| `pull.rebase = true` and `pull.ff = true` | rebases |
| `pull.rebase = false` and `pull.ff = true` | merges |
| `pull.ff = true` alone | merges |

To keep a bare pull that rebases, set both keys in `~/.gitconfig`:

```
[pull]
	rebase = true
	ff = true
```

The last row of the table is a second trap. `pull.ff = true` on its own does not bring back git's
stock refusal: it makes a bare pull merge. No value of `pull.ff` restores the stock message, and a
later file cannot unset a key an earlier one set.

## When it says "multiple branches"

```
fatal: Cannot fast-forward to multiple branches.
```

You get this on a branch that is only behind, where a fast-forward is plainly possible. Nothing is
wrong with the branch. Another `git fetch` ran in the same working tree at the same moment: a
coding agent, an editor, a script. Both wrote their results to `FETCH_HEAD`, the file now lists
the branch twice, and `git pull` counts two branches to integrate.

Run `git pull` again.

Without this key the same collision prints
`fatal: Need to specify how to reconcile divergent branches.`, which sends you looking for a
divergence that does not exist. Racing a background `git fetch` against `git pull`, on a branch
that was only behind, left the branch listed twice. Naming the branch twice by hand, with
`git pull origin main main`, prints each message: the first with the key, the second without.

## Branches that have no upstream yet

This key changes nothing there. Under the [push defaults](git-push-defaults.md) a new branch has no
upstream until its first push, so `git pull` on it reports that there is no tracking information.
That page covers how to bring such a branch up to date with main.

## Activation

None, once the include is in place. `git/.gitconfig` is read live through the include directive
`./install.sh` wrote, so the key is in effect as soon as your checkout of this repository contains
it. [Activation](git-push-defaults.md#activation) in the push defaults covers that include.

To see which file supplies the value git uses:

```sh
git config --show-origin --get-all pull.ff
```

The last line printed is the one in effect.

## Reference

- [`git help config`](https://git-scm.com/docs/git-config) — `pull.ff`, `pull.rebase`,
  `branch.<name>.rebase`
- [`git help pull`](https://git-scm.com/docs/git-pull)
