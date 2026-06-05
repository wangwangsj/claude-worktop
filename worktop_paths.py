"""Worktop shared path / identity resolution (stdlib only).

State is GLOBAL: ONE location shared by every project and conversation, located via the
``WORKTOP_STATE`` env var when set, otherwise ``~/.worktop``. A single ball window shows
all projects' conversations, grouped by project. ``worktop.py`` (run from any project) and
``gui.pyw`` (launched anywhere) both resolve to the same global folder, so the GUI sees
every conversation. The single-instance name is fixed, so only one global ball runs.
"""
import os


def _state_dir():
    env = os.environ.get("WORKTOP_STATE")
    if env:
        return os.path.abspath(env)
    return os.path.join(os.path.expanduser("~"), ".worktop")   # GLOBAL — all projects/conversations


STATE_DIR = _state_dir()
LANE_DIR = os.path.join(STATE_DIR, "lanes")
RESP = os.path.join(STATE_DIR, "response.json")   # legacy shared file; per-lane response_<lane>.json is preferred
WINCFG = os.path.join(STATE_DIR, "win.json")
LOG = os.path.join(STATE_DIR, "gui.log")
INSTANCE_NAME = "worktop-global"   # single global ball (one window for all projects)
