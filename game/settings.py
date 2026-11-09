"""Player settings (sound, music volume, effects volume, scanlines), kept between sessions.

Desktop: saves/settings.json next to the save file. Browser: localStorage (the save file there is
the SQLite database, which holds per-player data; settings belong to the device).
"""
import json
from pathlib import Path

from config import SAVE_DIR, WEB

KEY = "mathmon_settings_v1"
DEFAULTS = {"sound": True, "music": 7, "sfx": 8, "scanlines": False}


def _path(folder=None):
    """settings.json sits next to the save database (tests use their own temporary folder)."""
    return (Path(folder) if folder else SAVE_DIR) / "settings.json"


def load(folder=None):
    data = {}
    try:
        if WEB:
            from game.web_storage import _storage
            store = _storage()
            raw = store.getItem(KEY) if store is not None else None
            data = json.loads(str(raw)) if raw else {}
        elif _path(folder).exists():
            data = json.loads(_path(folder).read_text(encoding="utf-8"))
    except Exception:
        data = {}
    settings = dict(DEFAULTS)
    settings.update({k: v for k, v in data.items() if k in DEFAULTS})
    settings["music"] = max(0, min(10, int(settings["music"])))
    settings["sfx"] = max(0, min(10, int(settings["sfx"])))
    return settings


def save(settings, folder=None):
    try:
        raw = json.dumps({k: settings[k] for k in DEFAULTS})
        if WEB:
            from game.web_storage import _storage
            store = _storage()
            if store is not None:
                store.setItem(KEY, raw)
        else:
            _path(folder).parent.mkdir(parents=True, exist_ok=True)
            _path(folder).write_text(raw, encoding="utf-8")
    except Exception:
        pass


def apply(game, settings):
    """Push the settings into the running game (audio volumes, mute, scanlines)."""
    from game import audio
    audio.set_volumes(settings["music"] / 10, settings["sfx"] / 10)
    audio.set_enabled(settings["sound"])
    game.sound = settings["sound"]
    game.scanlines = settings["scanlines"]
