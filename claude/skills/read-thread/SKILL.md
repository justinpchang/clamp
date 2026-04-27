---
name: read-thread
description: >
  Resolves "@@<UUID>" thread references in user prompts by reading the prior
  Claude Code conversation and extracting context relevant to the current
  task. Load this skill the moment you see "@@" followed by a UUID in user
  input — the user is asking you to incorporate context from a prior thread.
allowed-tools: Task
---

# Read Thread

When the user puts `@@<UUID>` in a prompt, it means: **read the referenced
prior Claude Code conversation and use it as context for what I'm asking
now**.

## When to activate

If you see one or more `@@<UUID>` substrings (UUID = 8-4-4-4-12 hex chars,
e.g. `@@c1f913fd-99b8-4e06-b1ed-114c7687a742`) anywhere in the user's
message, follow the steps below **before** doing the rest of the task.

## What to do

For each `@@<UUID>` reference, spawn a `Task` subagent that reads the
thread's `.jsonl` transcript directly and returns only the distilled context
relevant to the current task. This keeps your own context lean.

### Where the transcript lives

Claude Code stores each thread as a JSONL file at:

```
~/.claude/projects/<encoded-cwd>/<UUID>.jsonl
```

`<encoded-cwd>` is the project's absolute path with `/` replaced by `-`
(e.g. `/Users/alice/dev/foo` → `-Users-alice-dev-foo`). If the file isn't
in the current project's encoded dir, glob `~/.claude/projects/*/<UUID>.jsonl`
to find it.

Each line is a JSON object; relevant ones have `type` of `"user"` or
`"assistant"` with a `message.content` array of text / tool_use /
tool_result / thinking blocks.

### Subagent prompt template

Spawn the subagent with a prompt like:

> Read the Claude Code thread JSONL at:
>
> `~/.claude/projects/*/{<UUID>}.jsonl` (glob to find the right project dir)
>
> Each line is a JSON object. Parse them and walk through user/assistant
> messages in order.
>
> Extract only information relevant to this goal: **<one-sentence
> statement of the user's current task, drawn from the surrounding prompt>**.
>
> Return a concise summary that preserves: decisions made, code patterns
> used, file paths touched, error symptoms encountered, and any code
> snippets directly applicable. Skip pleasantries, tangents, and
> superseded approaches.

If multiple `@@<UUID>` references are present, spawn one subagent per UUID
in parallel (multiple `Task` calls in a single message), then synthesize
their summaries.

### Continue with the user's request

After the subagent(s) return, continue with whatever the user actually
asked, integrating the extracted context.

## Examples

**User input:** `@@c1f913fd-99b8-4e06-b1ed-114c7687a742 apply the same fix here`

You should:
1. Detect the `@@<UUID>` reference.
2. Spawn a `Task` subagent told to find and read
   `~/.claude/projects/*/c1f913fd-99b8-4e06-b1ed-114c7687a742.jsonl` and
   return the fix that was applied (file, diff, rationale).
3. Apply the equivalent change to the current task's context.

**User input (multiple refs):** `merge the approaches from @@<uuid1> and @@<uuid2>`

Spawn two subagents in parallel, one per UUID, then synthesize.

## Don't

- Don't ignore the `@@` reference. If it's there, the user expects it to
  influence your answer.
- Don't paste the raw thread back to the user — extract and use it.
- Don't read the JSONL inline yourself; delegate to a subagent so the raw
  transcript never bloats your context.
- Don't get blocked if a UUID is malformed or the file is missing — note
  what you tried and ask the user to clarify.
