# Worktop

A slim, always-on-top desktop **HUD ball** that shows what your AI coding agent
(Claude Code, etc.) is doing — live task title, sub-steps, progress, log — and lets
you **answer the agent's decisions with one click**. It docks to a screen edge and
collapses into a small pill until something needs your eye.

> 一个常驻桌面的"工作台小球"：实时显示 AI 编码代理正在干什么，并支持一键拍板决策。

Separate process, stdlib + PySide6 only. No project coupling — drop it next to any
project and it tracks that project's agent.

## Features

- **Multi-lane** — one task **card per concurrent agent**; parallel agents never clobber each other.
- **Stacked deck** — extra lanes stack behind the focused card; hover the deck to fan it open, click to switch.
- **Clickable title** — opens the task's issue/PR link (hover / pressed states; only real `http(s)` links are interactive).
- **Decision panel** — the agent asks a question with options; you click (or type a custom reply) and it's delivered back to the agent.
- **Completion banner** — a finished task flashes a prominent green banner, then its card drops away.
- **Edge dock + collapse** — drag to a screen edge and it tucks into a thin pill; hover to reveal. Never steals keyboard focus.

## Requirements

- Windows (the installer is `.bat`; the Python/Qt code itself is cross-platform).
- Python 3.9+ on `PATH` (the `py` launcher or `python`).

## Install

```bat
git clone https://github.com/<you>/claude-worktop.git
cd claude-worktop
install.bat
```

`install.bat` creates a local `.venv` and installs PySide6 into it. Nothing global is touched.

To wire a project so its agent knows the conventions, run **`worktop-wire.bat`** from that project's
root — it appends a short Worktop section (pointing at [AGENTS.md](AGENTS.md)) to the project's `CLAUDE.md`, idempotently.

## Launch

Run from your **project folder** (state lands in `.\.worktop\`):

```bat
C:\path\to\claude-worktop\worktop-launch.bat
```

Or launch it the way an agent would (working directory = the project root):

```powershell
Start-Process "C:\path\to\claude-worktop\.venv\Scripts\pythonw.exe" `
  -ArgumentList "C:\path\to\claude-worktop\gui.pyw" -WorkingDirectory "C:\your\project"
```

## How the agent drives it

The agent calls `worktop.py` (same interpreter, project folder as the working dir).
**This is the convention to give your agent — call it when a task starts and as it progresses:**

```bash
PY="C:/path/to/claude-worktop/.venv/Scripts/python.exe"
W="C:/path/to/claude-worktop/worktop.py"

"$PY" "$W" task  "Migrate the LLM layer" "subtitle" "https://issue-url"   # start a task
"$PY" "$W" steps "recon" "port classes" "compile" "submit"               # set sub-steps
"$PY" "$W" advance "compiled OK"                                         # active -> done, next -> active
"$PY" "$W" log   "note for the log"
"$PY" "$W" done  "all green"                                            # finished -> green banner, card drops
"$PY" "$W" decide "Approach A or B?" "A: fast" "B: safe"                 # ask the user (see below)
```

For **concurrent agents**, each extra one passes a distinct lane so it gets its own card:

```bash
"$PY" "$W" task "Other agent's job" --id agent2
```

Lane id resolves as `--id <lane>` › `$WORKTOP_LANE` › `$CLAUDE_SESSION_ID` › `main`.

### Click-to-answer decisions (Claude Code)

1. **Real-time** (recommended): after `worktop.py decide … --id <lane>`, the agent launches the
   watcher **for that lane** in the background and ends its turn — the user's click wakes it:

   ```bash
   "$PY" "C:/path/to/claude-worktop/worktop_watch.py" --lane <lane>   # background; prints the choice on click
   ```

2. **Passive fallback**: wire the inject hook into the project's `.claude/settings.json`. It only
   delivers when the session's `WORKTOP_LANE` env var is set (so it can't cross-feed a click to the
   wrong agent); otherwise it's a no-op and you rely on the watcher above.

   ```json
   {
     "hooks": {
       "UserPromptSubmit": [
         { "hooks": [ { "type": "command",
             "command": "\"C:/path/to/claude-worktop/.venv/Scripts/python.exe\" \"C:/path/to/claude-worktop/worktop_inject.py\"" } ] }
       ]
     }
   }
   ```

See **[AGENTS.md](AGENTS.md)** for the full set of conventions to give your agent.

## State

Per-project, under `<project>/.worktop/` (`lanes/`, `response_<lane>.json`, `win.json`, `gui.log`).
Override the location with the `WORKTOP_STATE` environment variable. Add `.worktop/` to your project's `.gitignore`.

## Multi-agent

Decision responses are **per-lane** (`response_<lane>.json`): each agent's `worktop_watch.py --lane <lane>`
reads only its own lane, so a click routes to the right agent. The passive `worktop_inject.py` hook delivers
only when `$WORKTOP_LANE` is set (else it's a no-op), so it never cross-feeds a click to the wrong agent.

## Known limitations

- The passive inject hook needs `$WORKTOP_LANE` to deliver; without it, rely on the lane-scoped watcher.
- Bottom-edge docking isn't a dock target (left / right / top are).

## License

MIT — see [LICENSE](LICENSE).
