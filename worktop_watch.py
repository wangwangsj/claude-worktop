#!/usr/bin/env python3
"""Real-time link: block until the user clicks THIS lane's Worktop decision option,
then print the choice and exit. Run in the BACKGROUND — its exit re-invokes the agent
with the click. Reads a PER-LANE response file (response_<lane>.json) so each agent
only sees its own lane's clicks. Lane = --lane <lane> | $WORKTOP_LANE | main. stdlib only.

Pair with `worktop.py decide --id <lane>`: present a decision, launch this watcher with
the SAME lane in the background, end the turn; the user's click wakes the agent."""
import sys
import os
import json
import time

from worktop_paths import STATE_DIR


def _lane(argv):
    for i, a in enumerate(argv):
        if a == "--lane" and i + 1 < len(argv):
            return argv[i + 1]
    return os.environ.get("WORKTOP_LANE") or "main"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    lane = _lane(sys.argv[1:])
    resp = os.path.join(STATE_DIR, "response_" + lane + ".json")
    deadline = time.time() + 3600  # 1h safety cap
    while time.time() < deadline:
        try:
            with open(resp, encoding="utf-8") as f:
                r = json.load(f)
        except Exception:
            r = None
        if r and not r.get("consumed") and r.get("choice"):
            r["consumed"] = True
            try:
                with open(resp, "w", encoding="utf-8") as f:
                    json.dump(r, f, ensure_ascii=False)
            except Exception:
                pass
            print(f"[Worktop] User picked: 「{r.get('choice')}」 (question: {r.get('q', '')}). Continue accordingly.")
            return 0
        time.sleep(0.25)
    print("[Worktop] Timed out (1h) waiting for a choice.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
