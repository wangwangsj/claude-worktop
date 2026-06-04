#!/usr/bin/env python3
"""Real-time link: block until the user clicks a Worktop decision option, then
print the choice and exit. Run in the BACKGROUND — its exit re-invokes the agent
with the click, so the user never has to type/press-enter. Polls response.json
(per-project, see worktop_paths). stdlib only.

Pair with `worktop.py decide ...`: present a decision, launch this watcher in the
background, end the turn; the user's click wakes the agent with their choice."""
import sys
import json
import time

from worktop_paths import RESP


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    deadline = time.time() + 3600  # 1h safety cap
    while time.time() < deadline:
        try:
            with open(RESP, encoding="utf-8") as f:
                r = json.load(f)
        except Exception:
            r = None
        if r and not r.get("consumed") and r.get("choice"):
            r["consumed"] = True
            try:
                with open(RESP, "w", encoding="utf-8") as f:
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
