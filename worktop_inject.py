#!/usr/bin/env python3
"""UserPromptSubmit hook — deliver a Worktop GUI decision click to the agent.

When the user clicks an option in the GUI's amber decision panel, gui.pyw writes
their choice to response.json. This hook (wired into a project's settings.json
UserPromptSubmit) reads that file on the next prompt, injects "user chose X" into
the agent's context via hookSpecificOutput.additionalContext, and marks it consumed
so it is delivered exactly once. stdlib only — no deps.

Note: the response channel is per-project but shared across agents in that project;
with multiple concurrent agents a click may reach whichever agent prompts first."""
import sys
import json

from worktop_paths import RESP


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # the agent reads hook stdout as UTF-8
    except Exception:
        pass
    try:
        with open(RESP, encoding="utf-8") as f:
            r = json.load(f)
    except Exception:
        return 0
    if not r or r.get("consumed"):
        return 0
    choice = r.get("choice", "")
    q = r.get("q", "")
    r["consumed"] = True
    try:
        with open(RESP, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False)
    except Exception:
        pass
    msg = f"[Worktop decision] The user clicked: 「{choice}」"
    if q:
        msg += f" (for question: {q})"
    msg += ". Continue accordingly."
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": msg,
    }}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
