# 0008. Keep one agent notification channel across Zed, Ghostty and Herdr

## Status

Accepted

## Context

Claude Code runs in three hosts on the same machine, and each turns "agent finished" or "needs
input" into a notification differently. Zed's Terminal Threads never parse OSC 9; they raise their
own persistent popup when an unfocused thread rings the terminal bell. Bare Ghostty turns OSC 9 into
a macOS notification and answers the bell with a Dock bounce. Herdr owns the PTY, swallows the
agent's OSC 9, detects pane state itself, and posts through `terminal-notifier`. macOS decides per
sender app whether a notification is Temporary (gone in seconds) or Persistent, and stores that
choice in a private preference file with no supported write path. In the private original, a
synchronous notifier in a Stop hook once blocked Claude Code for the full 600-second hook timeout.

## Decision

We set `preferredNotifChannel` to `iterm2_with_bell` as the only agent-side notification setting,
keep Herdr on `delivery = "system"`, and leave persistence to the macOS Alert style set by hand.

## Consequences

- One Claude Code setting serves all three hosts; nothing is switched when moving between Zed and
  Herdr.
- Persistence is a GUI toggle per sender app; no installer takes it over, so the manual guide
  carries it.
- The bell also bounces Ghostty's Dock icon and counts a badge; `bell-features` is the documented
  opt-out.
- No `Notification` or `Stop` hook calls a notifier: it double-fires beside Herdr and can block the
  agent.
- Bare Ghostty dismisses a notification after three seconds while focused, whatever the alert
  style.
- Herdr stays silent for the active tab while the terminal is focused; that is by design.

## Alternatives Considered

- Claude Code `Notification`/`Stop` hooks running `terminal-notifier` — double-fire beside Herdr,
  and a synchronous hook once blocked the agent for 600 seconds.
- `preferredNotifChannel = auto` or `ghostty` — `auto` sends nothing in Zed; the `ghostty` channel
  emitted nothing when tested.
- Herdr `delivery = "terminal"` — window-level focus suppression, one notification per second, and
  the three-second auto-dismiss while focused.
- Scripting `com.apple.ncprefs` for Persistent alerts — an undocumented flag bitfield that needs the
  notification daemon restarted and cannot be told apart from a user's choice afterwards.
