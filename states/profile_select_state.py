"""SAVE PROFILES (3:07 report): one player can keep several journeys.

CONTINUE on the title screen opens this list. Each profile shows the trainer's name, their lead
MathMon and level, the world they are in and when it was last played. ENTER loads a profile,
N starts a new one (older profiles are kept), X deletes one (press X twice to confirm).
"""
import pygame

from config import PALETTE
from game import ui
from game.creatures import draw_creature
from game.ui import cursor, panel, text
from monsters.monster_data import has_species, species
from states.base import Screen

MAX_PROFILES = 6
TOP, ROW_H, X0, X1 = 42, 24, 12, 308
WORLD_NAMES = {"number_forest": "Number Forest", "crystal_realm": "Crystal Realm", "algebra_cavern": "Algebra Cavern",
               "geometry_kingdom": "Geometry Kingdom", "chronos_dimension": "Chronos Dimension",
               "village_shop": "Mathmart", "village_sanctuary": "Sanctuary", "village_recovery": "Recovery Center",
               "village_lab": "Professor's Lab"}


def local_time(stamp):
    """SQLite stores UTC ('2026-11-09 07:33:12.345'); show it in the player's own time zone."""
    from datetime import datetime, timezone
    try:
        utc = datetime.strptime(str(stamp)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return utc.astimezone().strftime("%d %b %Y, %H:%M")
    except (TypeError, ValueError):
        return str(stamp or "")[:16]


class ProfileScreen(Screen):
    title = "PROFILES"

    def __init__(self, game):
        super().__init__(game)
        self.confirm_delete = None
        self.choice = None           # ("load", player_id) or ("new", None) when the screen closes
        self.refresh()

    def refresh(self):
        self.profiles = self.game.repository.list_profiles()
        self.selected = min(self.selected, max(0, len(self.profiles)))

    def items(self):
        return self.profiles + [{"new": True}]

    def rows(self):
        return TOP, ROW_H, X0, X1

    # ------------------------------------------------------------------ actions
    def activate(self, index):
        if index >= len(self.profiles):
            self.new_profile()
            return
        self.close(("load", self.profiles[index]["player_id"]))

    def new_profile(self):
        if len(self.profiles) >= MAX_PROFILES:
            self.notice = f"You have {MAX_PROFILES} profiles. Delete one (X) to make room."
            return
        self.close(("new", None))

    def delete(self, index):
        if index >= len(self.profiles):
            return
        profile = self.profiles[index]
        if self.confirm_delete != profile["player_id"]:
            self.confirm_delete = profile["player_id"]
            self.notice = f"Delete {profile['name']}'s journey for good? Press X again to confirm."
            return
        self.game.repository.delete_profile(profile["player_id"])
        self.confirm_delete = None
        self.notice = f"{profile['name']}'s profile was deleted."
        self.refresh()

    def handle_key(self, key, unicode=""):
        if key in (pygame.K_x, pygame.K_DELETE):
            self.delete(self.selected)
            return
        self.confirm_delete = None if key not in (pygame.K_x, pygame.K_DELETE) else self.confirm_delete
        if key == pygame.K_n:
            self.new_profile()
            return
        super().handle_key(key, unicode)

    # ------------------------------------------------------------------ drawing
    def draw(self, surface, frame=0):
        self.draw_frame(surface, "SAVE PROFILES", footer="ENTER: PLAY   N: NEW PROFILE   X: DELETE   ESC: BACK")
        text(surface, f"{len(self.profiles)}/{MAX_PROFILES} profiles - each one is a separate journey", (160, 32), 8,
             PALETTE["sky"], center=True)
        for index, item in enumerate(self.items()):
            y = TOP + index * ROW_H
            chosen = index == self.selected
            panel(surface, (X0, y, X1 - X0, ROW_H - 3), PALETTE["deep"] if chosen else PALETTE["night"],
                  PALETTE["gold"] if chosen else None)
            if chosen:
                cursor(surface, X0 + 3, y + 9, PALETTE["gold"], frame)
            if item.get("new"):
                full = len(self.profiles) >= MAX_PROFILES
                text(surface, "+ NEW PROFILE" if not full else "+ NEW PROFILE (full - delete one first)",
                     (X0 + 40, y + 7), 10, PALETTE["muted"] if full else PALETTE["mint"])
                continue
            if has_species(item["lead"]):
                draw_creature(surface, species(item["lead"]), (X0 + 24, y + ROW_H - 5), 18)
            danger = self.confirm_delete == item["player_id"]
            text(surface, item["name"][:14], (X0 + 40, y + 3), 10, PALETTE["coral"] if danger else
                 (PALETTE["gold"] if chosen else PALETTE["white"]))
            where = WORLD_NAMES.get(item["world"], item["world"].replace("_", " ").title())
            text(surface, f"{item['lead']} Lv {item['level']}  -  {where}", (X0 + 40, y + 13), 8, PALETTE["cream"])
            played = local_time(item["updated_at"])
            text(surface, f"last played {played}", (X1 - 6, y + 4), 7, PALETTE["muted"], align="right")
        if self.notice:
            text(surface, self.notice, (160, 214), 8, PALETTE["coral"], center=True)
