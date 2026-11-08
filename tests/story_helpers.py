"""Test helpers: read through story scenes and chapter cards the way a player would."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from states.codex_state import ChapterCard  # noqa: E402
from states.scene_state import SceneScreen  # noqa: E402


def key(game, k):
    game._handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, unicode="", mod=0))


def finish_story(game, pick=None, limit=400):
    """Close every story overlay on top of the game. In choice menus, pick option ``pick`` (an int or a
    callable(options) -> index); by default explore menus are left and decisions take the first option.
    Returns the ids of the scenes that were shown, in order."""
    shown = []
    for _ in range(limit):
        screen = game.states.overlay
        if isinstance(screen, ChapterCard):
            shown.append(f"card:{screen.chapter['id']}")
            screen.close()
            game.states._pop_closed()
            continue
        if not isinstance(screen, SceneScreen):
            break
        if not shown or shown[-1] != screen.scene.get("id"):
            shown.append(screen.scene.get("id"))
        if screen.in_choice:
            options = screen.options()
            if pick is None:
                index = len(options) - 1 if screen.choices["mode"] == "explore" else 0
            else:
                index = pick(options) if callable(pick) else min(pick, len(options) - 1)
            screen.choose(index)
        else:
            screen.age = 10 ** 6
            screen.handle_key(pygame.K_RETURN)
        game.states._pop_closed()
    return shown
