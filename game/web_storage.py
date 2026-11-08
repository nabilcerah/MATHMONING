"""Keep the SQLite save alive in a web browser.

In the browser (pygbag) files live in memory and vanish on reload, so the save file is copied
into the browser's localStorage (base64) whenever it changes, and restored from there at start-up.
On desktop every function here does nothing.
"""
import base64
import hashlib

from config import WEB

KEY = "mathmon_save_v1"


def _storage():
    if not WEB:
        return None
    try:
        import platform  # pygbag's browser bridge
        return platform.window.localStorage
    except Exception:
        return None


def restore(path):
    """Copy a saved game from browser storage to ``path``. Returns True if one was found."""
    store = _storage()
    if store is None:
        return False
    try:
        data = store.getItem(KEY)
        if not data:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(str(data)))
        return True
    except Exception:
        return False


class Persister:
    """Call ``sync()`` now and then; it writes the save to browser storage only when it changed."""

    def __init__(self, path):
        self.path = path
        self.digest = None

    def sync(self):
        store = _storage()
        if store is None:
            return False
        try:
            if not self.path.exists():
                return False
            raw = self.path.read_bytes()
            digest = hashlib.md5(raw).hexdigest()
            if digest == self.digest:
                return False
            store.setItem(KEY, base64.b64encode(raw).decode("ascii"))
            self.digest = digest
            return True
        except Exception:
            return False
