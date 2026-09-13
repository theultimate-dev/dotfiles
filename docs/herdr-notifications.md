# Herdr notifications on macOS

How to get reliable "your agent finished" notifications when you run coding agents inside
[Herdr](https://herdr.dev) in [Ghostty](https://ghostty.org).

Verified against **Herdr 0.9.0**, **Ghostty 1.3.1** and **terminal-notifier 3.1** on macOS 26.

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
[Step 4 of the manual setup guide](manual-setup.md#4-herdr-notifications) carries the file contents,
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

## Making a notification stay on screen

macOS, not Herdr, decides how long a notification stays. Every sender app has an **Alert style** in
System Settings → Notifications: *Temporary*, a banner that leaves after a few seconds and is the
default, or *Persistent*, which stays until you dismiss it (older macOS versions call it *Alerts*).
Herdr's notifications are posted by `terminal-notifier`, so that is the app whose style matters;
Ghostty's own style matters on the days you run an agent in a bare terminal. Until you flip it,
everything is configured correctly and the banner is simply gone before you look up — the symptom
is "nothing happened", not an error.
[Step 5 of the manual setup guide](manual-setup.md#5-allow-notifications-and-make-them-stay-on-screen)
has the click path and the check.

Why this is a hand step and not part of `install.sh`: the setting lives in `com.apple.ncprefs`, a
private property list whose per-app flags are an undocumented bitfield that only takes effect once
the notification daemon restarts. A script writing it would be guessing, and nothing could tell a
scripted flag from your own choice afterwards.

One thing Persistent does not change: while Ghostty is focused it dismisses a notification raised
through `OSC 9` after three seconds, whatever the alert style. `terminal-notifier` posts through
its own app, so Ghostty's focus has no say — one more reason `"system"` beats `"terminal"` here.

## The number on the Dock icon

The badge is not a notification, and Herdr did not send it. Claude Code's `iterm2_with_bell`
channel rings the terminal bell next to the OSC 9, Herdr forwards every bell from a pane to the
outer terminal, and Ghostty's default `bell-features` (`attention,title`) bounces the Dock icon and
counts bells while the window is unfocused. When the alert style is Temporary, that count is the
only trace that survives, which is why it looks as if the badge is all you get.

The bell stays on: it is what Zed's Terminal Threads key their popup on. If the badge is noise once
alerts are Persistent, `bell-features = no-attention` in your Ghostty configuration keeps the
notification and drops the bounce and the badge, and `no-title` also drops the 🔔 in the tab title.
The repo's [`ghostty/config.ghostty`](../ghostty/config.ghostty) carries
`bell-features = no-attention,no-title` commented out, ready to switch on.

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
[step 4 of the manual setup guide](manual-setup.md#4-herdr-notifications) covers installing one for
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
  `"preferredNotifChannel": "iterm2_with_bell"` in `~/.claude/settings.json`). It costs nothing
  inside Herdr and it means the same agent still notifies correctly on the days you run it in a
  bare terminal — the OSC 9 half feeds Ghostty, the bell half feeds terminals that never parse
  OSC 9, such as Zed's Terminal Threads. The channels that were rejected, and why, are in
  [ADR 0008](decisions/0008-keep-one-agent-notification-channel-across-hosts.md).

## One agent setting, three hosts

The same `iterm2_with_bell` value is what makes Claude Code notify correctly wherever it runs. What
differs is who turns the emitted sequence into something you see:

| Host | Claude Code emits | What you see | Sender in System Settings | Stays on screen |
| --- | --- | --- | --- | --- |
| Zed Terminal Threads | BEL; the OSC 9 is ignored | Zed's own popup with a **View** button, when the thread is unfocused; `agent.notify_when_agent_waiting` (default `primary_screen`) governs it | none — Zed draws it | Yes, until dismissed |
| Bare Ghostty | OSC 9 and BEL | Ghostty raises a macOS notification from the OSC 9 (`desktop-notifications = true`); suppressed while the pane is focused, dismissed after 3 s while the window is focused. The bell bounces the Dock icon | Ghostty | Only with Ghostty's style set to Persistent, and only while unfocused |
| Herdr in Ghostty | OSC 9, swallowed by Herdr; BEL, forwarded | Herdr detects the pane state and posts through `terminal-notifier -activate`; the forwarded bell becomes the Dock badge | terminal-notifier | Only with terminal-notifier's style set to Persistent |

Nothing needs configuring on the Zed side. `terminal.bell` defaults to `off` and only controls the
audible sound; the popup does not depend on it. Claude Code's `auto` channel keys on
`TERM_PROGRAM` and sends nothing under Zed — the bell is the whole reason for `iterm2_with_bell`.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Notification icon is a script/scroll; clicking opens Finder | `terminal-notifier` not installed — Herdr fell back to `osascript` |
| No notifications at all while the terminal is focused | `delivery = "terminal"` + the outer terminal's focus suppression. Switch to `"system"` |
| Notifications vanish when several agents finish at once | Ghostty's 1/sec rate limit on `"terminal"` delivery. Switch to `"system"` |
| Nothing fires anywhere | Notification permission not granted for `terminal-notifier` (or your terminal) in System Settings |
| A banner appears, then vanishes after a few seconds | Alert style is Temporary for the sender app — `terminal-notifier` under Herdr, Ghostty otherwise. Set it to Persistent — see [above](#making-a-notification-stay-on-screen) |
| Only a badge on the Ghostty Dock icon | That is the bell. The banner was Temporary and already gone, or the pane was in the active tab while Ghostty was focused — see [above](#the-number-on-the-dock-icon) |
| Two notifications per event | A leftover agent-side notify hook running alongside Herdr — remove the hook |
| Config edits ignored | `herdr server reload-config`; check for typos with `herdr config check` (a bare `[toast]` section is silently wrong — it must be `[ui.toast]`) |

## Reference

- [Herdr configuration docs](https://herdr.dev/docs/configuration/)
- [Ghostty configuration reference](https://ghostty.org/docs/config/reference)
- [ADR 0008](decisions/0008-keep-one-agent-notification-channel-across-hosts.md) — the decision and
  the alternatives that lost
- [Manual setup, step 5](manual-setup.md#5-allow-notifications-and-make-them-stay-on-screen) — the
  permission and the alert style, with a check for each
