"""Small game-facing player model."""
from dataclasses import dataclass


@dataclass
class Player:
    name: str
    creature: str
    level: int = 1
    hp: int = 30
    max_hp: int = 30
    exp: int = 0
    x: int = 4
    y: int = 6
    player_id: int = 0
    world: str = "number_forest"   # which map the player is on

    @property
    def next_level_exp(self) -> int:
        return self.level * 20

    def add_exp(self, amount: int) -> bool:
        self.exp += max(0, amount)
        leveled = False
        while self.exp >= self.next_level_exp:
            self.exp -= self.next_level_exp
            self.level += 1
            self.max_hp += 4
            self.hp = self.max_hp
            leveled = True
        return leveled
