# clamp — claude + amp-style thread command palette

A small wrapper that adds Amp's hotkey-driven thread palette to Claude Code.

It runs `claude` inside an isolated `tmux` server (so it doesn't pollute your
own tmux), binds a global hotkey (default `C-g`) to a `tmux display-popup`,
and uses `fzf` for the picker UI.

## What you get

Press the hotkey from anywhere inside the wrapped `claude` session. A popup
opens with three commands:

- **switch**     — fzf list of every prior thread for this project, with a
  formatted transcript in the preview pane. Enter resumes that thread —
  in a *new tmux window* (`claude --resume <uuid>`) so the thread you
  came from keeps running. If the picked thread is already open in some
  window, switch jumps to that window instead of spawning a duplicate.
- **reference**  — same picker, but Enter inserts `@@<uuid> ` into the
  current claude prompt buffer (via `tmux send-keys -l`). Use this to ask
  Claude to read a prior thread.
- **handoff**    — type a one-line prompt for what you want to do next.
  Clamp fires a one-shot `claude -p --model haiku` (override via
  `$CLAMP_HANDOFF_MODEL`) that gets `@@<uuid>` and uses the `read-thread`
  skill to pull only the relevant parts of the prior thread (so long
  transcripts don't blow the context window), then synthesizes a tight
  handoff summary aimed at the next task. Clamp opens a fresh `claude` in
  a new window (the source thread keeps running) and pre-fills its
  prompt with `Continuing work from thread @@<uuid>. … <next task> …
  <summary>`. The new thread can also call the `read-thread` skill on
  `@@<uuid>` to recover any detail the summary skipped.
- **new**        — start a fresh thread (`claude`) in a new window.

Each thread runs in its own tmux window inside the project session, so
switching between them is non-destructive — old claude processes keep
running in the background. The window list is intentionally hidden —
navigate threads via the `switch` palette, not via tmux's window keys.
Quit a thread's claude (`Ctrl-D` or `/exit`) and tmux closes its
window; quit the last one and clamp tears its tmux server down.

Threads are read from `~/.claude/projects/<encoded-cwd>/*.jsonl`, sorted by
mtime, with title = first user message.

## Requirements

- `tmux` ≥ 3.2 (for `display-popup`)
- `fzf`
- `python3`
- `claude` (Claude Code CLI)

## Install

```bash
git clone <this repo> ~/dev/clamp
cd ~/dev/clamp
./install.sh
```

The installer verifies dependencies, symlinks `clamp` into
`~/.local/bin` (or `$PREFIX`), and installs the `read-thread` Claude Code
skill into `~/.claude/skills/`. It's idempotent — re-run anytime.

```bash
./install.sh /usr/local/bin     # custom install dir
./install.sh --skip-skill       # don't symlink the skill
```

## Use

From a regular shell (not already inside tmux):

```bash
clamp                   # run claude in $PWD
clamp ~/dev/myrepo      # run claude in a specific dir
```

That's the entire interface. Inside, press **`C-g`** to open the command
palette (switch / reference / new thread). Quit claude (`Ctrl-D` or
`/exit`) and clamp tears down its tmux server automatically — no daemon
left behind.

Re-run `./install.sh` to upgrade.

`claude` runs with `--dangerously-skip-permissions` by default. Override
via `CLAMP_CLAUDE_FLAGS=...` if you'd rather keep the prompts.

## Thread referencing (the @@-trick)

When you pick **reference** in the palette, clamp inserts `@@<uuid> ` at
your cursor. The installer also drops a Claude Code skill at
`~/.claude/skills/read-thread/` that teaches Claude to:

1. Detect `@@<UUID>` in your message.
2. Read the prior thread (`clamp render <UUID>` or directly from
   `~/.claude/projects/.../UUID.jsonl`).
3. Spawn a `Task` subagent for goal-aware extraction when threads are long.
4. Continue with your actual request, using the extracted context.

To see the rendered thread yourself: `clamp render <UUID>`.

## How it works (architecture)

```
~/.local/bin/clamp start
     │
     │ tmux -L clamp -f tmux.conf new-session  (cwd-named session, window 0 runs `claude`)
     │ tmux -L clamp bind-key -T root C-g  display-popup -E "clamp picker"
     ▼
  isolated tmux server (socket: "clamp")
     │
     │ user presses C-g
     ▼
  tmux display-popup runs `clamp picker` with CLAMP_TARGET_PANE=#{pane_id}
     │
     ├─ switch    → fzf with --preview "clamp render {1}"
     │              if window already tagged with that sid: select-window
     │              else: new-window "claude --resume <id>" and tag it
     │              (existing windows keep running untouched)
     │
     ├─ reference → fzf with --preview "clamp render {1}"
     │              on Enter: tmux send-keys -t $TARGET -l "@@<id> "
     │
     ├─ handoff   → new-window "claude" + deferred-paste of summary
     │
     └─ new       → new-window "claude"
```

Key design choices:

- **Isolated socket.** All bindings live on `tmux -L clamp` so your normal
  tmux config and key bindings are untouched.
- **No supervisor process.** Each clamp session is just a normal tmux
  session; the only "code" running is the bash script invoked by the popup.
- **No state file.** Thread metadata is read live from
  `~/.claude/projects/<cwd>/*.jsonl` every time. There's nothing to keep in
  sync.
- **Preview != live session.** Unlike Amp, the preview pane is a rendered
  transcript of the `.jsonl`, not a live `claude` instance. This is way
  cheaper than spawning a `claude` per thread you scroll past, and gives the
  same functional outcome (you can see the full conversation, scroll it, and
  decide which one to pick).

## Configuration

Environment variables read by `clamp`:

| Var                   | Default | Meaning |
|-----------------------|---------|---------|
| `CLAMP_HOTKEY`        | `C-g`   | tmux key that opens the palette |
| `CLAMP_SOCKET`        | `clamp` | `tmux -L` socket name |
| `CLAMP_HANDOFF_MODEL` | `haiku` | model used for the one-shot summary in `handoff` |

Example: `CLAMP_HOTKEY="M-o" clamp start`

## Why not extend agent-deck?

[`agent-deck`](https://github.com/asheshgoplani/agent-deck) is a great tool
but it's a full Bubble Tea TUI dashboard (~14k lines) that *replaces* your
terminal context with a session manager. Clamp is the opposite: ~250 lines
total, the dashboard is a fzf popup that overlays your existing claude
session and disappears as soon as you pick something.

## Limitations / future work

- The "preview" is a rendered transcript, not a live claude TUI. If you want
  the exact Amp behavior of swapping a real claude session in the
  background as you scroll, we'd need to spawn (and cache) a `claude
  --resume <id>` process per thread you navigate to and use
  `tmux switch-client` between them. Not hard, but materially more code.
- Fresh threads (`new` and `handoff`) can't be tagged with a sid until
  claude assigns one (after the first message lands in the .jsonl). If you
  later use `switch` to resume that thread, you get a duplicate window
  running the same sid. Close the old one, or just don't.
- Cross-project thread browsing isn't supported — clamp only lists threads
  whose `cwd` matches the pane's current path.
