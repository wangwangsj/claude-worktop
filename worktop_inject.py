#!/usr/bin/env python3
"""UserPromptSubmit hook — deliver THIS lane's Worktop decision click to the agent.

Reads a PER-LANE response file response_<lane>.json where lane = $WORKTOP_LANE. If
WORKTOP_LANE is NOT set, this does NOTHING — preventing cross-agent leakage (a click on
one agent's card must not be injected into a different agent's prompt). With multiple
concurrent agents, prefer the lane-scoped worktop_watch.py for delivery. stdlib only."""
import sys
import os
import json

from worktop_paths import STATE_DIR


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # the agent reads hook stdout as UTF-8
    except Exception:
        pass
    lane = os.environ.get("WORKTOP_LANE")
    if not lane:
        return 0  # no session lane -> no passive delivery (avoid cross-agent leak)
    resp = os.path.join(STATE_DIR, "response_" + lane + ".json")
    try:
        with open(resp, encoding="utf-8") as f:
            r = json.load(f)
    except Exception:
        return 0
    if not r or r.get("consumed"):
        return 0
    choice = r.get("choice", "")
    q = r.get("q", "")
    r["consumed"] = True
    try:
        with open(resp, "w", encoding="utf-8") as f:
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
