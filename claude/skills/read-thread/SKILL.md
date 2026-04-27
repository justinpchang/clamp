---
name: read-thread
description: >
  Read and extract relevant content from a prior Claude Code thread by its
  UUID, referenced as "@@<UUID>" in the user prompt. Renders the thread's
  JSONL transcript and uses a Task subagent to extract only the information
  relevant to the user's current goal. Keeps your context lean while
  preserving important details. Load this skill the moment you see "@@"
  followed by a UUID in user input — the user is asking you to incorporate
  context from a prior thread.
allowed-tools: Task
---

# Read Thread

When the user puts `@@<UUID>` in a prompt, it means: **read the referenced
prior Claude Code conversation and use it as context for what I'm asking
now**.

The point is to get the *relevant* information from the prior thread into
your context — not the raw transcript. Long threads can be many thousands
of tokens; pulling the whole thing in defeats the purpose. Always go via a
`Task` subagent, with a goal-specific extraction prompt.

## When to use this skill

Activate **before** answering the rest of the user's message if any of the
following are true:

- You see `@@<UUID>` (UUID = 8-4-4-4-12 hex chars,
  e.g. `@@c1f913fd-99b8-4e06-b1ed-114c7687a742`) anywhere in the user's
  message.
- The user asks to **"apply the same approach from"**, **"do what we did
  in"**, **"reuse the plan from"**, or **"continue the work from"** a
  thread reference.
- The user pastes a bare UUID and the surrounding context makes it clear
  it refers to a prior thread (e.g. "use what we figured out in
  `c1f913fd-…`").
- A `Continuing work from thread @@<UUID>` handoff prompt is detected —
  this is the canonical signal that a fresh thread is inheriting state
  from a prior one.

Multiple references? Spawn one subagent per UUID, in parallel.

## When NOT to use this skill

- No `@@<UUID>` reference and no thread URL/ID is mentioned.
- The user is asking a generic question that doesn't depend on prior
  conversation context.
- The reference is to the *current* thread — context is already loaded.
- The user wants a summary of a thread *for them* (use `clamp render
  <UUID>` and show it directly; don't go through the extraction skill).

## How it works

Claude Code stores each thread as a JSONL file at:

```
~/.claude/projects/<encoded-cwd>/<UUID>.jsonl
```

`<encoded-cwd>` is the project's absolute path with `/` replaced by `-`
(e.g. `/Users/alice/dev/foo` → `-Users-alice-dev-foo`). If the file isn't
in the current project's encoded dir, glob
`~/.claude/projects/*/<UUID>.jsonl` to locate it.

Each JSONL line is a JSON object; the relevant ones have `type` of
`"user"` or `"assistant"` with a `message.content` array of text /
tool_use / tool_result / thinking blocks.

## Subagent prompt template

For each `@@<UUID>` reference, spawn a `Task` subagent. The two parameters
that matter:

1. **threadID** — the UUID, used to locate the JSONL.
2. **goal** — a *specific* one-sentence statement of what you need to
   extract, drawn from the user's current request. Be concrete: "the SQL
   queries used to compute monthly active users", not "stuff about
   analytics".

Spawn the subagent with a prompt like:

> Read the Claude Code thread JSONL at:
>
> `~/.claude/projects/*/{<UUID>}.jsonl` (glob to find the right project dir)
>
> Each line is a JSON object. Walk through user/assistant messages in
> order, parsing the `message.content` blocks (text / tool_use /
> tool_result / thinking).
>
> **Extract only information relevant to this goal:**
>
>     <one-sentence statement of the user's current task>
>
> Return a concise summary that preserves: decisions made, code patterns
> used, file paths touched, error symptoms encountered, and any code
> snippets directly applicable to the goal. Skip pleasantries, tangents,
> and superseded approaches. If the goal isn't actually addressed in the
> thread, say so plainly rather than padding.

If multiple `@@<UUID>` references are present, spawn one subagent per UUID
in parallel (multiple `Task` calls in a single assistant turn), then
synthesize their summaries.

After the subagent(s) return, **continue with whatever the user actually
asked**, integrating the extracted context.

## Examples

**User input:** `@@c1f913fd-99b8-4e06-b1ed-114c7687a742 apply the same fix here`

You should:

1. Detect the `@@<UUID>` reference.
2. Spawn a `Task` subagent told to read
   `~/.claude/projects/*/c1f913fd-99b8-4e06-b1ed-114c7687a742.jsonl` with
   the goal: *"the bug fix that was applied — file path, diff, and root
   cause."*
3. Apply the equivalent change to the current task's context.

**User input (multiple refs):** `merge the approaches from @@<uuid1> and @@<uuid2>`

Spawn two subagents in parallel, each with a goal scoped to "the approach
taken in this thread for X", then synthesize.

**User input (handoff):**
`Continuing work from thread @@<uuid>. … Next task: implement the export endpoint. …`

Use the @@<uuid> reference to fetch any detail the inline summary skipped
— scope the goal to "the export endpoint design and any existing
implementation work."

## Don't

- Don't ignore the `@@` reference. If it's there, the user expects it to
  influence your answer.
- Don't paste the raw thread back to the user — extract and *use* it.
- Don't read the JSONL inline yourself; delegate to a Task subagent so the
  raw transcript never bloats your context. (This is the whole point.)
- Don't pass a vague goal to the subagent. "Anything relevant" produces
  noise; a concrete goal produces a usable summary.
- Don't get blocked if a UUID is malformed or the file is missing — note
  what you tried and ask the user to clarify.
