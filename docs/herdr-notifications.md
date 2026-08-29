# Herdr notifications on macOS

How to get reliable "your agent finished" notifications when you run coding agents inside
[Herdr](https://herdr.dev) in [Ghostty](https://ghostty.org).

Verified against **Herdr 0.8.x** and **Ghostty 1.3** on macOS.

## The problem this solves

Every modern terminal can raise native macOS notifications on behalf of the app running inside it —
Ghostty does this via the `OSC 9` / `OSC 777` escape sequences, gated by
`desktop-notifications = true`. Every modern coding agent knows how to emit those sequences. So on a
bare terminal you configure the agent and you are done.

**A multiplexer breaks that chain.** Herdr is a terminal emulator in its own right: it owns the PTY,
parses the escape sequences your agent writes, and paints its own frame into the outer terminal. The
agent's `OSC 9` stops at Herdr. Ghostty never sees it.

So the moment you start running agents inside Herdr, your terminal-side notification setup goes
quiet and **Herdr's own configuration becomes the only thing that matters**. Herdr replaces the
mechanism entirely: instead of relaying what the agent emitted, it detects agent state per pane and
generates its own notifications, formatted as `<agent> finished` / `<agent> needs attention` with a
`workspace · number · tab` subtitle.

This is an upgrade, not a workaround — Herdr knows which *pane* you are looking at, while a terminal
only knows whether its window is focused. But it does need configuring.

## The four delivery modes

Everything is driven by one key in `~/.config/herdr/config.toml`:

```toml
[ui.toast]
delivery = "system"
```

| Value        | What happens                                                    | Works over SSH |
| ------------ | --------------------------------------------------------------- | -------------- |
| `"off"`      | No popups at all.                                                 | —              |
| `"herdr"`    | In-app toast drawn inside the Herdr TUI. Never leaves the terminal. | ✅ (it's just text) |
| `"terminal"` | Herdr emits an `OSC 9` to the **outer** terminal, which raises the OS notification. | ✅ |
| `"system"`   | Herdr calls the local OS notification service directly, bypassing the terminal. | ❌ (fires on the remote host) |

On macOS, `"system"` uses [`terminal-notifier`](https://github.com/julienXX/terminal-notifier) if it
is on `PATH`, and falls back to `osascript` if it is not. On Linux it uses `notify-send`.

## Recommended setup: local agents on macOS

Herdr reads `~/.config/herdr/config.toml`, and four values in it are worth setting deliberately.
[Step 5 of the manual setup guide](manual-setup.md#5-herdr-notifications) carries the file contents,
the reload command and the rollback; this section is why each value is what it is.

**`delivery = "system"`, under `[ui.toast]`.** The one that matters. Herdr owns the PTY, so the
terminal-side path is already broken before you configure anything, and `"system"` is what replaces
it — Herdr calling the OS notification service itself rather than asking the terminal to. The
section below on `"terminal"` is the long argument for choosing it over the intuitive alternative.

**`delay_seconds`, left at its default of `1`.** It swallows state changes shorter than the delay,
which is what keeps a fast tool call from flashing a banner at you. Lowering it does not make you
better informed; it turns every momentary pause into an interruption.

**`enabled = true`, under `[ui.sound]`.** A banner you have to be looking at the screen to see is
half a notification, and the point of running several agents at once is that you are not watching
any of them. Per-agent overrides live in `[ui.sound.agents]` and are worth knowing about before you
turn sound on globally: one chatty agent is the usual reason people give up on notification sounds
entirely, and muting just that one is cheaper than going silent everywhere. [Sounds](#sounds) below
covers the formats and path rules.

**`open_notification_target`, bound under `[keys]`.** A banner tells you *that* an agent finished,
not which of them did — and across a fleet of panes that is most of the question. The binding jumps
to the pane behind the last notification, which is what turns the banner into navigation rather than
a nudge to go hunting.

None of this needs a restart: Herdr validates and hot-reloads the file on request, which is also the
quickest way to discover that a table name was typed wrong. On macOS, though, judge nothing until
`terminal-notifier` is on `PATH` — without it every notification still fires, and every one of them
arrives wearing the wrong application's face.

### Why `terminal-notifier` is not optional in practice

Without it, Herdr shells out to `osascript -e 'display notification …'`. macOS attributes those
notifications to **Script Editor** — you get the wrong icon, and clicking the notification dumps you
into Script Editor or a Finder window instead of your terminal. There is nothing Herdr can do about
that; it is how macOS treats notifications posted by an unbundled AppleScript.

With `terminal-notifier` present, Herdr reads `TERM_PROGRAM`, maps it to the host terminal's bundle
id (it knows `com.mitchellh.ghostty`, `com.googlecode.iterm2`, `com.github.wez.wezterm`,
`com.apple.Terminal`) and passes it to `terminal-notifier -activate`. Clicking now raises your
terminal. Bind `open_notification_target` and you can go from banner to the exact pane in two
keystrokes.

> First notification after installing will be silent until you allow notifications for
> `terminal-notifier` in **System Settings → Notifications**.

## Why not `delivery = "terminal"`?

It is the intuitive choice — let the terminal you already configured do the work — and it is the
*wrong* choice for a multi-agent workflow on a local machine. Two reasons, both structural.

**1. Your multiplexer is one surface.** Ghostty decides whether to present an `OSC 9` notification
with this rule (`macos/Sources/Ghostty/Ghostty.App.swift`):

```swift
return !window.isKeyWindow || !surface.focused
```

That is: *suppress if the surface that sent it is focused in the key window*. For a bare terminal
that is exactly right. But a whole Herdr session — every workspace, every tab, every pane — is a
**single** Ghostty surface. So whenever the Ghostty window is focused, Ghostty drops the
notification, even though you are looking at a completely different Herdr workspace than the agent
that just finished. You lose precisely the notification you most wanted: the background agent
finishing while you work in the foreground one.

Herdr's own suppression is pane- and tab-aware and already got this right; the terminal then
second-guesses it with coarser information.

**2. Ghostty rate-limits.** The core enforces one desktop notification per second globally, plus a
5-second dedupe window for identical title+body (`src/Surface.zig`). Fleet a dozen agents and
finishes that land in the same second are silently dropped. `"system"` has no such ceiling.

`delivery = "system"` sidesteps both by making Herdr the single authority on when you get notified.

### When `"terminal"` *is* the right answer

Use it for **remote sessions** — `herdr --remote <ssh-target>`, or Herdr running on a dev box you
SSH into. `"system"` would raise the notification on the remote machine, where nobody is looking at
it. `"terminal"` travels down the SSH connection as an escape sequence and surfaces on your laptop.
The focus suppression caveat still applies, but a notification on the wrong machine is strictly
worse.

A reasonable split is `"system"` in your dotfiles and `"terminal"` in the `config.toml` on remote
hosts.

## When Herdr suppresses a notification

Worth knowing so you can tell "configured wrong" from "working as designed":

- **The active tab is suppressed.** If the agent is in the tab you are looking at, no popup.
  Suppression is tab-aware, not workspace-wide, so a background tab in your *current* workspace
  still alerts.
- **A focused pane still alerts when the terminal window is unfocused.** Switch to your browser
  while an agent runs and you will still hear about it.
- **`delay_seconds`** (default `1`) swallows state changes shorter than the delay, so a fast tool
  call does not flash a banner at you.

## Sounds

```toml
[ui.sound]
enabled = true
path = "sounds/notification.mp3"   # one sound for everything
done_path = "sounds/done.mp3"      # …or split: agent finished
request_path = "sounds/request.mp3" # …and: agent needs input
```

MP3 only. Relative paths resolve against the config directory. Per-agent control lives in
`[ui.sound.agents]` with `"default"` / `"on"` / `"off"` — handy for muting one chatty agent without
going silent everywhere.

## Agent-side setup

Herdr ships integrations that teach each agent to report its session to the multiplexer. `setup.sh`
registers them for every agent whose configuration directory already exists;
[step 5 of the manual setup guide](manual-setup.md#5-herdr-notifications) covers installing one for
an agent that arrived afterwards.

For Claude Code the integration drops `~/.claude/hooks/herdr-agent-state.sh` and registers it as a
`SessionStart` hook in `~/.claude/settings.json`. The hook only reports the session id over Herdr's
Unix socket — it never notifies. Detection of finished / needs-attention is Herdr's, from the pane
contents.

Two things follow:

- **Do not add Stop/Notification hooks that shell out to a notifier.** They will double-fire
  alongside Herdr, and a synchronous `osascript` in a Stop hook can block the agent for the length
  of the hook timeout.
- **Leave the agent's own notification channel enabled anyway** (for Claude Code,
  `"preferredNotifChannel": "iterm2"` in `~/.claude/settings.json`). It costs nothing inside Herdr
  and it means the same agent still notifies correctly on the days you run it in a bare terminal.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Notification icon is a script/scroll; clicking opens Finder | `terminal-notifier` not installed — Herdr fell back to `osascript` |
| No notifications at all while the terminal is focused | `delivery = "terminal"` + the outer terminal's focus suppression. Switch to `"system"` |
| Notifications vanish when several agents finish at once | Ghostty's 1/sec rate limit on `"terminal"` delivery. Switch to `"system"` |
| Nothing fires anywhere | Notification permission not granted for `terminal-notifier` (or your terminal) in System Settings |
| Two notifications per event | A leftover agent-side notify hook running alongside Herdr — remove the hook |
| Config edits ignored | `herdr server reload-config`; check for typos with `herdr config check` (a bare `[toast]` section is silently wrong — it must be `[ui.toast]`) |

## Reference

- [Herdr configuration docs](https://herdr.dev/docs/configuration/)
- [Ghostty configuration reference](https://ghostty.org/docs/config/reference)
