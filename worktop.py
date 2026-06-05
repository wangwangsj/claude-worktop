#!/usr/bin/env python3
"""Worktop — progress-state writer (stdlib only). Global, multi-lane.

Each Claude CONVERSATION writes its OWN lane file (<state>/lanes/<lane>.json); the GUI
globs the GLOBAL lane dir and shows one card per conversation, grouped by project. The
lane defaults to the conversation id and the project to the working-dir name, so no flags
are needed — just run worktop.py from the project folder.
Lane id resolves as:  --id <lane>  >  $WORKTOP_LANE  >  $CLAUDE_CODE_SESSION_ID  >  'main'
Project resolves as:  $WORKTOP_PROJECT  >  basename(cwd).

Commands (all operate on the current lane):
  task "<title>" ["<subtitle>"] ["<link>"]  start a new task (clears steps + log)
  steps "a" "b" "c" ...           set the sub-step list (first becomes active)
  step "<name|index>" <status>    set one step's status (done|active|todo)
  advance ["log msg"]             current active -> done, next todo -> active
  log "<msg>"                     append a timestamped log line
  done ["log msg"]                mark all steps done, state=done
  idle                            state=idle (waiting)
  link "<url>"                    set the clickable issue/CL URL
  decide "<question>" [opt ...]   surface a pending decision (gate / fork)
  resolve ["log msg"]             clear the decision and resume
  drop                            remove this lane's card (end/forget the task)
Global flag (anywhere in argv): --id <lane>
"""
import sys, os, json, tempfile, time
from datetime import datetime

from worktop_paths import LANE_DIR


def _now():
    return datetime.now().strftime("%H:%M:%S")


def _lane_from(argv):
    """Strip `--id <lane>` out of argv; resolve the lane id with fallbacks."""
    lane, out, i = None, [], 0
    while i < len(argv):
        if argv[i] == "--id" and i + 1 < len(argv):
            lane = argv[i + 1]; i += 2; continue
        out.append(argv[i]); i += 1
    lane = lane or os.environ.get("WORKTOP_LANE") or os.environ.get("CLAUDE_CODE_SESSION_ID") or "main"
    lane = "".join(c if (c.isalnum() or c in "-_") else "_" for c in lane)[:48] or "main"
    return lane, out


def _path(lane):
    return os.path.join(LANE_DIR, lane + ".json")


def load(lane):
    try:
        with open(_path(lane), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"title": "", "subtitle": "", "steps": [], "log": [], "state": "idle"}


def save(lane, d):
    os.makedirs(LANE_DIR, exist_ok=True)
    d["lane"] = lane
    d["project"] = os.environ.get("WORKTOP_PROJECT") or os.path.basename(os.path.abspath(os.getcwd())) or "?"
    d["updated"] = _now()
    d["ts"] = time.time()
    fd, tmp = tempfile.mkstemp(dir=LANE_DIR, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _path(lane))


def _log(d, args):
    if args:
        d.setdefault("log", []).append({"t": _now(), "msg": " ".join(args)})
        d["log"] = d["log"][-200:]


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    lane, argv = _lane_from(argv)
    cmd, args = argv[0], argv[1:]
    if cmd == "task":
        save(lane, {"title": args[0] if args else "", "subtitle": args[1] if len(args) > 1 else "",
                    "link": args[2] if len(args) > 2 else "",
                    "steps": [], "log": [], "state": "working", "started": _now()})
    elif cmd == "steps":
        d = load(lane)
        d["steps"] = [{"name": a, "status": "todo"} for a in args]
        if d["steps"]:
            d["steps"][0]["status"] = "active"
        d["state"] = "working"
        save(lane, d)
    elif cmd == "step":
        d = load(lane)
        name = args[0]
        status = args[1] if len(args) > 1 else "active"
        hit = None
        for i, s in enumerate(d["steps"]):
            if s["name"] == name or (name.isdigit() and int(name) == i):
                hit = s
                break
        if hit:
            hit["status"] = status
        else:
            d["steps"].append({"name": name, "status": status})
        save(lane, d)
    elif cmd == "advance":
        d = load(lane)
        steps = d.get("steps", [])
        moved = False
        for i, s in enumerate(steps):
            if s["status"] == "active":
                s["status"] = "done"
                if i + 1 < len(steps):
                    steps[i + 1]["status"] = "active"
                moved = True
                break
        if not moved:
            for s in steps:
                if s["status"] == "todo":
                    s["status"] = "active"
                    break
        _log(d, args)
        save(lane, d)
    elif cmd == "log":
        d = load(lane)
        _log(d, args)
        save(lane, d)
    elif cmd == "done":
        d = load(lane)
        for s in d.get("steps", []):
            s["status"] = "done"
        d["state"] = "done"
        _log(d, args)
        save(lane, d)
    elif cmd == "idle":
        d = load(lane)
        d["state"] = "idle"
        save(lane, d)
    elif cmd == "link":
        d = load(lane)
        d["link"] = args[0] if args else ""
        save(lane, d)
    elif cmd == "decide":
        d = load(lane)
        d["decision"] = {"q": args[0] if args else "", "options": list(args[1:])}
        d["state"] = "decision"
        save(lane, d)
    elif cmd == "resolve":
        d = load(lane)
        d["decision"] = None
        if d.get("state") == "decision":
            d["state"] = "working"
        _log(d, args)
        save(lane, d)
    elif cmd == "drop":
        try:
            os.remove(_path(lane))
        except OSError:
            pass
    else:
        print(f"unknown command: {cmd}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
