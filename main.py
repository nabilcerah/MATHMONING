"""Launch MATHMON. Run with: python main.py

The same file starts the browser build (pygbag needs an async ``main`` run with asyncio).
pygbag decides which libraries to download by reading THIS file's imports, so pygame and
sqlite3 are imported here directly even though the game modules import them too.
"""
import asyncio
import sqlite3  # noqa: F401  (tells the web build to include SQLite for saves)

import pygame  # noqa: F401  (tells the web build to load pygame)

from game.game_manager import GameManager


async def main() -> None:
    await GameManager().run_async()


if __name__ == "__main__":
    asyncio.run(main())
