# Driving Worktop from an AI agent

Conventions an AI coding agent (Claude Code, etc.) should follow when using Worktop.
Paste the essentials into your project's agent instructions (e.g. `CLAUDE.md` or a memory)
so the agent drives the ball consistently.

Below, `PY` = `…\claude-worktop\.venv\Scripts\python.exe` and `W` = `…\claude-worktop\worktop.py`.
Run them with the **project root as the working directory** (state lands in `<project>/.worktop/`).

## 1. Drive the ball for every task — never let it go stale

- Start:     `PY W task "<title>" ["<subtitle>"] ["<issue/PR url>"]`  then  `PY W steps "a" "b" "c"`
- Progress:  `PY W advance ["log"]`  ·  `PY W step "<name|idx>" <done|active|todo>`  ·  `PY W log "<msg>"`
- Finish:    `PY W done ["log"]`   (flashes a green completion banner, then the card drops)
- Idle:      `PY W idle`

Keep the title link pointed at the task's issue/PR; only valid `http(s)` links are clickable.
The progress bar counts done steps (an `active` step counts as half), so call `advance` as you go.

## 2. Decisions = dual channel, then END the turn (never block)

When you need the user to decide, surface it in BOTH places and stop:

1. `PY W decide "<question>" "<opt1>" "<opt2>" … --id <lane>`   — pops the ball (amber panel).
2. Launch the watcher in the background:  `PY …\worktop_watch.py --lane <lane>`
3. Also write the same **numbered options as plain text in chat**.
4. **End the turn.** The user answers on the ball OR in chat; either wakes you (the watcher
   exits printing the choice, or the user replies).

Do NOT use a blocking in-chat-only picker — a ball click can't satisfy it, so the ball goes dead.

## 3. Never steal focus

The ball is always-on-top and pops open for decisions / completion, but it must never grab
keyboard focus (it uses show + raise, not activate). The user's editor stays the active window.

## 4. Concurrent agents → one lane each

- Every command takes `--id <lane>`; the default is `main`.
- If you are NOT the only agent running, pass a distinct `--id` (e.g. `--id agent2`) so you get
  your own card and your decisions don't collide with others.
- Decision responses are **per-lane** (`response_<lane>.json`); each agent's watcher reads only
  its own lane (`worktop_watch.py --lane <lane>`), so a click routes to the right agent.
- The passive `worktop_inject.py` hook only delivers when `$WORKTOP_LANE` is set — otherwise it
  does nothing, to avoid cross-feeding a click to the wrong agent. Prefer the watcher.

## 5. Text encoding

If you call Worktop from PowerShell, pass ball text as ASCII/English — PowerShell mangles
non-ASCII argv. Use a UTF-8 shell (bash) when the text must be non-ASCII.
