"""Shared settings for MATHMON."""
import os
from pathlib import Path
import sys

FROZEN = getattr(sys, "frozen", False)


def resolve_paths(frozen, executable, source_file, local_data=None):
    root = Path(executable).resolve().parent if frozen else Path(source_file).resolve().parent
    if frozen:
        user_data = Path(local_data or os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        save_dir = user_data / "MATHMON" / "saves"
    else:
        save_dir = root / "saves"
    return root, save_dir


ROOT, SAVE_DIR = resolve_paths(FROZEN, sys.executable, __file__)
VIRTUAL_WIDTH = 320
VIRTUAL_HEIGHT = 240
WINDOW_SCALE = 3
FPS = 60
TITLE = "MATHMON — Train Your Mind. Evolve Your Power."
DATABASE_PATH = SAVE_DIR / "mathmon.sqlite3"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

PALETTE = {
    "ink": (19, 25, 42), "night": (28, 42, 65), "deep": (40, 65, 82),
    "leaf": (71, 139, 91), "mint": (137, 199, 124), "cream": (249, 231, 180),
    "gold": (242, 187, 82), "coral": (235, 112, 92), "sky": (110, 177, 206),
    "white": (255, 247, 220), "muted": (159, 174, 167),
}
