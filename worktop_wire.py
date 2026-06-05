#!/usr/bin/env python3
"""Wire a project to use Worktop: append a concise agent-conventions block to the
project's CLAUDE.md (idempotent — skips if already wired). Run via worktop-wire.bat
from the project root, or:  python worktop_wire.py <project-dir>
"""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MARK = "<!-- worktop-conventions -->"

BLOCK = f"""
{MARK}
## Worktop ball — agent conventions

This project uses the Worktop HUD ball. Install: `{HERE}` · full guide: `{os.path.join(HERE, "AGENTS.md")}`.

- **Drive it every task:** `worktop.py task "<title>" [sub] [url]`, then `steps …`; `advance` / `log` as you go; `done` at the end. Run with the project root as the working directory (state lands in `./.worktop/`).
- **Decisions = dual channel, then END the turn:** `worktop.py decide "<q>" "<opt>" … --id <lane>` + launch `worktop_watch.py --lane <lane>` in the background + also list the numbered options in chat. The user answers on the ball OR in chat. Do NOT use a blocking in-chat-only picker.
- **Concurrent agents:** each extra agent passes a distinct `--id <lane>` (default `main`); decision responses are per-lane.
- Never steal focus; when calling from PowerShell pass ball text as ASCII.
"""


def main(argv):
    proj = os.path.abspath(argv[0]) if argv else os.getcwd()
    md = os.path.join(proj, "CLAUDE.md")
    existing = ""
    if os.path.exists(md):
        with open(md, encoding="utf-8") as f:
            existing = f.read()
    if MARK in existing:
        print(f"[worktop] CLAUDE.md already wired: {md}")
        return 0
    with open(md, "a", encoding="utf-8") as f:
        f.write(BLOCK)
    print(f"[worktop] Appended Worktop conventions to {md}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
