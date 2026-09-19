# 0012. Replace Glow with Leaf for Markdown

## Status

Accepted

## Context

Yazi uses Glow both to open Markdown and to render its preview pane. Documents also contain
Mermaid diagrams and math that Glow's standard renderer leaves as source. Leaf renders supported
diagrams and formulas in the terminal, provides a table of contents and editor integration, and
has a noninteractive ANSI mode compatible with the existing Piper plugin. Homebrew packages it
as `leaf-markdown-viewer`, consistent with
[0003](0003-install-daily-tools-through-homebrew.md). Both readers render tables; table support
alone does not justify replacement.

## Decision

We use Homebrew-installed Leaf for Markdown reading and Yazi previews.

## Consequences

- One reader supplies full-screen navigation and noninteractive previews through the existing
  Piper plugin.
- Both Yazi commands force Ocean, a built-in dark theme, regardless of the terminal's reported
  appearance.
- Leaf opens micro through `Ctrl+E`; Yazi retains its existing editor menu entries.
- Terminal diagrams do not guarantee browser-equivalent rendering or complete Mermaid compatibility.
- Narrow previews can clip or wrap diagrams; Leaf clamps inline widths to at least 20 columns.
- Existing users must install Leaf before restarting Yazi; configuration stubs need no reinstall.
- Glow leaves the Brewfile, but existing installations remain available for comparison until users
  remove them.
- Leaf's standalone settings remain unmanaged; Homebrew owns installation and updates.

The comparison, renderer behavior, and limitations live in [the Yazi guide](../yazi.md#leaf-and-glow).
This replaces the previous Glow configuration; no earlier ADR selected Glow.

## Alternatives Considered

- Retain Glow — leaves Mermaid diagrams and math as source in the default reading workflow.
- Leaf for opening, Glow for previews — previews would still omit diagrams and math.
- Vendor installer — bypasses the established Homebrew installation channel.
