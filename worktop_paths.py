"""Worktop shared path / identity resolution (stdlib only).

State is PER-PROJECT: it lives in ``<project>/.worktop/``, located via the
``WORKTOP_STATE`` environment variable when set, otherwise ``<cwd>/.worktop``.
``worktop.py`` runs from the project root and ``gui.pyw`` is launched with that
root as its working directory, so writer and GUI resolve to the same folder.
The GUI's single-instance name is derived from the state path, so every project
gets its own independent ball window + lanes.
"""
import os
import hashlib


def _state_dir():
    env = os.environ.get("WORKTOP_STATE")
    if env:
        return os.path.abspath(env)
    return os.path.join(os.path.abspath(os.getcwd()), ".worktop")


STATE_DIR = _state_dir()
LANE_DIR = os.path.join(STATE_DIR, "lanes")
RESP = os.path.join(STATE_DIR, "response.json")
WINCFG = os.path.join(STATE_DIR, "win.json")
LOG = os.path.join(STATE_DIR, "gui.log")
INSTANCE_NAME = "worktop-" + hashlib.md5(STATE_DIR.encode("utf-8")).hexdigest()[:10]
